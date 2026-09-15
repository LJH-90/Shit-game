# -*- coding: utf-8 -*-
"""
updater.py — GitHub 릴리스 기반 원격 업데이트 (표준 라이브러리만).

흐름
    check_async()   최신 릴리스 조회 (백그라운드). 새 버전이면 state = "available"
    start_install() 사용자가 U 를 누르면: exe 옆에 <exe>.new 로 받고 크기·SHA256 확인
                    → 실행 중인 exe 를 <exe>.old 로 이름 변경 (윈도우는 실행 중 파일도 이름 변경 가능)
                    → <exe>.new 를 원래 이름으로. 실패하면 되돌림. state = "ready"
    restart(exe)    앱이 종료(핫키 해제)한 뒤 새 exe 실행
    cleanup(exe)    다음 실행 때 남은 .old / .new 삭제

소스 실행(python molgam.py)에서는 알림만 하고 파일을 바꾸지 않는다 (git pull 로 받는다).
네트워크가 막혀 있으면 조용히 넘어간다.

    python updater.py --selftest   # 네트워크 없이 버전 비교·다운로드 검증·교체·설정 병합 검증
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import urllib.request

from version import REPO, VERSION

API = "https://api.github.com/repos/{repo}/releases/latest"
TIMEOUT = 6
CHUNK = 1 << 16


# ---------------------------------------------------------------- pure helpers
def parse_version(s: str) -> tuple[int, int, int] | None:
    m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", (s or "").strip())
    if not m:
        return None
    return tuple(int(g or 0) for g in m.groups())


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return a is not None and b is not None and a > b


def pick_release(data: dict) -> dict | None:
    """GitHub release JSON -> {"version", "url", "size", "sha256", "page"} of its .exe asset."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    if parse_version(tag) is None:
        return None
    for asset in data.get("assets") or []:
        if str(asset.get("name", "")).lower().endswith(".exe") and asset.get("browser_download_url"):
            digest = str(asset.get("digest") or "")
            return {"version": tag.lstrip("v"), "url": asset["browser_download_url"],
                    "size": int(asset.get("size") or 0),
                    "sha256": digest[7:].lower() if digest.startswith("sha256:") else None,
                    "page": str(data.get("html_url", ""))}
    return None


def merge_missing(dst: dict, src: dict) -> bool:
    """Copy keys present in src but missing in dst, recursively. Existing values are never overwritten.
    Used so a user's config.json keeps its hotkey/names while gaining keys added by a new version."""
    changed = False
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
            changed = True
        elif isinstance(dst[k], dict) and isinstance(v, dict):
            changed = merge_missing(dst[k], v) or changed
    return changed


def apply_swap(exe: str, new_path: str) -> None:
    """Put new_path in place of exe. A running exe cannot be overwritten on Windows, but it can be renamed."""
    old = exe + ".old"
    if os.path.exists(old):
        os.remove(old)                      # leftover of an earlier update; that process is gone
    os.replace(exe, old)
    try:
        os.replace(new_path, exe)
    except OSError:
        os.replace(old, exe)                # roll back: keep the working exe
        raise


def cleanup(exe: str | None) -> None:
    if not exe:
        return
    for path in (exe + ".old", exe + ".new"):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass                            # still locked: try again next start


def restart(exe: str) -> None:
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([exe], cwd=os.path.dirname(exe) or None, creationflags=flags, close_fds=True)


# ---------------------------------------------------------------- state machine
class Updater:
    """Polled by the UI thread every tick; network work runs on daemon threads.

    state: disabled | idle | checking | unreachable | latest | available | downloading | ready | error
    """

    MIN_SIZE = 1 << 20                      # a real PyInstaller exe is several MB

    def __init__(self, exe_path: str | None, repo: str = REPO, current: str = VERSION,
                 enabled: bool = True, opener=None):
        self.exe = exe_path                 # None when running from source
        self.repo = repo
        self.current = current
        self.state = "idle" if enabled else "disabled"
        self.release: dict | None = None
        self.progress = 0.0
        self.message = ""
        self._opener = opener or urllib.request.urlopen

    @property
    def can_install(self) -> bool:
        return bool(self.exe)

    def _request(self, url: str, accept: str):
        req = urllib.request.Request(url, headers={"User-Agent": f"MolGam/{self.current}", "Accept": accept})
        return self._opener(req, timeout=TIMEOUT)

    # -- check
    def check_async(self) -> None:
        if self.state == "idle":
            self.state = "checking"
            threading.Thread(target=self.check, daemon=True).start()

    def check(self) -> None:
        try:
            with self._request(API.format(repo=self.repo), "application/vnd.github+json") as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as ex:             # offline / proxy / rate limit: no notice
            self.message = str(ex)[:120]
            self.state = "unreachable"
            return
        rel = pick_release(data)
        if rel and is_newer(rel["version"], self.current):
            self.release = rel
            self.state = "available"
        else:
            self.state = "latest"

    # -- install
    def start_install(self) -> bool:
        if self.state not in ("available", "error") or not self.release or not self.can_install:
            return False
        self.state = "downloading"
        self.progress = 0.0
        threading.Thread(target=self.install, daemon=True).start()
        return True

    def install(self) -> None:
        new_path = self.exe + ".new"
        try:
            self._download(self.release, new_path)
            apply_swap(self.exe, new_path)
        except Exception as ex:
            try:
                os.remove(new_path)
            except OSError:
                pass
            self.message = f"업데이트 실패: {ex}"[:60]
            self.state = "error"
            return
        self.message = f"v{self.release['version']} 설치 완료 · 재시작합니다"
        self.state = "ready"

    def _download(self, rel: dict, path: str) -> None:
        digest = hashlib.sha256()
        got = 0
        with self._request(rel["url"], "application/octet-stream") as resp, open(path, "wb") as fh:
            total = rel["size"] or int(resp.headers.get("Content-Length") or 0)
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                got += len(chunk)
                if total:
                    self.progress = min(1.0, got / total)
        if rel["size"] and got != rel["size"]:
            raise IOError(f"크기 불일치 {got}/{rel['size']}")
        if rel["sha256"] and digest.hexdigest() != rel["sha256"]:
            raise IOError("SHA256 불일치")
        if got < self.MIN_SIZE:
            raise IOError("받은 파일이 너무 작음")

    # -- UI text
    def notice(self) -> str | None:
        s = self.state
        if s in ("available", "error") and self.release:
            ver = self.release["version"]
            if s == "error":
                return f"{self.message} · U 다시 시도"
            return f"새 버전 v{ver} · U 업데이트" if self.can_install else f"새 버전 v{ver} (소스 실행: git pull)"
        if s == "downloading":
            return f"업데이트 받는 중 {int(self.progress * 100)}%"
        if s == "ready":
            return self.message
        return None


