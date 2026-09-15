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


sys.path.insert(0, bundled_dir())
sys.path.insert(0, base_dir())

from overlay import Overlay          # noqa: E402  (DPI 설정 포함, tk 임포트 전에 실행돼야 함)
import tkinter as tk                 # noqa: E402
from sprites import SpriteBank       # noqa: E402
from game import World, CHAR_KEYS    # noqa: E402

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


class Renderer:
    """World.snapshot() → Canvas. 아이템 풀 재사용."""

    def __init__(self, canvas: tk.Canvas, bank: SpriteBank, config: dict):
        self.cv = canvas
        self.bank = bank
        self.config = config
        self.player_item = None
        self.enemy_items: dict[int, dict] = {}     # id -> {"img":item,"label":item,"shadow":item,"hp":item,"hpbg":item}
        self.bullet_pool: list[int] = []
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
        n = self.bank.anim_len(anim)
        if anim in ("death", "victory", "jump", "fall"):
            frame = min(int(frame), n - 1)
        img = self.bank.get(anim, int(frame), palette, flip, scale)
        ax, ay = self.bank.anchor(anim, int(frame), flip, scale, palette=palette)
        return img, ax, ay

    def _pool_get(self, pool: list, factory, idx: int):
        while len(pool) <= idx:
            pool.append(factory())
        return pool[idx]

    def _pool_hide_from(self, pool: list, idx: int):
        for it in pool[idx:]:
            self.cv.itemconfig(it, state="hidden")

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
        if not self.select_items:
            # 배경 패널
            self.select_items.append(self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=2))
            self.select_items.append(self._text2(0, 0, "", size=16, anchor="n"))
            for i in range(len(CHAR_KEYS)):
                box = self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=3)
                img = self.cv.create_image(0, 0, anchor="s")
                name = self._text2(0, 0, "", size=13, anchor="n")
                trait = self._text2(0, 0, "", size=10, anchor="n", bold=False, fill="#9fc9ff")
                self.select_items.append((box, img, name, trait))
            self.select_items.append(self._text2(0, 0, "", size=10, anchor="s", bold=False, fill="#c7d2e0"))
            self.select_items.append(self._text2(0, 0, "", size=11, anchor="s", fill="#ffd166"))

        panel = self.select_items[0]
        pw, ph = min(self.W - 40, 640), min(self.H - 20, 300)
        self.cv.coords(panel, cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2)
        self._show(panel)
        title = self.select_items[1]
        self._set_text2(title, cx, cy - ph // 2 + 10, "캐릭터 선택   ←  →  이동 · Space 시작")
        for it in title:
            self._show(it)
        n = len(CHAR_KEYS)
        locked = hud.get("char_locked") or [False] * n
        for i in range(n):
            box, img, name, trait = self.select_items[2 + i]
            key = CHAR_KEYS[i]
            x = cx + int((i - (n - 1) / 2) * gap)
            is_locked = i < len(locked) and locked[i]
            # 잠긴 캐릭터는 검은 실루엣
            im, ax, ay = self._sprite("idle", 0, "silhouette" if is_locked else key, False, 2)
            self.cv.itemconfig(img, image=im)
            self.cv.coords(img, x, cy + 22)
            self._show(img)
            self.cv.coords(box, x - 55, cy - 30, x + 55, cy + 76)
            self.cv.itemconfig(box, state="normal" if i == sel else "hidden")
            cinfo = chars.get(key, {})
            if is_locked:
                self._set_text2(name, x, cy + 28, "???", fill=LOCKED_FG)
                self._set_text2(trait, x, cy + 50, "%s스테이지 클리어 시 해금" % cinfo.get("unlock_stage", 5))
            else:
                self._set_text2(name, x, cy + 28, names[i] if i < len(names) else cinfo.get("name", key), fill=TEXT_FG)
                self._set_text2(trait, x, cy + 50, "특성: %s" % cinfo.get("trait", ""))
            for it in name + trait:
                self._show(it)
        foot = self.select_items[2 + n]
        self._set_text2(foot, cx, cy + ph // 2 - 8,
                        "이동 ←→ · 점프 ↑/Z · 사격 Space/X · 스킬 C · 앉기 ↓ · 일시정지 P · 종료 Esc")
        for it in foot:
            self._show(it)
        best = self.select_items[3 + n]
        self._set_text2(best, cx, cy + ph // 2 - 28, "최고 기록  %s" % format(hud.get("best", 0), ","))
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
            self._set_text2(d["label"], int(e["x"]), y - 4, e.get("label", ""))
            for it in d["label"]:
                self._show(it)
            hp, hpm = e.get("hp", 1), e.get("hp_max", 1)
            show_hp = (hpm > 1) and (e.get("boss") or snap["hud"].get("show_enemy_hp")) and e["anim"] != "death"
            if show_hp and not e.get("boss"):
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

        # 플레이어
        p = snap["player"]
        if self.player_item is None:
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

        # 탄환
        for i, b in enumerate(snap["bullets"]):
            it = self._pool_get(self.bullet_pool, lambda: self.cv.create_rectangle(0, 0, 0, 0, outline=""), i)
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
        self.cv.coords(self.hud_items["bg"], 4, 4, 12 + 9 * len(line) + 20, 30)
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
            self._set_text2(self.hud_items["bosstxt"], bx - 4, by + 6, "BOSS")
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


    # --- 상점 (스테이지 클리어 후)
    def _shop_all_items(self) -> list:
        ui = self.shop_ui
        items = [ui["panel"], *ui["title"], *ui["score"], *ui["msg"], *ui["help"]]
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
        rows = shop["items"]
        if not self.shop_ui:
            self.shop_ui = {
                "panel": self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=2),
                "title": self._text2(0, 0, "", size=14, anchor="n"),
                "score": self._text2(0, 0, "", size=11, anchor="n", fill="#ffd166"),
                "rows": [(self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=2),
                          self._text2(0, 0, "", size=11, anchor="n"),
                          self._text2(0, 0, "", size=9, anchor="n", bold=False, fill="#9fc9ff"))
                         for _ in rows],
                "msg": self._text2(0, 0, "", size=10, anchor="s", fill="#ffb3b3"),
                "help": self._text2(0, 0, "", size=9, anchor="s", bold=False, fill="#c7d2e0"),
            }
        ui = self.shop_ui
        cx, cy = self.W // 2, self.H // 2
        pw, ph = min(self.W - 40, 720), min(self.H - 20, 230)
        self.cv.coords(ui["panel"], cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2)
        self._set_text2(ui["title"], cx, cy - ph // 2 + 10, "상점 — 점수로 강화 (쓴 점수는 기록에서 빠짐)")
        self._set_text2(ui["score"], cx, cy - ph // 2 + 34, "보유 점수 %s" % format(snap["hud"]["score"], ","))
        cell = (pw - 40) // len(rows)
        for i, (row, (box, label, sub)) in enumerate(zip(rows, ui["rows"])):
            x = cx - pw // 2 + 20 + cell * i + cell // 2
            self.cv.coords(box, x - cell // 2 + 6, cy - 22, x + cell // 2 - 6, cy + 42)
            self.cv.itemconfig(box, state="normal" if i == shop["index"] else "hidden")
            fg = TEXT_FG if row["afford"] else LOCKED_FG
            self._set_text2(label, x, cy - 12, row["label"], fill=fg)
            if row["key"] == "next":
                info = ""
            elif row["level"] >= row["max"]:
                info = "최대 (Lv%d)" % row["level"]
            else:
                info = "%s점 · Lv%d/%d" % (format(row["cost"], ","), row["level"], row["max"])
            self._set_text2(sub, x, cy + 12, info)
        self._set_text2(ui["msg"], cx, cy + ph // 2 - 26, shop.get("msg") or "")
        self._set_text2(ui["help"], cx, cy + ph // 2 - 8, "← → 선택 · Space 구매 / 다음 스테이지")
        unselected = {box for j, (box, _l, _s) in enumerate(ui["rows"]) if j != shop["index"]}
        for it in self._shop_all_items():
            if it not in unselected:
                self._show(it)
            self.cv.tag_raise(it)                 # 월드 아이템보다 위


class App:
    def __init__(self):
        self.config = load_json("config.json")
        self.stages = load_json("stages.json")
        self.save_path = os.path.join(base_dir(), self.config.get("save_file", "cache.dat"))
        self.save = self._load_save()
        self.fps = int(self.config.get("fps", 30))

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
        self.overlay.root.after(16, self.tick)

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
        self.world.key_down(key)

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
