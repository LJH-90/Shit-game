# -*- coding: utf-8 -*-
"""
molgam.py — MolGam 진입점.

Overlay(투명 창) + SpriteBank(도트) + World(게임 로직) 을 묶어 그린다.
그리기 계층은 Canvas 아이템을 재사용한다(엔티티마다 생성/삭제하지 않고 coords/itemconfig 갱신).

    python molgam.py            # 실행
    python game.py --selftest   # 로직만 검증
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

# ---------------------------------------------------------------- 경로
def base_dir() -> str:
    """exe 옆 폴더(frozen) 또는 스크립트 폴더."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bundled_dir() -> str:
    return getattr(sys, "_MEIPASS", base_dir())


def load_json(name: str, default=None):
    for d in (base_dir(), bundled_dir()):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    if default is not None:
        return default
    raise FileNotFoundError(name)


def load_config_file(name: str):
    """exe 옆 파일을 우선 쓰되, 새 버전 exe 에 동봉된 파일에만 있는 키는 채워 넣고 저장한다.
    (업데이트 후에도 사용자가 바꾼 핫키·이름은 그대로, 새 캐릭터·설정 키는 추가)"""
    ext = os.path.join(base_dir(), name)
    bun = os.path.join(bundled_dir(), name)
    if os.path.abspath(ext) == os.path.abspath(bun) or not (os.path.isfile(ext) and os.path.isfile(bun)):
        return load_json(name)
    with open(ext, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(bun, "r", encoding="utf-8") as f:
        bundled = json.load(f)
    if isinstance(data, dict) and isinstance(bundled, dict) and updater.merge_missing(data, bundled):
        try:
            with open(ext, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return data


sys.path.insert(0, bundled_dir())
sys.path.insert(0, base_dir())

from overlay import Overlay          # noqa: E402  (DPI 설정 포함, tk 임포트 전에 실행돼야 함)
import tkinter as tk                 # noqa: E402
from sprites import SpriteBank       # noqa: E402
from game import World, CHAR_KEYS    # noqa: E402
try:                                 # v1.6: 팀 B 가 추가하는 상수. 아직 없으면 계약값으로 대체
    from game import ELEMENT_KEYS    # noqa: E402
except ImportError:
    ELEMENT_KEYS = ["cheongryong", "baekho", "jujak", "hyeonmu"]
import updater                       # noqa: E402
from version import VERSION          # noqa: E402

FONT = "Malgun Gothic"
TEXT_FG = "#f2f6ff"
TEXT_SHADOW = "#0a0c12"
GROUND_COLOR = "#8fd3ff"
PLATFORM_FILL = "#2b3340"
PLATFORM_EDGE = "#8fd3ff"
PLAYER_BULLET = "#fff28a"
ENEMY_BULLET = "#ff6b6b"
LASER_COLOR = "#7dffea"
MISSILE_COLOR = "#ffa94d"
ITEM_GLYPH = {"laser": "L", "homing": "H", "spread": "S", "rapid": "R", "life": "♥"}
SHIELD_COLORS = ("#ff8a8a", "#ffd166", "#7dd3fc")   # 실드 1 / 2 / 3
PAPERS_PER_ZONE = 10                                 # 서류 스톰 한 영역에 날리는 종이 수
LOCKED_FG = "#7a8494"
HUD_BG = "#161a22"
HUD_EDGE = "#3d4a5c"
MID_FG = "#ffd166"                                   # 중간 보스 라벨(금색)
ELEM_STRONG_FG = "#ff9f43"                           # 속성 상성 "강!"
ELEM_WEAK_FG = "#9aa4b2"                             # 속성 상성 "약"
ELEM_DEFAULT_COLORS = {"cheongryong": "#4cc9f0", "baekho": "#f1f1f1",
                       "jujak": "#ff6b6b", "hyeonmu": "#8d99ae"}      # hud.element_colors 없을 때
ELEM_DEFAULT_NAMES = ["청룡", "백호", "주작", "현무"]
ELEM_DIM_FG = "#7a8494"                              # 선택 안 된 속성 이름


def _dim_color(hex_color: str, k: float = 0.35) -> str:
    """#rrggbb 를 k 배 어둡게. 투명색(#010203)과 겹치지 않게 최소 8 로 클램프."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        r, g, b = 128, 128, 128
    return "#%02x%02x%02x" % tuple(max(8, int(c * k)) for c in (r, g, b))


class Renderer:
    """World.snapshot() → Canvas. 아이템 풀 재사용."""

    def __init__(self, canvas: tk.Canvas, bank: SpriteBank, config: dict):
        self.cv = canvas
        self.bank = bank
        self.config = config
        self.player_item = None
        self.shield_item = None
        self.aura_feet = None                       # 플레이어 발밑 속성 타원
        self.aura_ring = None                       # 플레이어 몸 뒤 맥동 링
        self.enemy_items: dict[int, dict] = {}     # id -> {"img","label","hp","hpbg","ring"}
        self.bullet_pool: list[int] = []
        self.bullet_img_pool: list[int] = []        # v1.7: 스프라이트 탄(보스 투사체) 이미지 풀
        self.item_pool: list[tuple[int, int]] = []
        self.platform_pool: list[int] = []
        self.pit_pool: list[int] = []
        self.ground_pool: list[int] = []
        self.effect_pool: list[tuple[int, int]] = []  # (shadow_text, text) / oval reused as text
        self.hud_items: dict[str, int] = {}
        self.select_items: list[int] = []
        self._img_refs: list = []                   # PhotoImage 참조 유지
        self._last_state = None
        self._banner_items: tuple[int, int] | None = None
        self._boss_items: dict[str, int] = {}
        self.zone_pool: list[int] = []
        self.paper_pool: list[int] = []
        self.shop_ui: dict = {}
        self._notice: tuple[int, int] | None = None
        self.W = int(canvas["width"])
        self.H = int(canvas["height"])

    # ------------------------------------------------------------ 유틸
    def resize(self, w: int, h: int) -> None:
        self.W, self.H = w, h

    def _text2(self, x, y, text, size=11, anchor="nw", bold=True, fill=TEXT_FG):
        """그림자 있는 텍스트 두 개 생성 → (shadow, main)."""
        f = (FONT, size, "bold" if bold else "normal")
        s = self.cv.create_text(x + 1, y + 1, text=text, font=f, fill=TEXT_SHADOW, anchor=anchor)
        m = self.cv.create_text(x, y, text=text, font=f, fill=fill, anchor=anchor)
        return s, m

    def _set_text2(self, pair, x, y, text, fill=None):
        s, m = pair
        self.cv.coords(s, x + 1, y + 1)
        self.cv.coords(m, x, y)
        self.cv.itemconfig(s, text=text)
        if fill:
            self.cv.itemconfig(m, text=text, fill=fill)
        else:
            self.cv.itemconfig(m, text=text)

    def _hide(self, item) -> None:
        self.cv.itemconfig(item, state="hidden")

    def _show(self, item) -> None:
        self.cv.itemconfig(item, state="normal")

    def _sprite(self, anim, frame, palette, flip, scale):
        # 게임 로직의 scale(2/4/6)은 절반 크기로 그린다 (1/2/3)
        scale = max(1, int(scale) // 2)
        try:
            n = self.bank.anim_len(anim, palette)      # v1.6: 보스 전용 ANIMS (팀 A)
        except TypeError:
            try:
                n = self.bank.anim_len(anim)
            except KeyError:                           # 이 팔레트에 없는 애니(attack/hurt 등) → idle
                anim, frame = "idle", 0
                n = self.bank.anim_len(anim)
        if anim in ("death", "victory", "jump", "fall", "attack", "attack2", "hurt"):
            frame = min(int(frame), max(0, n - 1))
        img = self.bank.get(anim, int(frame), palette, flip, scale)
        ax, ay = self.bank.anchor(anim, int(frame), flip, scale, palette=palette)
        return img, ax, ay

    def _bullet_image(self, b: dict):
        """v1.7: bullets 항목에 sprite(팔레트 key)·anim 이 있으면 1x 이미지, 아니면 None(사각형으로 그림)."""
        palette, anim = b.get("sprite"), b.get("anim")
        if not palette or not anim:
            return None
        frame = int(b.get("frame", 0) or 0)
        try:
            try:
                n = self.bank.anim_len(anim, palette)
            except TypeError:
                n = self.bank.anim_len(anim)
            frame = min(max(0, frame), max(0, n - 1))
            return self.bank.get(anim, frame, palette, bool(b.get("flip")), 1)
        except (KeyError, TypeError, ValueError, IndexError, tk.TclError):
            return None

    def _pool_get(self, pool: list, factory, idx: int):
        while len(pool) <= idx:
            pool.append(factory())
        return pool[idx]

    def _pool_hide_from(self, pool: list, idx: int):
        for it in pool[idx:]:
            self.cv.itemconfig(it, state="hidden")

    @staticmethod
    def _equip_text(hud: dict) -> str:
        """v1.7: hud.equip {slot: level} + hud.equip_labels {slot: label} → "장비: 안전모 Lv1 · 운동화 Lv2"."""
        equip = hud.get("equip") or {}
        labels = hud.get("equip_labels") or {}
        if not isinstance(equip, dict):
            return ""
        parts = []
        for slot, lv in equip.items():
            try:
                lv = int(lv or 0)
            except (TypeError, ValueError):
                continue
            if lv <= 0:
                continue
            parts.append("%s Lv%d" % (labels.get(slot, slot) if isinstance(labels, dict) else slot, lv))
        return "장비: " + " · ".join(parts) if parts else ""

    @staticmethod
    def _stats_text(st) -> str:
        """v1.7: {"str","agi","int"} → "힘 N · 민첩 N · 지혜 N"."""
        if not isinstance(st, dict):
            return ""
        return "힘 %s · 민첩 %s · 지혜 %s" % (st.get("str", "-"), st.get("agi", "-"), st.get("int", "-"))

    def _elem_color(self, hud: dict, key) -> str:
        colors = hud.get("element_colors") or {}
        return colors.get(key) or ELEM_DEFAULT_COLORS.get(key, "#c7d2e0")

    # ------------------------------------------------------------ 그리기
    def draw(self, snap: dict) -> None:
        state = snap["state"]
        if state != self._last_state:
            self._on_state_change(self._last_state, state)
            self._last_state = state

        if state == "select":
            self._draw_select(snap)
            return
        self._draw_world(snap)
        self._draw_hud(snap)
        self._draw_shop(snap)

    def _on_state_change(self, old, new):
        if new == "select" or old == "select":
            # 화면 전환: 전부 숨김
            for it in self.cv.find_all():
                self.cv.itemconfig(it, state="hidden")
            self.enemy_items.clear()  # 재생성 (아이템은 남지만 숨김 상태)

    # --- 캐릭터 선택 화면
    def _draw_select(self, snap):
        hud = snap["hud"]
        names = hud["char_names"]
        sel = hud["select_index"]
        chars = self.config.get("characters", {})
        cx = self.W // 2
        cy = self.H // 2
        gap = 150
        n = len(CHAR_KEYS)
        if not self.select_items:
            # 배경 패널
            self.select_items.append(self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=2))
            self.select_items.append(self._text2(0, 0, "", size=16, anchor="n"))
            for i in range(n):
                box = self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=3)
                img = self.cv.create_image(0, 0, anchor="s")
                name = self._text2(0, 0, "", size=13, anchor="n")
                trait = self._text2(0, 0, "", size=10, anchor="n", bold=False, fill="#9fc9ff")
                stats = self._text2(0, 0, "", size=9, anchor="n", bold=False, fill="#c7d2e0")
                self.select_items.append((box, img, name, trait, stats))
            self.select_items.append(self._text2(0, 0, "", size=10, anchor="s", bold=False, fill="#c7d2e0"))
            self.select_items.append(self._text2(0, 0, "", size=11, anchor="s", fill="#ffd166"))
            # 속성 행: 힌트 + 선택 표시 + 이름 4개
            elem_hint = self._text2(0, 0, "", size=10, anchor="e", bold=False, fill="#c7d2e0")
            elem_mark = self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=2)
            elem_names = [self._text2(0, 0, "", size=11, anchor="center") for _ in ELEMENT_KEYS]
            self.select_items.append((elem_hint, elem_mark, elem_names))
            # v1.7: 스탯 설명 한 줄 (스탯 행 아래, 작고 어둡게)
            self.select_items.append(self._text2(0, 0, "", size=9, anchor="n", bold=False, fill=ELEM_DIM_FG))

        panel = self.select_items[0]
        pw, ph = min(self.W - 40, 640), min(self.H - 20, 340)
        top = cy - ph // 2
        bottom = cy + ph // 2
        self.cv.coords(panel, cx - pw // 2, top, cx + pw // 2, bottom)
        self._show(panel)
        title = self.select_items[1]
        self._set_text2(title, cx, top + 8, "캐릭터 선택   ←→ 캐릭터 · ↑↓ 속성 · Space 시작")
        for it in title:
            self._show(it)
        row_y = top + 122                       # 캐릭터 발 위치
        locked = hud.get("char_locked") or [False] * n
        char_stats = hud.get("char_stats") or [None] * n
        for i in range(n):
            box, img, name, trait, stats = self.select_items[2 + i]
            key = CHAR_KEYS[i]
            x = cx + int((i - (n - 1) / 2) * gap)
            is_locked = i < len(locked) and locked[i]
            # 잠긴 캐릭터는 검은 실루엣
            im, ax, ay = self._sprite("idle", 0, "silhouette" if is_locked else key, False, 2)
            self.cv.itemconfig(img, image=im)
            self.cv.coords(img, x, row_y)
            self._show(img)
            self.cv.coords(box, x - 55, row_y - 88, x + 55, row_y + 66)
            self.cv.itemconfig(box, state="normal" if i == sel else "hidden")
            cinfo = chars.get(key, {})
            st = char_stats[i] if i < len(char_stats) else None
            if is_locked:
                self._set_text2(name, x, row_y + 4, "???", fill=LOCKED_FG)
                self._set_text2(trait, x, row_y + 26, "%s스테이지 클리어 시 해금" % cinfo.get("unlock_stage", 5))
                self._set_text2(stats, x, row_y + 44, "")
            else:
                self._set_text2(name, x, row_y + 4, names[i] if i < len(names) else cinfo.get("name", key), fill=TEXT_FG)
                self._set_text2(trait, x, row_y + 26, "특성: %s" % cinfo.get("trait", ""))
                if isinstance(st, dict):
                    self._set_text2(stats, x, row_y + 44, "민첩 %s · 힘 %s · 지혜 %s"
                                    % (st.get("agi", "-"), st.get("str", "-"), st.get("int", "-")))
                else:
                    self._set_text2(stats, x, row_y + 44, "")
            for it in name + trait + stats:
                self._show(it)

        # 속성 행 (↑↓)
        elem_hint, elem_mark, elem_names = self.select_items[4 + n]
        enames = hud.get("element_names") or ELEM_DEFAULT_NAMES
        eidx = hud.get("element_index")
        if eidx is None:
            ekey = hud.get("element")
            eidx = ELEMENT_KEYS.index(ekey) if ekey in ELEMENT_KEYS else 0
        stat_hint = self.select_items[5 + n]
        self._set_text2(stat_hint, cx, row_y + 62, "힘=공격력 · 민첩=이동/점프 · 지혜=탄속/마법")
        for it in stat_hint:
            self._show(it)
        ey = row_y + 92
        egap = 96
        ex0 = cx - int((len(ELEMENT_KEYS) - 1) / 2 * egap) + 30
        self._set_text2(elem_hint, ex0 - egap // 2 - 10, ey, "↑↓ 속성")
        for it in elem_hint:
            self._show(it)
        for j, key in enumerate(ELEMENT_KEYS):
            ex = ex0 + j * egap
            label = enames[j] if j < len(enames) else key
            color = self._elem_color(hud, key)
            pair = elem_names[j]
            if j == eidx:
                self._set_text2(pair, ex, ey, "◆ %s" % label, fill=color)
                self.cv.coords(elem_mark, ex - egap // 2 + 8, ey - 13, ex + egap // 2 - 8, ey + 13)
                self.cv.itemconfig(elem_mark, outline=color, state="normal")
            else:
                self._set_text2(pair, ex, ey, label, fill=ELEM_DIM_FG)
            for it in pair:
                self._show(it)

        foot = self.select_items[2 + n]
        self._set_text2(foot, cx, bottom - 8,
                        "이동 ←→ · 점프 ↑/Z · 사격 Space/X · 스킬 C · 앉기 ↓ · 일시정지 P · 종료 Esc")
        for it in foot:
            self._show(it)
        best = self.select_items[3 + n]
        self._set_text2(best, cx, bottom - 28, "최고 기록  %s" % format(hud.get("best", 0), ","))
        for it in best:
            self._show(it)

    # --- 월드
    def _draw_world(self, snap):
        gy = snap["ground_y"]
        # 바닥선 (구덩이 제외)
        pits = sorted(snap.get("pits", []))
        segs = []
        x0 = 0
        for px, pw in pits:
            segs.append((x0, px))
            x0 = px + pw
        segs.append((x0, self.W))
        for i, (a, b) in enumerate(segs):
            it = self._pool_get(self.ground_pool, lambda: self.cv.create_line(0, 0, 0, 0, fill=GROUND_COLOR, width=3), i)
            self.cv.coords(it, a, gy + 2, b, gy + 2)
            self._show(it)
        self._pool_hide_from(self.ground_pool, len(segs))
        # 구덩이 표시 (아래로 벌어진 빗금)
        for i, (px, pw) in enumerate(pits):
            it = self._pool_get(self.pit_pool, lambda: self.cv.create_line(0, 0, 0, 0, fill="#ff6b6b", width=2, dash=(4, 4)), i)
            self.cv.coords(it, px, gy + 8, px + pw, gy + 8)
            self._show(it)
        self._pool_hide_from(self.pit_pool, len(pits))
        # 발판
        plats = snap.get("platforms", [])
        for i, (x, y, w, h) in enumerate(plats):
            it = self._pool_get(self.platform_pool,
                                lambda: self.cv.create_rectangle(0, 0, 0, 0, fill=PLATFORM_FILL, outline=PLATFORM_EDGE, width=2), i)
            self.cv.coords(it, x, y, x + w, y + h)
            self._show(it)
        self._pool_hide_from(self.platform_pool, len(plats))

        # 적
        alive = set()
        for e in snap["enemies"]:
            eid = e["id"]
            alive.add(eid)
            d = self.enemy_items.get(eid)
            if d is None:
                d = {
                    "ring": self.cv.create_oval(0, 0, 0, 0, outline="", width=2),   # img 보다 먼저 → 아래 층
                    "img": self.cv.create_image(0, 0, anchor="nw"),
                    "label": self._text2(0, 0, "", size=8, anchor="s"),
                    "hpbg": self.cv.create_rectangle(0, 0, 0, 0, fill="#3a1414", outline=""),
                    "hp": self.cv.create_rectangle(0, 0, 0, 0, fill="#ff5252", outline=""),
                }
                self.enemy_items[eid] = d
            im, ax, ay = self._sprite(e["anim"], e["frame"], e["palette"], e["flip"], e.get("scale", 2))
            x = int(e["x"]) - ax
            y = int(e["y"]) - ay
            self.cv.itemconfig(d["img"], image=im, state="normal")
            self.cv.coords(d["img"], x, y)
            is_mid = bool(e.get("mid"))
            label = e.get("label", "") or ""
            if is_mid:
                label = "★ " + label
            self._set_text2(d["label"], int(e["x"]), y - 4, label, fill=MID_FG if is_mid else TEXT_FG)
            for it in d["label"]:
                self._show(it)
            # 속성 링 (발밑)
            ring = d.get("ring")
            elem = e.get("element")
            if ring is not None:
                if elem and e["anim"] != "death":
                    rw = max(12, int(im.width() * 0.9))
                    ex, ey = int(e["x"]), int(e["y"])
                    self.cv.coords(ring, ex - rw // 2, ey - 4, ex + rw // 2, ey + 4)
                    self.cv.itemconfig(ring, outline=self._elem_color(snap["hud"], elem), state="normal")
                else:
                    self._hide(ring)
            hp, hpm = e.get("hp", 1), e.get("hp_max", 1)
            big = e.get("boss") or is_mid
            show_hp = (hpm > 1) and (big or snap["hud"].get("show_enemy_hp")) and e["anim"] != "death"
            if show_hp and not big:
                bw = 40
                bx = int(e["x"]) - bw // 2
                by = y - 20
                self.cv.coords(d["hpbg"], bx, by, bx + bw, by + 4)
                self.cv.coords(d["hp"], bx, by, bx + int(bw * max(0, hp) / hpm), by + 4)
                self._show(d["hpbg"]); self._show(d["hp"])
            else:
                self._hide(d["hpbg"]); self._hide(d["hp"])
        for eid in list(self.enemy_items):
            if eid not in alive:
                d = self.enemy_items.pop(eid)
                self.cv.delete(d["img"], d["hpbg"], d["hp"], *d["label"])
                if d.get("ring") is not None:
                    self.cv.delete(d["ring"])

        # 플레이어
        p = snap["player"]
        if self.player_item is None:
            # 생성 순서 = 층 순서: 오라(발밑·링) → 실드 → 플레이어 이미지
            # Windows Tk 는 stipple 채움을 불투명하게 그리므로 오라는 윤곽선만 쓴다
            self.aura_feet = self.cv.create_oval(0, 0, 0, 0, outline="", width=2)
            self.aura_ring = self.cv.create_oval(0, 0, 0, 0, outline="", width=2)
            self.shield_item = self.cv.create_oval(0, 0, 0, 0, outline=SHIELD_COLORS[0], width=2)
            self.player_item = self.cv.create_image(0, 0, anchor="nw")
        shield = snap["hud"].get("shield", 0)
        if p.get("visible", True):
            im, ax, ay = self._sprite(p["anim"], p["frame"], p["palette"], p["flip"], p.get("scale", 2))
            px, py = int(p["x"]) - ax, int(p["y"]) - ay
            if snap["hud"].get("melee_t", 0) > 0:
                px += int(3 * math.sin(time.perf_counter() * 60))   # 근접 공격 중 흔들기
            self.cv.itemconfig(self.player_item, image=im, state="normal")
            self.cv.coords(self.player_item, px, py)
            # 속성 오라: 발밑 납작 타원 + 몸 뒤 맥동 링 (플레이어 이미지 아래 층)
            elem = p.get("element")
            if elem and p["anim"] != "death":
                color = self._elem_color(snap["hud"], elem)
                fx, fy = int(p["x"]), int(p["y"])
                w, h = im.width(), im.height()
                fw = max(16, int(w * 1.6))
                self.cv.coords(self.aura_feet, fx - fw // 2, fy - 7, fx + fw // 2, fy + 7)
                self.cv.itemconfig(self.aura_feet, outline=color, fill="", state="normal")
                pulse = 0.5 + 0.5 * math.sin(time.perf_counter() * 4.0)
                r = int(max(w, h) * 0.45 + 4 + 5 * pulse)
                rcy = fy - h // 2
                self.cv.coords(self.aura_ring, fx - r, rcy - r, fx + r, rcy + r)
                self.cv.itemconfig(self.aura_ring, outline=color, fill="", width=2 + int(pulse * 2), state="normal")
                self.cv.tag_lower(self.aura_ring, self.player_item)
                self.cv.tag_lower(self.aura_feet, self.aura_ring)
            else:
                self._hide(self.aura_feet)
                self._hide(self.aura_ring)
            if shield > 0 and p["anim"] != "death":
                # 실드 남은 수만큼 색이 바뀌는 방어막 (3 파랑 → 1 빨강)
                cx, w, h = int(p["x"]), im.width(), im.height()
                r = max(w, h) // 2 + 4
                cy = int(p["y"]) - h // 2
                self.cv.coords(self.shield_item, cx - r, cy - r, cx + r, cy + r)
                self.cv.itemconfig(self.shield_item, outline=SHIELD_COLORS[min(shield, 3) - 1], state="normal")
            else:
                self._hide(self.shield_item)
            if p.get("invincible") and int(time.perf_counter() * 12) % 2 == 0:
                self._hide(self.player_item)
        else:
            self._hide(self.player_item)
            self._hide(self.shield_item)
            self._hide(self.aura_feet)
            self._hide(self.aura_ring)

        # 탄환
        n_img = 0
        for i, b in enumerate(snap["bullets"]):
            it = self._pool_get(self.bullet_pool, lambda: self.cv.create_rectangle(0, 0, 0, 0, outline=""), i)
            # v1.7: sprite 탄(보스 투사체)은 사각형 대신 이미지(중심 앵커). 에셋이 없으면 사각형으로 대체
            im = self._bullet_image(b)
            if im is not None:
                img_it = self._pool_get(self.bullet_img_pool, lambda: self.cv.create_image(0, 0, anchor="center"), n_img)
                n_img += 1
                self.cv.coords(img_it, int(b["x"]), int(b["y"]))
                self.cv.itemconfig(img_it, image=im, state="normal")
                self._hide(it)
                continue
            hw, hh = b["w"] / 2, b["h"] / 2
            self.cv.coords(it, b["x"] - hw, b["y"] - hh, b["x"] + hw, b["y"] + hh)   # x,y = 중심
            kind = b.get("kind", "normal")
            if b["owner"] != "player":
                fill = ENEMY_BULLET
            elif kind == "laser":
                fill = LASER_COLOR
            elif kind == "missile":
                fill = MISSILE_COLOR
            else:
                fill = PLAYER_BULLET
            self.cv.itemconfig(it, fill=fill, state="normal")
        self._pool_hide_from(self.bullet_pool, len(snap["bullets"]))
        self._pool_hide_from(self.bullet_img_pool, n_img)

        # 서류 스톰 영역: 점선 테두리 + 날리는 서류 조각
        zones = snap.get("zones", [])
        gy = snap["ground_y"]
        now = time.perf_counter()
        pi = 0
        for zi, z in enumerate(zones):
            rect = self._pool_get(self.zone_pool, lambda: self.cv.create_rectangle(
                0, 0, 0, 0, outline="#9fd3ff", width=1, dash=(3, 3)), zi)
            zx0 = z["x"] - z["w"] / 2
            self.cv.coords(rect, zx0, gy - z["h"], zx0 + z["w"], gy)
            self._show(rect)
            for k in range(PAPERS_PER_ZONE):
                paper = self._pool_get(self.paper_pool, lambda: self.cv.create_rectangle(
                    0, 0, 0, 0, fill="#f4f4f4", outline="#141416"), pi)
                pi += 1
                px = zx0 + (k * 37 + now * (60 + 11 * k)) % max(1, z["w"] - 8)
                py = gy - 8 - (k * 23 + now * (90 + 7 * k)) % max(1, z["h"] - 12)
                pw, ph = (7, 5) if (k + int(now * 8)) % 2 else (5, 7)
                self.cv.coords(paper, px, py, px + pw, py + ph)
                self._show(paper)
        self._pool_hide_from(self.zone_pool, len(zones))
        self._pool_hide_from(self.paper_pool, pi)

        # 아이템 (무기/1UP)
        items = snap.get("items", [])
        for i, itd in enumerate(items):
            box, txt = self._pool_get(self.item_pool, lambda: (
                self.cv.create_rectangle(0, 0, 0, 0, fill="#1c2230", outline="#ffd166", width=2),
                self.cv.create_text(0, 0, text="", font=(FONT, 8, "bold"), fill="#ffd166")), i)
            s = 14
            x, y = itd["x"], itd["y"]
            blink = itd["t"] < 2.5 and int(itd["t"] * 8) % 2 == 0
            self.cv.coords(box, x - s / 2, y - s, x + s / 2, y)
            self.cv.coords(txt, x, y - s / 2)
            self.cv.itemconfig(txt, text=ITEM_GLYPH.get(itd["kind"], "?"))
            st = "hidden" if blink else "normal"
            self.cv.itemconfig(box, state=st)
            self.cv.itemconfig(txt, state=st)
        for box, txt in self.item_pool[len(items):]:
            self._hide(box)
            self._hide(txt)

        # 이펙트
        for i, fx in enumerate(snap.get("effects", [])):
            pair = self._pool_get(self.effect_pool, lambda: self._text2(0, 0, "", size=10, anchor="center"), i)
            kind = fx["kind"]
            if kind == "text":
                self._set_text2(pair, fx["x"], fx["y"] - int(fx.get("t", 0) * 40), fx.get("text") or "", fill="#ffd166")
            elif kind == "elem":
                # 속성 상성 표시: "강!" 주황 / "약" 회색, 위로 떠오름
                txt = fx.get("text") or ""
                fill = ELEM_STRONG_FG if "강" in txt else ELEM_WEAK_FG
                self._set_text2(pair, fx["x"], fx["y"] - 10 - int(fx.get("t", 0) * 40), txt, fill=fill)
            elif kind == "hit":
                self._set_text2(pair, fx["x"], fx["y"], "✦", fill="#fff28a")
            else:
                self._set_text2(pair, fx["x"], fx["y"], "•", fill="#ffb3b3")
            for it in pair:
                self._show(it)
        for pair in self.effect_pool[len(snap.get("effects", [])):]:
            for it in pair:
                self._hide(it)

    # --- HUD
    def _draw_hud(self, snap):
        hud = snap["hud"]
        if not self.hud_items:
            self.hud_items["bg"] = self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=1)
            self.hud_items["line"] = self._text2(0, 0, "", size=10)
            self.hud_items["elem"] = self._text2(0, 0, "", size=10, anchor="nw")
            self.hud_items["equip"] = self._text2(0, 0, "", size=9, anchor="nw", bold=False, fill="#c7d2e0")
            self.hud_items["banner"] = self._text2(0, 0, "", size=22, anchor="center", fill="#ffd166")
            self.hud_items["sub"] = self._text2(0, 0, "", size=11, anchor="center", bold=False)
            self.hud_items["bossbg"] = self.cv.create_rectangle(0, 0, 0, 0, fill="#3a1414", outline="#7a2a2a")
            self.hud_items["boss"] = self.cv.create_rectangle(0, 0, 0, 0, fill="#ff5252", outline="")
            self.hud_items["bosstxt"] = self._text2(0, 0, "", size=9, anchor="w")
        hearts = "♥" * max(0, hud["lives"]) + "♡" * max(0, self.config.get("lives", 3) - hud["lives"])
        if hud.get("shield_max"):
            hearts += " 실드" + "◆" * max(0, hud["shield"]) + "◇" * max(0, hud["shield_max"] - hud["shield"])
        diff = hud.get("difficulty", "easy")
        diff_txt = ""
        if hud.get("stage_no", 1) >= 15:
            diff_txt = {"easy": " [쉬움]", "normal": " [보통]", "hard": " [하드]"}.get(diff, "")
        line = "%s  %s점  %s%s  · %s" % (hearts, format(hud["score"], ","), hud["stage_name"], diff_txt, hud.get("char_name", ""))
        if hud.get("weapon"):
            left = hud.get("weapon_left")
            unit = "발" if hud["weapon"] == "homing" else "초"
            line += "  · %s %s%s" % (hud.get("weapon_label") or hud["weapon"], left, unit)
        if hud.get("skill_label"):
            cd = hud.get("skill_cd") or 0
            line += "  · %s %s" % (hud["skill_label"], "준비(C)" if cd <= 0 else "%d초" % (int(cd) + 1))
        self._set_text2(self.hud_items["line"], 12, 8, line)
        # 현재 속성 이름을 캐릭터 이름 뒤에 속성 색으로 (별도 아이템: 한 줄에 색을 섞을 수 없음)
        ekey = hud.get("element")
        ename = hud.get("element_name") or ""
        right = 12 + 9 * len(line)
        try:
            bb = self.cv.bbox(self.hud_items["line"][1])
            if bb:
                right = bb[2]
        except Exception:
            pass
        if ekey and ename:
            self._set_text2(self.hud_items["elem"], right + 2, 8, " · %s" % ename, fill=self._elem_color(hud, ekey))
            for it in self.hud_items["elem"]:
                self._show(it)
            right += 2 + 9 * (len(ename) + 2)
        else:
            for it in self.hud_items["elem"]:
                self._hide(it)
        # v1.7: 장비 줄 "장비: 안전모 Lv1 · 운동화 Lv2" (레벨 0 제외, 없으면 숨김)
        equip_txt = self._equip_text(hud)
        bottom = 30
        if equip_txt:
            self._set_text2(self.hud_items["equip"], 12, 28, equip_txt)
            for it in self.hud_items["equip"]:
                self._show(it)
            bottom = 46
            try:
                bb = self.cv.bbox(self.hud_items["equip"][1])
                if bb:
                    right = max(right, bb[2])
            except Exception:
                right = max(right, 12 + 9 * len(equip_txt))
        else:
            for it in self.hud_items["equip"]:
                self._hide(it)
        self.cv.coords(self.hud_items["bg"], 4, 4, right + 20, bottom)
        self._show(self.hud_items["bg"])
        for it in self.hud_items["line"]:
            self._show(it)

        # 보스 HP
        if hud.get("boss_hp_max"):
            bw = min(360, self.W // 3)
            bx = self.W - bw - 16
            by = 10
            self.cv.coords(self.hud_items["bossbg"], bx, by, bx + bw, by + 12)
            self.cv.coords(self.hud_items["boss"], bx, by, bx + int(bw * max(0, hud["boss_hp"]) / hud["boss_hp_max"]), by + 12)
            self._show(self.hud_items["bossbg"]); self._show(self.hud_items["boss"])
            any_mid = any(e.get("mid") for e in snap.get("enemies", []))
            any_boss = any(e.get("boss") and not e.get("mid") for e in snap.get("enemies", []))
            mid_only = any_mid and not any_boss
            self._set_text2(self.hud_items["bosstxt"], bx - 4, by + 6, "★ MID BOSS" if mid_only else "BOSS",
                            fill=MID_FG if mid_only else TEXT_FG)
            self.cv.itemconfig(self.hud_items["bosstxt"][1], anchor="e")
            self.cv.itemconfig(self.hud_items["bosstxt"][0], anchor="e")
            for it in self.hud_items["bosstxt"]:
                self._show(it)
        else:
            for k in ("bossbg", "boss"):
                self._hide(self.hud_items[k])
            for it in self.hud_items["bosstxt"]:
                self._hide(it)

        # 배너
        banner = hud.get("banner")
        state = snap["state"]
        sub = ""
        if state == "paused":
            banner = banner or "일시정지"
            sub = "P 로 재개"
        elif state == "game_over":
            banner = banner or "GAME OVER"
            sub = "점수 %s · Space 로 계속" % format(hud["score"], ",")
        elif state == "continue":
            sub = "← → 선택 · Space 확인"
        elif state == "stage_clear":
            banner = banner or "STAGE CLEAR"
        if banner:
            self._set_text2(self.hud_items["banner"], self.W // 2, self.H // 2 - 20, banner)
            self._set_text2(self.hud_items["sub"], self.W // 2, self.H // 2 + 16, sub)
            for it in self.hud_items["banner"] + self.hud_items["sub"]:
                self._show(it)
        else:
            for it in self.hud_items["banner"] + self.hud_items["sub"]:
                self._hide(it)


    # --- 오른쪽 위 알림 (버전 / 업데이트)
    def draw_notice(self, text: str | None) -> None:
        if self._notice is None:
            self._notice = self._text2(0, 0, "", size=9, anchor="ne", bold=False, fill="#9fe6a0")
        if not text:
            for it in self._notice:
                self._hide(it)
            return
        self._set_text2(self._notice, self.W - 10, 8, text)
        for it in self._notice:
            self._show(it)
            self.cv.tag_raise(it)

    # --- 상점 (스테이지 클리어 후)
    def _shop_all_items(self) -> list:
        ui = self.shop_ui
        items = [ui["panel"], *ui["title"], *ui["score"], *ui["stats"], *ui["msg"], *ui["help"]]
        for box, label, sub in ui["rows"]:
            items += [box, *label, *sub]
        return items

    def _draw_shop(self, snap):
        shop = snap["hud"].get("shop")
        if not shop:
            if self.shop_ui:
                for it in self._shop_all_items():
                    self._hide(it)
            return
        rows = shop.get("items") or []
        if not self.shop_ui:
            self.shop_ui = {
                "panel": self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=2),
                "title": self._text2(0, 0, "", size=14, anchor="n"),
                "score": self._text2(0, 0, "", size=11, anchor="n", fill="#ffd166"),
                "stats": self._text2(0, 0, "", size=10, anchor="n", bold=False, fill="#9fc9ff"),   # v1.7 유효 스탯
                "rows": [],
                "msg": self._text2(0, 0, "", size=10, anchor="s", fill="#ffb3b3"),
                "help": self._text2(0, 0, "", size=9, anchor="s", bold=False, fill="#c7d2e0"),
            }
        ui = self.shop_ui
        while len(ui["rows"]) < len(rows):          # 항목 수가 늘어도(v1.7: 7개) 풀을 키운다
            ui["rows"].append((self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=2),
                               self._text2(0, 0, "", size=11, anchor="n"),
                               self._text2(0, 0, "", size=9, anchor="n", bold=False, fill="#9fc9ff")))
        cx, cy = self.W // 2, self.H // 2
        pw, ph = min(self.W - 40, 840), min(self.H - 20, 250)
        top, bottom = cy - ph // 2, cy + ph // 2
        self.cv.coords(ui["panel"], cx - pw // 2, top, cx + pw // 2, bottom)
        self._set_text2(ui["title"], cx, top + 10, "상점 — 점수로 강화 (쓴 점수는 기록에서 빠짐)")
        self._set_text2(ui["score"], cx, top + 34, "보유 점수 %s" % format(snap["hud"].get("score", 0), ","))
        # v1.7: 현재 유효 스탯 (상점 포함). shop.stats 우선, 없으면 hud.stats
        stats_txt = self._stats_text(shop.get("stats") or snap["hud"].get("stats"))
        self._set_text2(ui["stats"], cx, top + 56, stats_txt)
        cell = (pw - 40) // max(1, len(rows))
        # 칸이 좁으면(7개 항목) 라벨 글꼴을 줄인다
        lsize = 11 if cell >= 110 else (10 if cell >= 92 else 9)
        ssize = 9 if cell >= 92 else 8
        sel = shop.get("index", 0)
        for i, (row, (box, label, sub)) in enumerate(zip(rows, ui["rows"])):
            x = cx - pw // 2 + 20 + cell * i + cell // 2
            self.cv.coords(box, x - cell // 2 + 4, cy - 8, x + cell // 2 - 4, cy + 54)
            self.cv.itemconfig(box, state="normal" if i == sel else "hidden")
            fg = TEXT_FG if row.get("afford") else LOCKED_FG
            for it in label:
                self.cv.itemconfig(it, font=(FONT, lsize, "bold"))
            for it in sub:
                self.cv.itemconfig(it, font=(FONT, ssize, "normal"))
            self._set_text2(label, x, cy + 2, row.get("label", row.get("key", "")), fill=fg)
            lv, mx = int(row.get("level", 0)), int(row.get("max", 0))
            if row.get("key") == "next":
                info = ""
            elif mx <= 0:                                 # v1.7: max 0 = 무제한 → "Lv n" 만
                info = "%s점 · Lv%d" % (format(row.get("cost", 0), ","), lv)
            elif lv >= mx:
                info = "최대 (Lv%d)" % lv
            else:
                info = "%s점 · Lv%d/%d" % (format(row.get("cost", 0), ","), lv, mx)
            self._set_text2(sub, x, cy + 26, info)
        for box, label, sub in ui["rows"][len(rows):]:
            self._hide(box)
            for it in label + sub:
                self._hide(it)
        self._set_text2(ui["msg"], cx, bottom - 26, shop.get("msg") or "")
        self._set_text2(ui["help"], cx, bottom - 8, "← → 선택 · Space 구매 / 다음 스테이지")
        unselected = {box for j, (box, _l, _s) in enumerate(ui["rows"]) if j != sel}
        for j, (box, label, sub) in enumerate(ui["rows"]):
            if j >= len(rows):
                unselected.add(box)
                unselected.update(label)
                unselected.update(sub)
        for it in self._shop_all_items():
            if it not in unselected:
                self._show(it)
            self.cv.tag_raise(it)                 # 월드 아이템보다 위


class App:
    def __init__(self):
        self.config = load_config_file("config.json")
        self.stages = load_config_file("stages.json")
        self.save_path = os.path.join(base_dir(), self.config.get("save_file", "cache.dat"))
        self.save = self._load_save()
        self.fps = int(self.config.get("fps", 30))
        # 원격 업데이트: exe 로 실행할 때만 파일 교체. 지난 업데이트의 .old 는 여기서 지운다
        exe = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) else None
        updater.cleanup(exe)
        upd_cfg = self.config.get("update") or {}
        self.updater = updater.Updater(exe, repo=str(upd_cfg.get("repo", updater.REPO)),
                                       enabled=bool(upd_cfg.get("check", True)))
        self.restart_exe: str | None = None

        self.overlay = Overlay(hotkey=self.config.get("hotkey", "shift+0"),
                               on_toggle=self._on_toggle, on_quit=self.quit)
        self.bank = SpriteBank(self.overlay.root, base_scale=1)
        self.world = World(self.stages, self.config, self.save, self.overlay.w, self.overlay.h)
        self.renderer = Renderer(self.overlay.canvas, self.bank, self.config)
        self.overlay.bind_keys(self._key_down, self._key_up)
        self.running = True
        self.last = time.perf_counter()
        self.acc = 0.0
        self._save_n = 0

        # 자주 쓰는 팔레트 미리 생성 (선택 화면 + 1스테이지)
        try:
            self.bank.preload(list(CHAR_KEYS) + ["intern", "staff", "teamlead"], [1])
        except Exception:
            pass
        try:                                   # v1.6 중간 보스 시트 (팀 A). 에셋이 없어도 기동은 계속
            self.bank.preload(["mai", "choi", "chang"], [1])   # v1.7: chang(뚱뚱보 보스) 포함
        except Exception:
            pass
        self.overlay.root.after(16, self.tick)
        self.updater.check_async()

    # ------------------------------------------------------------ 저장
    def _load_save(self) -> dict:
        try:
            with open(self.save_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _write_save(self) -> None:
        try:
            data = self.world.save_data()
            with open(self.save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    # ------------------------------------------------------------ 입력/토글
    def _on_toggle(self, visible: bool) -> None:
        if visible:
            if self.overlay.place_on_cursor_monitor() or (self.overlay.w, self.overlay.h) != (self.renderer.W, self.renderer.H):
                self.renderer.resize(self.overlay.w, self.overlay.h)
                self.world.resize(self.overlay.w, self.overlay.h)
            self.world.set_paused(False)
            self.last = time.perf_counter()
        else:
            self.world.set_paused(True)
            self._write_save()

    def _key_down(self, key: str) -> None:
        if key == "quit":
            return
        if key == "update":
            # 플레이 중에는 무시 (선택 화면 / 일시정지 / 게임오버에서만)
            if self.world.state in ("select", "continue", "paused", "game_over"):
                self.updater.start_install()
            return
        self.world.key_down(key)

    def _update_notice(self, state: str) -> str | None:
        text = self.updater.notice()
        if text and (state in ("select", "continue", "paused", "game_over")
                     or self.updater.state in ("downloading", "ready", "error")):
            return text
        return f"MolGam v{VERSION}" if state == "select" else None

    def _key_up(self, key: str) -> None:
        self.world.key_up(key)

    def quit(self) -> None:
        if not self.running:
            return
        self.running = False
        self._write_save()
        self.overlay.destroy()

    # ------------------------------------------------------------ 루프
    def tick(self) -> None:
        if not self.running:
            return
        self.overlay.poll()
        if not self.running:
            return
        now = time.perf_counter()
        dt = now - self.last
        self.last = now
        if self.overlay.visible:
            step = 1.0 / self.fps
            self.acc += min(dt, 0.25)
            n = 0
            while self.acc >= step and n < 4:
                self.world.update(step)
                self.acc -= step
                n += 1
            snap = self.world.snapshot()
            self.renderer.draw(snap)
            self.renderer.draw_notice(self._update_notice(snap["state"]))
            if self.updater.state == "ready" and self.restart_exe is None:
                # 새 exe 로 교체 끝: 저장·핫키 해제 후 종료하고 main() 이 새 exe 를 띄운다
                self.restart_exe = self.updater.exe
                self.overlay.root.after(1500, self.quit)
            self._save_n += 1
            if self._save_n >= self.fps * 20:   # 20초마다 진행 저장
                self._save_n = 0
                self._write_save()
        else:
            self.acc = 0.0
        self.overlay.root.after(max(1, 1000 // self.fps), self.tick)

    def run(self) -> None:
        try:
            self.overlay.root.mainloop()
        finally:
            self.quit()


def main() -> int:
    try:
        app = App()
    except RuntimeError as ex:
        # 핫키 등록 실패 등: 콘솔 없이 실행되므로 메시지 박스로 안내
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(ex), "MolGam", 0x10)
        except Exception:
            print(ex)
        return 1
    app.run()
    if app.restart_exe:
        try:
            updater.restart(app.restart_exe)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