# ---------------------------------------------------------------- selftest
def selftest() -> int:
    import io
    import tempfile

    assert is_newer("v1.5.0", "1.4.0") and is_newer("1.10.0", "1.9.9") and is_newer("2.0", "1.9.9")
    assert not is_newer("1.4", "1.4.0") and not is_newer("v1.3.9", "1.4.0") and not is_newer("latest", "1.0.0")
    print("PASS 1: version compare")

    payload = os.urandom(Updater.MIN_SIZE + 12345)
    sha = hashlib.sha256(payload).hexdigest()

    def release_json(sha256=sha, size=len(payload), tag="v9.9.0"):
        return {"tag_name": tag, "draft": False, "prerelease": False, "html_url": "https://example/rel",
                "assets": [{"name": "MolGam.zip", "browser_download_url": "https://example/zip", "size": 1},
                           {"name": "SystemSettingsHelper.exe", "browser_download_url": "https://example/exe",
                            "size": size, "digest": "sha256:" + sha256}]}

    rel = pick_release(release_json())
    assert rel and rel["version"] == "9.9.0" and rel["url"].endswith("/exe") and rel["sha256"] == sha
    assert pick_release({"tag_name": "v2.0.0", "prerelease": True, "assets": []}) is None
    print("PASS 2: release asset pick (exe, digest, skips prerelease)")

    class Resp(io.BytesIO):
        def __init__(self, data):
            super().__init__(data)
            self.headers = {"Content-Length": str(len(data))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()

    def opener_for(release):
        def _open(req, timeout=None):
            url = req.full_url
            if "api.github.com" in url:
                return Resp(json.dumps(release).encode("utf-8"))
            if url.endswith("/exe"):
                return Resp(payload)
            raise OSError("unexpected url " + url)
        return _open

    with tempfile.TemporaryDirectory() as tmp:
        exe = os.path.join(tmp, "game.exe")
        with open(exe, "wb") as fh:
            fh.write(b"old exe")
        up = Updater(exe, current="1.4.0", opener=opener_for(release_json()))
        up.check()
        assert up.state == "available" and "U 업데이트" in up.notice()
        assert up.start_install() is True
        for _ in range(500):
            if up.state not in ("downloading",):
                break
            threading.Event().wait(0.01)
        assert up.state == "ready", (up.state, up.message)
        assert open(exe, "rb").read() == payload and open(exe + ".old", "rb").read() == b"old exe"
        assert not os.path.exists(exe + ".new")
        cleanup(exe)
        assert not os.path.exists(exe + ".old")
        print("PASS 3: download verified, running exe swapped, .old cleaned up")

        # corrupt download: digest mismatch -> error, exe untouched, no .new left
        with open(exe, "wb") as fh:
            fh.write(b"current exe")
        bad = Updater(exe, current="1.4.0", opener=opener_for(release_json(sha256="0" * 64)))
        bad.check()
        bad.install()
        assert bad.state == "error" and "SHA256" in bad.message
        assert open(exe, "rb").read() == b"current exe" and not os.path.exists(exe + ".new")
        print("PASS 4: corrupt download rejected, exe untouched")

        # same version -> latest; network failure -> unreachable; source run never installs
        same = Updater(exe, current="9.9.0", opener=opener_for(release_json()))
        same.check()
        assert same.state == "latest" and same.notice() is None

        def offline(req, timeout=None):
            raise OSError("no route")

        off = Updater(exe, current="1.4.0", opener=offline)
        off.check()
        assert off.state == "unreachable" and off.notice() is None
        src = Updater(None, current="1.4.0", opener=opener_for(release_json()))
        src.check()
        assert src.state == "available" and not src.start_install() and "git pull" in src.notice()
        assert Updater(exe, enabled=False).state == "disabled"
        print("PASS 5: up-to-date / offline / source run / disabled")

    user = {"hotkey": "ctrl+shift+0", "characters": {"jaehwi": {"name": "재휘"}}}
    bundled = {"hotkey": "shift+0", "characters": {"jaehwi": {"name": "이재휘", "speed": 1.3},
                                                    "masked": {"hidden": True}}, "lives": 3}
    assert merge_missing(user, bundled)
    assert user["hotkey"] == "ctrl+shift+0" and user["characters"]["jaehwi"] == {"name": "재휘", "speed": 1.3}
    assert user["characters"]["masked"] == {"hidden": True} and user["lives"] == 3
    assert not merge_missing(user, bundled)
    print("PASS 6: config merge keeps user values, adds new keys")
    print("UPDATER SELFTEST OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(f"MolGam {VERSION} ({REPO}). Run with --selftest.")
