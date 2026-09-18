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
PAPERS_PER_ZONE = 14                                 # 서류 스톰 한 영역에 날리는 종이 수
STORM_EDGE = "#9fd3ff"                               # 서류 스톰 깔때기 윤곽 / 바닥 타원
STORM_RING2 = "#cfe8ff"                              # 바람 고리 교대 색
STORM_RINGS = 4                                     # 바람 고리 수
STORM_FADE = 0.4                                     # 마지막 0.4 초: 깔때기가 좁아지고 종이가 흩어짐
PAPER_FILL = "#f7f7fa"
PAPER_EDGE = "#1b1e26"
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
WARN_FAR = "#ffd166"                                 # 등장 예고: 멀 때(노랑) → 임박(빨강)
WARN_NEAR = "#ff5252"
STREAK_FG = "#e8f1ff"                                # 적 스프린트 속도선
DUST_FILL = "#5b6170"                                # 착지/솟구침 먼지
DUST_EDGE = "#c8ccd4"
DUST_TTL = 0.35
# ---- v1.9 (팀 C): 인벤토리 · 돈 · 난이도 · 근접 · 아군 · 낙하 단어 · 마을
INV_GLYPH = {"laser": ("L", "#7dffea"), "homing": ("H", "#ffa94d"), "spread": ("S", "#fff28a"),
             "rapid": ("R", "#ff9f43"), "life": ("♥", "#ff6b6b"), "bomb": ("B", "#ff5252"),
             "coffee": ("C", "#c08457"), "decoy": ("D", "#9fd3ff"), "drone": ("◈", "#cfe8ff"),
             "dog": ("P", "#f5b971")}                # 슬롯/바닥 아이템 글리프 + 색 (이모지 의존 없음)
INV_LABEL = {"laser": "레이저", "homing": "유도", "spread": "확산", "rapid": "연사", "life": "1UP",
             "bomb": "폭탄", "coffee": "커피", "decoy": "분신", "drone": "드론", "dog": "찹츄"}
INV_SLOTS = 5
INV_SLOT = 40                                        # 슬롯 한 변(px)
INV_GAP = 4
COIN_FILL = "#ffd166"
COIN_EDGE = "#b8860b"
MONEY_FG = "#ffd166"
SLOW_FG = "#6ea8ff"                                  # 야근 커피 슬로우 비네트
DIFF_LABELS = ["쉬움", "보통", "어려움", "하드", "헬", "크레이지"]
DIFF_KEYS = ["easy", "normal", "hard", "harder", "hell", "crazy"]
DIFF_COLORS = ["#4ade80", "#facc15", "#fb923c", "#ff5252", "#e11d48", "#c084fc"]   # 초록 → 빨강 → 보라
MELEE_WHITE = "#f7fbff"
MELEE_AMBER = "#ffb347"
MELEE_CYAN = "#7dffea"
BOMB_BODY = "#2b3340"
BOMB_BAND = "#ff5252"
BLAST_OUT = "#fff28a"
BLAST_IN = "#ff9f43"
BLAST_DIM = "#5a1a1a"
WAVE_FILL = "#ffa94d"
WAVE_EDGE = "#ffd166"
WORD_BG = "#0a0c12"
WORD_TYPED = "#7dffea"
WORD_SIZE = 16
WORD_STYLE = {"gear": ("#ffd166", "#ffd166", "✦"), "wipe": ("#ff5252", TEXT_FG, "×"),
              "money": ("#22c55e", TEXT_FG, "₩"), "life": ("#ff6b6b", TEXT_FG, "♥")}   # (edge, text, mark)
WORD_HINT_T = 1.5
DRONE_BODY = "#5b6170"
DRONE_TOP = "#8d99ae"
DRONE_EYE = "#ff5252"
DRONE_ROTOR = "#cfe8ff"
DOG_FILL = "#f5b971"
DOG_DARK = "#0a0c12"
DECOY_EDGE = "#9fd3ff"
CARD_FILL = "#1c2230"
CARD_SEL = "#ffd166"
RARITY_COLORS = {"normal": "#c7d2e0", "rare": "#4cc9f0", "unique": "#ffd166"}
RARITY_LABEL = {"normal": "일반", "rare": "레어", "unique": "유니크"}
SLOT_LABEL = {"hat": "안전모", "gloves": "작업 장갑", "suit": "사신 정장", "shoes": "운동화",
              "weapon": "사무용 무기", "acc": "사원증"}
SLOT_ORDER = ("hat", "gloves", "suit", "shoes", "weapon", "acc")
SLOT_SYMBOLS = ("₩", "★", "◆", "♥", "7")
FX_TTL = {"slash": 0.2, "word": 0.8, "coin": 0.8, "boxopen": 0.6}   # 스냅샷에 ttl 이 없을 때 진행률 기준


def _rgb(hex_color: str) -> tuple[int, int, int]:
    try:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return 128, 128, 128


def _dim_color(hex_color: str, k: float = 0.35) -> str:
    """#rrggbb 를 k 배 어둡게. 투명색(#010203)과 겹치지 않게 최소 8 로 클램프."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        r, g, b = 128, 128, 128
    return "#%02x%02x%02x" % tuple(max(8, int(c * k)) for c in (r, g, b))


STORM_FILL = _dim_color(STORM_EDGE, 0.25)             # 서류 스톰 깔때기 안쪽 채움


def _light_color(hex_color: str, k: float = 0.5) -> str:
    """#rrggbb 를 흰색 쪽으로 k(0~1) 만큼 섞는다 (불꽃 심지 색)."""
    return "#%02x%02x%02x" % tuple(min(255, max(8, int(c + (255 - c) * k))) for c in _rgb(hex_color))


def _lerp_color(a: str, b: str, k: float) -> str:
    """a → b 를 k(0~1) 로 보간. 투명색과 겹치지 않게 최소 8."""
    k = min(1.0, max(0.0, k))
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#%02x%02x%02x" % tuple(max(8, int(x + (y - x) * k)) for x, y in ((ra, rb), (ga, gb), (ba, bb)))


class Renderer:
    """World.snapshot() → Canvas. 아이템 풀 재사용."""

    def __init__(self, canvas: tk.Canvas, bank: SpriteBank, config: dict):
        self.cv = canvas
        self.bank = bank
        self.config = config
        self.player_item = None
        self.shield_item = None
        self.ult_item = None                        # v2.0: 궁극 스킬 인물 사진 (발 기준 앵커 "s")
        self.aura_layers: list[int] = []            # 플레이어 속성 불꽃 오라 폴리곤 3장 (바깥→심지)
        self.ember_pool: list[int] = []             # 오라에서 떠오르는 불씨 6개
        self.enemy_items: dict[int, dict] = {}     # id -> {"img","label","hp","hpbg","ring"(불꽃 폴리곤)}
        self.warn_pool: list[dict] = []             # 등장 예고 표식 (warnings)
        self.dust_pool: list[int] = []              # "dust" 이펙트 타원 (이펙트당 3개)
        self.streak_pool: list[int] = []            # 적 스프린트 속도선 (적당 3개)
        self.drop_shadow_pool: list[int] = []       # 낙하 중인 적의 착지 그림자
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
        self.zone_pool: list[dict] = []             # 서류 스톰 깔때기: {"outer","inner","rings","base"}
        self.paper_pool: list[int] = []             # 회오리 주위를 도는 종이 (4점 폴리곤)
        self.shop_ui: dict = {}
        self._notice: tuple[int, int] | None = None
        # v1.9 (팀 C) — 월드용 범용 도형 풀: 프레임 시작에 카운터 0, 끝에 남은 항목 숨김
        self.fx_poly_pool: list[int] = []           # smooth 폴리곤 (근접 궤적·충격파·폭발)
        self.fx_line_pool: list[int] = []           # 선 (채찍·낙하 안내선)
        self.fx_oval_pool: list[int] = []           # 타원 (폭발 고리·동전·발밑 표식)
        self.fx_rect_pool: list[int] = []           # 사각형 (폭탄·색종이)
        self.fx_text_pool: list[tuple[int, int]] = []   # 그림자 글자 (동전 +₩ · 단어 폭발)
        self._fx_n = {"poly": 0, "line": 0, "oval": 0, "rect": 0, "text": 0}
        self.word_pool: list[dict] = []             # 낙하 타자 단어 알약 슬롯
        self.ally_pool: list[dict] = []             # 아군(분신/드론/찹츄) 슬롯
        self.inv_ui: dict = {}                      # 인벤토리 바 + 돈 + 슬로우 비네트
        self.town_ui: dict = {}                     # 마을 화면
        self._fonts: dict = {}                      # tkinter.font.Font 캐시 (글자 폭 측정)
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

    # ------------------------------------------------------------ 불꽃/예고 보조
    @staticmethod
    def _flame_points(cx: float, by: float, w: float, h: float, n: int, now: float,
                      seed: float, lean: float) -> list:
        """발밑 (cx, by) 를 중심으로 폭 w·높이 h 인 불꽃 폴리곤 좌표(닫힘, smooth 용).
        바닥은 납작한 타원 아래쪽 호, 위쪽은 n 개의 혀가 sin 으로 각기 다른 주기로 일렁인다.
        lean = 혀 끝의 x 기울기(h 비율, +면 오른쪽으로)."""
        pts = []
        hw = w / 2.0
        ry = max(2.0, h * 0.12)
        m = 4
        for i in range(m + 1):                     # 바닥 호: 왼 → 오
            t = i / m
            pts.append(cx - hw + w * t)
            pts.append(by + ry * math.sin(math.pi * t))
        vh = h * 0.28
        for k in range(n - 1, -1, -1):             # 위쪽 혀: 오 → 왼
            x0 = cx - hw + w * k / n
            x1 = cx - hw + w * (k + 1) / n
            f = 5.0 + 1.7 * ((k + int(seed)) % 3)  # 혀마다 다른 주파수
            ph = seed * 1.3 + k * 2.1
            edge = 0.6 + 0.4 * (1.0 - abs((k + 0.5) / n - 0.5) * 2.0)   # 가운데 혀가 가장 길다
            hk = h * edge * (0.55 + 0.45 * (0.5 + 0.5 * math.sin(now * f + ph)))
            pts.append(x1)
            pts.append(by - vh * (0.8 + 0.2 * math.sin(now * 4.0 + ph)))
            pts.append((x0 + x1) / 2.0 + lean * hk + 2.0 * math.sin(now * 3.3 + ph))
            pts.append(by - hk)
        pts.append(cx - hw)
        pts.append(by - vh)
        return pts

    def _hide_aura(self) -> None:
        for it in self.aura_layers:
            self._hide(it)
        for it in self.ember_pool:
            self._hide(it)

    def _new_warn_slot(self) -> dict:
        """등장 예고 표식 한 세트. ground/sky 가 항목을 골라 쓰고 나머지는 숨긴다."""
        return {
            "rect": self.cv.create_rectangle(0, 0, 0, 0, outline=WARN_FAR, width=2, dash=(4, 3)),
            "shadow": self.cv.create_oval(0, 0, 0, 0, outline=WARN_FAR, width=2, dash=(4, 3)),
            "guide": self.cv.create_line(0, 0, 0, 0, fill=WARN_FAR, width=1, dash=(3, 3)),
            "crack1": self.cv.create_line(0, 0, 0, 0, fill=WARN_FAR, width=2),
            "crack2": self.cv.create_line(0, 0, 0, 0, fill=WARN_FAR, width=2),
            "mark": self._text2(0, 0, "", size=12, anchor="s"),
        }

    def _warn_slot_items(self, slot: dict):
        for k in ("rect", "shadow", "guide", "crack1", "crack2"):
            yield slot[k]
        yield from slot["mark"]

    # ------------------------------------------------------------ 서류 스톰 회오리
    def _new_zone_slot(self) -> dict:
        """깔때기 한 세트. 생성 순서 = 층: inner(채움) → outer(윤곽) → rings → base."""
        inner = self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill=STORM_FILL, outline="", smooth=True, splinesteps=6)
        outer = self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline=STORM_EDGE, width=1,
                                       smooth=True, splinesteps=6)
        rings = [self.cv.create_oval(0, 0, 0, 0, outline=STORM_RING2 if j % 2 else STORM_EDGE, width=1)
                 for j in range(STORM_RINGS)]
        base = self.cv.create_oval(0, 0, 0, 0, outline=STORM_EDGE, width=1, dash=(4, 3))
        return {"inner": inner, "outer": outer, "rings": rings, "base": base}

    def _zone_slot_items(self, slot: dict):
        yield slot["inner"]
        yield slot["outer"]
        yield from slot["rings"]
        yield slot["base"]

    @staticmethod
    def _funnel_hw(w: float, s: float) -> float:
        """높이 비율 s(0 바닥 → 1 꼭대기)에서 깔때기 반폭. 바닥은 좁고 위로 갈수록 넓다."""
        return (w / 2.0) * (0.12 + 0.88 * (s ** 1.3))

    def _funnel_points(self, ax: float, gy: float, w: float, h: float, now: float, seed: float,
                       scale: float) -> list:
        """뒤집힌 깔때기(회오리) 폴리곤 좌표. 양 옆이 sin 으로 물결쳐 도는 느낌을 낸다."""
        pts = []
        m = 6
        for i in range(m + 1):                     # 오른쪽 옆: 바닥 → 꼭대기
            s = i / m
            wob = (1.5 + 4.0 * s) * math.sin(now * 6.0 + s * 7.0 + seed)
            pts.append(ax + self._funnel_hw(w, s) * scale + wob)
            pts.append(gy - s * h)
        for i in range(m, -1, -1):                 # 왼쪽 옆: 꼭대기 → 바닥
            s = i / m
            wob = (1.5 + 4.0 * s) * math.sin(now * 6.0 + s * 7.0 + seed + 2.4)
            pts.append(ax - self._funnel_hw(w, s) * scale + wob)
            pts.append(gy - s * h)
        return pts

    def _draw_shadow_oval(self, item: int, x: float, gy: float, w: float, color: str) -> None:
        """착지 지점 점선 납작 타원 (sky 예고 · 낙하 중 적 공용 스타일)."""
        self.cv.coords(item, x - w / 2.0, gy - 3, x + w / 2.0, gy + 3)
        self.cv.itemconfig(item, outline=color, state="normal")

    # ------------------------------------------------------------ v1.9 범용 도형 풀
    def _fx_begin(self) -> None:
        for k in self._fx_n:
            self._fx_n[k] = 0

    def _fx_end(self) -> None:
        self._pool_hide_from(self.fx_poly_pool, self._fx_n["poly"])
        self._pool_hide_from(self.fx_line_pool, self._fx_n["line"])
        self._pool_hide_from(self.fx_oval_pool, self._fx_n["oval"])
        self._pool_hide_from(self.fx_rect_pool, self._fx_n["rect"])
        for pair in self.fx_text_pool[self._fx_n["text"]:]:
            for it in pair:
                self._hide(it)

    def _poly(self, pts, fill="", outline="", width=1, smooth=True):
        it = self._pool_get(self.fx_poly_pool, lambda: self.cv.create_polygon(
            0, 0, 0, 0, 0, 0, fill="", outline="", smooth=True, splinesteps=6), self._fx_n["poly"])
        self._fx_n["poly"] += 1
        if len(pts) < 6:
            pts = list(pts) + [pts[-2] if pts else 0, pts[-1] if pts else 0] * 3
        self.cv.coords(it, *pts)
        self.cv.itemconfig(it, fill=fill, outline=outline, width=width, smooth=smooth, state="normal")
        return it

    def _line(self, pts, fill=TEXT_FG, width=1, dash=None, smooth=False):
        it = self._pool_get(self.fx_line_pool, lambda: self.cv.create_line(0, 0, 0, 0, fill=TEXT_FG),
                            self._fx_n["line"])
        self._fx_n["line"] += 1
        self.cv.coords(it, *pts)
        self.cv.itemconfig(it, fill=fill, width=width, dash=dash or (), smooth=smooth, state="normal")
        return it

    def _oval(self, x0, y0, x1, y1, fill="", outline="", width=1, dash=None):
        it = self._pool_get(self.fx_oval_pool, lambda: self.cv.create_oval(0, 0, 0, 0, fill="", outline=""),
                            self._fx_n["oval"])
        self._fx_n["oval"] += 1
        self.cv.coords(it, x0, y0, x1, y1)
        self.cv.itemconfig(it, fill=fill, outline=outline, width=width, dash=dash or (), state="normal")
        return it

    def _rect(self, x0, y0, x1, y1, fill="", outline="", width=1, dash=None):
        it = self._pool_get(self.fx_rect_pool, lambda: self.cv.create_rectangle(0, 0, 0, 0, fill="", outline=""),
                            self._fx_n["rect"])
        self._fx_n["rect"] += 1
        self.cv.coords(it, x0, y0, x1, y1)
        self.cv.itemconfig(it, fill=fill, outline=outline, width=width, dash=dash or (), state="normal")
        return it

    def _txt(self, x, y, text, size=10, fill=TEXT_FG, anchor="center", bold=True):
        pair = self._pool_get(self.fx_text_pool, lambda: self._text2(0, 0, "", size=10, anchor="center"),
                              self._fx_n["text"])
        self._fx_n["text"] += 1
        f = (FONT, int(size), "bold" if bold else "normal")
        for it in pair:
            self.cv.itemconfig(it, font=f, anchor=anchor, state="normal")
        self._set_text2(pair, x, y, text, fill=fill)
        return pair

    @staticmethod
    def _crescent_points(cx: float, cy: float, r: float, thick: float, a0: float, a1: float,
                         n: int = 7) -> list:
        """(cx,cy) 중심, 반지름 r 의 a0→a1(라디안) 호를 바깥으로, 두께 thick 의 안쪽 호를 되돌아오는
        초승달 폴리곤. 양 끝은 뾰족(두께 0), 가운데가 가장 두껍다."""
        pts = []
        for i in range(n + 1):
            t = i / n
            a = a0 + (a1 - a0) * t
            pts.append(cx + r * math.cos(a))
            pts.append(cy + r * math.sin(a))
        for i in range(n, -1, -1):
            t = i / n
            a = a0 + (a1 - a0) * t
            ri = r - thick * math.sin(math.pi * t)
            pts.append(cx + ri * math.cos(a))
            pts.append(cy + ri * math.sin(a))
        return pts

    def _font(self, size: int, bold: bool = True):
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            import tkinter.font as tkfont
            try:
                f = tkfont.Font(root=self.cv, family=FONT, size=size, weight="bold" if bold else "normal")
            except tk.TclError:
                f = None
            self._fonts[key] = f
        return f

    def _measure(self, text: str, size: int, bold: bool = True) -> int:
        f = self._font(size, bold)
        if f is None:
            return int(len(text) * size * 0.9)
        try:
            return int(f.measure(text))
        except tk.TclError:
            return int(len(text) * size * 0.9)

    @staticmethod
    def _fnum(v) -> float:
        try:
            return float(v or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _money_text(v) -> str:
        try:
            return "₩ " + format(int(v), ",")
        except (TypeError, ValueError):
            return "₩ 0"

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
        self._draw_town(snap)

    def _on_state_change(self, old, new):
        if new == "select" or old == "select":
            # 화면 전환: 전부 숨김
            for it in self.cv.find_all():
                self.cv.itemconfig(it, state="hidden")
            self.enemy_items.clear()  # 재생성 (아이템은 남지만 숨김 상태)
        if old == "town" and self.town_ui:
            for it in self._town_all_items():
                self._hide(it)

    # --- 캐릭터 선택 화면
    def _difficulty_index(self, hud: dict) -> int:
        """hud.difficulty_index → difficulty_label → 기존 difficulty 키 → 1(보통)."""
        idx = hud.get("difficulty_index")
        if isinstance(idx, int) and 0 <= idx < len(DIFF_LABELS):
            return idx
        label = hud.get("difficulty_label")
        if label in DIFF_LABELS:
            return DIFF_LABELS.index(label)
        key = hud.get("difficulty")
        if key in DIFF_KEYS:
            return DIFF_KEYS.index(key)
        return 1

    def _draw_select(self, snap):
        hud = snap["hud"]
        names = hud["char_names"]
        sel = hud["select_index"]
        chars = self.config.get("characters", {})
        cx = self.W // 2
        cy = self.H // 2
        gap = 160
        n = len(CHAR_KEYS)
        if not self.select_items:
            # 배경 패널
            self.select_items.append(self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=2))
            self.select_items.append(self._text2(0, 0, "", size=15, anchor="n"))
            for i in range(n):
                box = self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=3)
                img = self.cv.create_image(0, 0, anchor="s")
                name = self._text2(0, 0, "", size=13, anchor="n")
                trait = self._text2(0, 0, "", size=10, anchor="n", bold=False, fill="#9fc9ff")
                stats = self._text2(0, 0, "", size=9, anchor="n", bold=False, fill="#c7d2e0")
                self.select_items.append((box, img, name, trait, stats))
            self.select_items.append(self._text2(0, 0, "", size=9, anchor="se", bold=False, fill="#c7d2e0"))
            self.select_items.append(self._text2(0, 0, "", size=10, anchor="sw", fill="#ffd166"))
            # 속성 행: 힌트 + 선택 표시 + 이름 4개
            elem_hint = self._text2(0, 0, "", size=10, anchor="e", bold=False, fill="#c7d2e0")
            elem_mark = self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=2)
            elem_names = [self._text2(0, 0, "", size=11, anchor="center") for _ in ELEMENT_KEYS]
            self.select_items.append((elem_hint, elem_mark, elem_names))
            # v1.7: 스탯 설명 한 줄 (스탯 행 아래, 작고 어둡게)
            self.select_items.append(self._text2(0, 0, "", size=8, anchor="n", bold=False, fill=ELEM_DIM_FG))
            # v1.9: 난이도 행 (힌트 + 선택 박스 + 6개 이름)
            diff_hint = self._text2(0, 0, "", size=10, anchor="e", bold=False, fill="#c7d2e0")
            diff_mark = self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=2)
            diff_names = [self._text2(0, 0, "", size=11, anchor="center") for _ in DIFF_LABELS]
            self.select_items.append((diff_hint, diff_mark, diff_names))

        panel = self.select_items[0]
        ph = min(self.H - 20, 340)
        tall = ph >= 300
        # 낮은 띠(~270px)에서는 패널을 넓혀 속성 행과 난이도 행을 한 줄에 나란히 놓는다
        pw = min(self.W - 40, 760 if tall else 1180)
        side = (not tall) and pw >= 1100
        top = cy - ph // 2
        bottom = cy + ph // 2
        self.cv.coords(panel, cx - pw // 2, top, cx + pw // 2, bottom)
        self._show(panel)
        title = self.select_items[1]
        self._set_text2(title, cx, top + (6 if tall else 3), "캐릭터 선택   ←→ 캐릭터 · ↑↓ 속성 · C 난이도 · Space 시작")
        for it in title:
            self._show(it)
        row_y = top + (132 if tall else 104)     # 캐릭터 발 위치 (좁은 띠에서는 촘촘히)
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
            self.cv.coords(box, x - 66, row_y - 74, x + 66, row_y + 62)
            self.cv.itemconfig(box, state="normal" if i == sel else "hidden")
            cinfo = chars.get(key, {})
            st = char_stats[i] if i < len(char_stats) else None
            if is_locked:
                self._set_text2(name, x, row_y + 2, "???", fill=LOCKED_FG)
                self._set_text2(trait, x, row_y + 25, "%s스테이지 클리어 시 해금" % cinfo.get("unlock_stage", 5))
                self._set_text2(stats, x, row_y + 42, "")
            else:
                self._set_text2(name, x, row_y + 2, names[i] if i < len(names) else cinfo.get("name", key), fill=TEXT_FG)
                self._set_text2(trait, x, row_y + 25, "특성: %s" % cinfo.get("trait", ""))
                if isinstance(st, dict):
                    self._set_text2(stats, x, row_y + 42, "민첩 %s · 힘 %s · 지혜 %s"
                                    % (st.get("agi", "-"), st.get("str", "-"), st.get("int", "-")))
                else:
                    self._set_text2(stats, x, row_y + 42, "")
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
        self._set_text2(stat_hint, cx, row_y + 66, "힘=공격력 · 민첩=이동/점프 · 지혜=탄속/마법")
        for it in stat_hint:
            self._show(it)
        ey = row_y + (100 if tall else 98)
        egap = 96
        if side:
            ex0 = cx - pw // 2 + 140
        else:
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

        # v1.9: 난이도 행 (C) — 초록 → 빨강 → 보라, 잠긴 것은 어둡게 + "잠김"
        diff_hint, diff_mark, diff_names = self.select_items[6 + n]
        didx = self._difficulty_index(hud)
        dlocked = hud.get("difficulty_locked") or []
        dgap = 104
        if side:                                  # 속성 행 오른쪽에 나란히
            dy = ey
            dx0 = ex0 + (len(ELEMENT_KEYS) - 1) * egap + 50 + 60 + dgap // 2
        else:
            dy = ey + 26
            dx0 = cx - int((len(DIFF_LABELS) - 1) / 2 * dgap) + 30
        self._set_text2(diff_hint, dx0 - dgap // 2 - 10, dy, "C 난이도")
        for it in diff_hint:
            self._show(it)
        for j, label in enumerate(DIFF_LABELS):
            dx = dx0 + j * dgap
            pair = diff_names[j]
            is_locked = j < len(dlocked) and bool(dlocked[j])
            color = DIFF_COLORS[j]
            if j == didx:
                shown = (hud.get("difficulty_label") if hud.get("difficulty_label") in DIFF_LABELS else label)
                self._set_text2(pair, dx, dy, "◆ %s" % shown, fill=_dim_color(color, 0.55) if is_locked else color)
                self.cv.coords(diff_mark, dx - dgap // 2 + 6, dy - 13, dx + dgap // 2 - 6, dy + 13)
                self.cv.itemconfig(diff_mark, outline=color, state="normal")
            elif is_locked:
                self._set_text2(pair, dx, dy, "%s 잠김" % label, fill=_dim_color(color, 0.45))
            else:
                self._set_text2(pair, dx, dy, label, fill=_dim_color(color, 0.8))
            for it in pair:
                self._show(it)

        foot = self.select_items[2 + n]
        self._set_text2(foot, cx + pw // 2 - 12, bottom - 4,
                        "이동 ←→ · 점프 ↑/Z · 사격 Space/X · 스킬 C · 앉기 ↓ · 일시정지 P · 종료 Esc")
        for it in foot:
            self._show(it)
        best = self.select_items[3 + n]
        self._set_text2(best, cx - pw // 2 + 12, bottom - 4, "최고 기록  %s" % format(hud.get("best", 0), ","))
        for it in best:
            self._show(it)

    # --- 월드
    def _draw_world(self, snap):
        gy = snap["ground_y"]
        self._fx_begin()
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
        now = time.perf_counter()
        gy = snap["ground_y"]
        alive = set()
        n_streak = 0
        n_drop = 0
        for e in snap["enemies"]:
            eid = e["id"]
            alive.add(eid)
            d = self.enemy_items.get(eid)
            if d is None:
                d = {
                    # 발밑 속성 불꽃(폴리곤). img 보다 먼저 만들어 아래 층
                    "ring": self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="", width=1,
                                                   smooth=True, splinesteps=6),
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
            # 속성 불꽃 (발밑, 혀 3개짜리 작은 wisp)
            ring = d.get("ring")
            elem = e.get("element")
            dead = e["anim"] == "death"
            ex, ey = int(e["x"]), int(e["y"])
            sw, sh = im.width(), im.height()
            if ring is not None:
                if elem and not dead:
                    color = self._elem_color(snap["hud"], elem)
                    rw = max(10, int(sw * 0.6))
                    rh = 19.0 + 4.0 * math.sin(now * 7.0 + eid)
                    lean = 0.25 if e["flip"] else -0.25
                    self.cv.coords(ring, *self._flame_points(ex, ey, rw, rh, 3, now, eid % 7, lean))
                    self.cv.itemconfig(ring, fill=_dim_color(color, 0.7), outline=_light_color(color, 0.35),
                                       state="normal")
                else:
                    self._hide(ring)
            # 스프린트 속도선: 바라보는 반대쪽으로 짧은 가로선 3개 (프레임 패리티로 깜빡임)
            if e.get("sprint") and not dead:
                parity = int(now * 20) % 2
                for j in range(3):
                    ln = self._pool_get(self.streak_pool,
                                        lambda: self.cv.create_line(0, 0, 0, 0, fill=STREAK_FG, width=1), n_streak)
                    n_streak += 1
                    if (j + parity) % 3 == 1:            # 셋 중 하나는 번갈아 꺼짐
                        self._hide(ln)
                        continue
                    ln_len = (10, 18, 14)[j] + (0 if (j + parity) % 2 else 3)
                    sy = ey - sh * (0.25 + 0.25 * j)
                    if e["flip"]:                        # 왼쪽을 본다 → 오른쪽으로 꼬리
                        x0 = ex + sw * 0.5 + 2
                        x1 = x0 + ln_len
                    else:
                        x0 = ex - sw * 0.5 - 2
                        x1 = x0 - ln_len
                    self.cv.coords(ln, x0, sy, x1, sy)
                    self.cv.itemconfig(ln, width=2 if j == 1 else 1, state="normal")
            # 낙하 중: 착지 지점 점선 그림자 (가까워질수록 빨갛게)
            if e.get("drop") and not dead:
                sh_it = self._pool_get(self.drop_shadow_pool,
                                       lambda: self.cv.create_oval(0, 0, 0, 0, outline=WARN_FAR, width=2, dash=(4, 3)),
                                       n_drop)
                n_drop += 1
                near = 1.0 - min(1.0, max(0.0, (gy - ey) / max(1.0, float(gy))))
                self._draw_shadow_oval(sh_it, ex, gy, max(20, sw * 0.8), _lerp_color(WARN_FAR, WARN_NEAR, near))
            # v1.9: 근접 공격 중 → 앞쪽 흰 충격 초승달 / 슬로우 → 발밑 파란 타원
            if e.get("attack") and not dead:
                fdir = -1.0 if e["flip"] else 1.0
                acx = ex + fdir * (sw * 0.5 + 6)
                acy = ey - sh * 0.5
                a0 = (math.pi if fdir < 0 else 0.0) - 0.9
                self._poly(self._crescent_points(acx - fdir * 10, acy, 16, 6, a0, a0 + 1.8),
                           fill=MELEE_WHITE, outline="")
            if e.get("slow") and not dead:
                self._oval(ex - sw * 0.35, ey - 3, ex + sw * 0.35, ey + 4,
                           fill=_dim_color(SLOW_FG, 0.55), outline=SLOW_FG)
            hp, hpm = e.get("hp", 1), e.get("hp_max", 1)
            big = e.get("boss") or is_mid
            show_hp = (hpm > 1) and (big or snap["hud"].get("show_enemy_hp")) and e["anim"] != "death"
            if show_hp and not big:
                bw = 40
                bx = int(e["x"]) - bw // 2
                by = y - 26                       # above the name label (which sits at y-4)
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
        self._pool_hide_from(self.streak_pool, n_streak)

        # 등장 예고 (warnings): ground = 바닥에서 솟구침, sky = 위에서 낙하
        warnings = snap.get("warnings") or []
        n_warn = 0
        for wd in warnings:
            if not isinstance(wd, dict):
                continue
            slot = self._pool_get(self.warn_pool, self._new_warn_slot, n_warn)
            n_warn += 1
            try:
                ttl = float(wd.get("ttl") or 1.0)
                t = float(wd.get("t") or 0.0)
                wx = float(wd.get("x") or 0.0)
            except (TypeError, ValueError):
                for it in self._warn_slot_items(slot):
                    self._hide(it)
                continue
            u = 1.0 - min(1.0, max(0.0, t / max(0.001, ttl)))      # 0 → 1 (임박)
            color = _lerp_color(WARN_FAR, WARN_NEAR, u)
            on = int(now * (6 + 10 * u)) % 2 == 0                   # 임박할수록 빠른 깜빡임
            bob = 3.0 * math.sin(now * 8.0 + wx * 0.01)
            mark_s, mark_m = slot["mark"]
            if wd.get("kind") == "sky":
                self._hide(slot["rect"]); self._hide(slot["crack1"]); self._hide(slot["crack2"])
                sw_ = 30 + 20 * u
                if on:
                    self._draw_shadow_oval(slot["shadow"], wx, gy, sw_, color)
                    self.cv.itemconfig(mark_s, anchor="n"); self.cv.itemconfig(mark_m, anchor="n")
                    self._set_text2(slot["mark"], wx, 6 + bob, "▼", fill=color)
                    self._show(mark_s); self._show(mark_m)
                else:
                    self._hide(slot["shadow"]); self._hide(mark_s); self._hide(mark_m)
                # 착지점 위로 자라는 안내선(바닥에서 60 → 150 px): 임박하면(u > 0.7) 실선
                self.cv.coords(slot["guide"], wx, gy - 4 - (60 + 90 * u), wx, gy - 4)
                self.cv.itemconfig(slot["guide"], fill=color, dash=() if u > 0.7 else (2, 5), state="normal")
            else:                                                   # "ground"
                self._hide(slot["shadow"]); self._hide(slot["guide"])
                rw = 40 + 16 * u
                if on:
                    self.cv.coords(slot["rect"], wx - rw / 2.0, gy - 6, wx + rw / 2.0, gy)
                    self.cv.itemconfig(slot["rect"], outline=color, state="normal")
                    self.cv.itemconfig(mark_s, anchor="s"); self.cv.itemconfig(mark_m, anchor="s")
                    self._set_text2(slot["mark"], wx, gy - 10 + bob, "!", fill=color)
                    self._show(mark_s); self._show(mark_m)
                else:
                    self._hide(slot["rect"]); self._hide(mark_s); self._hide(mark_m)
                # 바닥 균열: 바깥·아래로 비스듬히, 임박할수록 길게
                cl = 4.0 + 14.0 * u
                self.cv.coords(slot["crack1"], wx - 6, gy, wx - 6 - cl, gy + cl * 0.5)
                self.cv.coords(slot["crack2"], wx + 6, gy, wx + 6 + cl, gy + cl * 0.5)
                self.cv.itemconfig(slot["crack1"], fill=color, state="normal")
                self.cv.itemconfig(slot["crack2"], fill=color, state="normal")
        for slot in self.warn_pool[n_warn:]:
            for it in self._warn_slot_items(slot):
                self._hide(it)

        # 플레이어
        p = snap["player"]
        if self.player_item is None:
            # 생성 순서 = 층 순서: 불꽃 오라(바깥→심지) → 불씨 → 실드 → 플레이어 이미지
            # Windows Tk 는 stipple 채움을 불투명하게 그리므로 알파 대신 층 순서로 겹친다
            self.aura_layers = [self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill="", outline="",
                                                       smooth=True, splinesteps=6) for _ in range(3)]
            self.ember_pool = [self.cv.create_oval(0, 0, 0, 0, fill="", outline="") for _ in range(6)]
            self.shield_item = self.cv.create_oval(0, 0, 0, 0, outline=SHIELD_COLORS[0], width=2)
            self.player_item = self.cv.create_image(0, 0, anchor="nw")
            for it in self.aura_layers + self.ember_pool:
                self.cv.tag_lower(it, self.player_item)
        shield = snap["hud"].get("shield", 0)
        if p.get("visible", True):
            im, ax, ay = self._sprite(p["anim"], p["frame"], p["palette"], p["flip"], p.get("scale", 2))
            px, py = int(p["x"]) - ax, int(p["y"]) - ay
            if snap["hud"].get("melee_t", 0) > 0:
                px += int(3 * math.sin(time.perf_counter() * 60))   # 근접 공격 중 흔들기
            self.cv.itemconfig(self.player_item, image=im, state="normal")
            self.cv.coords(self.player_item, px, py)
            # 속성 불꽃 오라: 발밑에서 타오르는 3층 불꽃 + 떠오르는 불씨 (플레이어 이미지 아래 층)
            elem = p.get("element")
            if elem and p["anim"] != "death":
                color = self._elem_color(snap["hud"], elem)
                fx, fy = int(p["x"]), int(p["y"])
                w, h = im.width(), im.height()
                lean = 0.3 if p["flip"] else -0.3            # 바라보는 반대쪽으로 기운다
                layers = ((1.5, 0.9, 5, _dim_color(color, 0.45), 0.0),
                          (1.1, 0.6, 4, color, 3.0),
                          (0.7, 0.35, 3, _light_color(color, 0.55), 6.0))
                for it, (kw, kh, n, fill, seed) in zip(self.aura_layers, layers):
                    self.cv.coords(it, *self._flame_points(fx, fy, max(16, w * kw), h * kh, n, now, seed, lean))
                    self.cv.itemconfig(it, fill=fill, outline=fill, state="normal")
                # 불씨: 발밑에서 위로 떠오르며 좌우로 흔들림, 주기마다 반복
                for k, it in enumerate(self.ember_pool):
                    period = 0.9 + 0.15 * k
                    ph = (now / period + k * 0.37) % 1.0
                    ex_ = fx + (k - 2.5) * w * 0.18 + 4.0 * math.sin(now * 3.0 + k * 1.7) + lean * h * ph
                    ey_ = fy - ph * h * 1.05
                    r = 2.5 - 1.2 * ph
                    self.cv.coords(it, ex_ - r, ey_ - r, ex_ + r, ey_ + r)
                    self.cv.itemconfig(it, fill=_light_color(color, 0.6) if ph < 0.4 else color, state="normal")
            else:
                self._hide_aura()
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
            self._hide_aura()

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
            kind = b.get("kind", "normal")
            if b.get("gravity") and kind not in ("blast", "wave"):
                # 포물선 투사체: 바닥에 점선 착지 그림자 (낙하 적과 같은 스타일)
                sh_it = self._pool_get(self.drop_shadow_pool,
                                       lambda: self.cv.create_oval(0, 0, 0, 0, outline=WARN_FAR, width=2, dash=(4, 3)),
                                       n_drop)
                n_drop += 1
                near = 1.0 - min(1.0, max(0.0, (gy - float(b["y"])) / max(1.0, float(gy))))
                self._draw_shadow_oval(sh_it, float(b["x"]), gy, max(14.0, b["w"] * 1.6),
                                       _lerp_color(WARN_FAR, WARN_NEAR, near))
            if kind in ("bomb", "blast", "wave"):
                self._hide(it)
                self._draw_special_bullet(b, kind, gy, now)
                continue
            self.cv.coords(it, b["x"] - hw, b["y"] - hh, b["x"] + hw, b["y"] + hh)   # x,y = 중심
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
        self._pool_hide_from(self.drop_shadow_pool, n_drop)

        # 서류 스톰 영역: 뒤집힌 깔때기 회오리 + 바람 고리 + 축을 도는 종이
        zones = snap.get("zones", [])
        gy = snap["ground_y"]
        now = time.perf_counter()
        pi = 0
        for zi, z in enumerate(zones):
            slot = self._pool_get(self.zone_pool, self._new_zone_slot, zi)
            ax_, zw, zh = float(z["x"]), float(z["w"]), float(z["h"])
            try:
                zt = float(z.get("t", 1.0) or 0.0)
            except (TypeError, ValueError):
                zt = 1.0
            fade = min(1.0, max(0.0, zt / STORM_FADE))          # 마지막 0.4 초: 1 → 0 으로 좁아짐
            if z.get("kind") == "quake":                        # v2.0 현기 해머 강타: 바닥 충격파 (깔때기 없음)
                for it in self._zone_slot_items(slot):
                    self._hide(it)
                self._draw_quake_zone(ax_, gy, zw, zt, self._fnum(z.get("ttl")) or 1.0, now)
                continue
            # 깔때기 2층: 안쪽 채움(폭 0.75) + 바깥 윤곽
            self.cv.coords(slot["outer"], *self._funnel_points(ax_, gy, zw, zh, now, zi * 1.7, fade))
            self.cv.coords(slot["inner"], *self._funnel_points(ax_, gy, zw, zh * 0.97, now, zi * 1.7 + 1.1, fade * 0.75))
            self._show(slot["outer"]); self._show(slot["inner"])
            # 바람 고리: 위로 떠오르며 반복, 폭은 깔때기를 따른다
            for j, ring in enumerate(slot["rings"]):
                s = (now * 0.35 + j / STORM_RINGS) % 1.0
                rhw = self._funnel_hw(zw, s) * fade * 1.05
                rhh = 3.0 + 3.0 * s
                ry = gy - s * zh
                self.cv.coords(ring, ax_ - rhw, ry - rhh, ax_ + rhw, ry + rhh)
                self._show(ring)
            # 바닥 접점: 폭이 맥동하는 납작 점선 타원
            bw = self._funnel_hw(zw, 0.0) * fade * (2.2 + 0.5 * math.sin(now * 5.0)) + 6.0
            self.cv.coords(slot["base"], ax_ - bw, gy - 3, ax_ + bw, gy + 3)
            self._show(slot["base"])
            # 종이: 축을 타원 궤도로 돌며 상승. 옆에서 볼수록 얇아지고, 뒤쪽(sin θ < 0)은 채움 아래 층
            scatter = 1.0 - fade                                  # 사라질 때 위로 흩어짐
            for k in range(PAPERS_PER_ZONE):
                paper = self._pool_get(self.paper_pool, lambda: self.cv.create_polygon(
                    0, 0, 0, 0, 0, 0, 0, 0, fill=PAPER_FILL, outline=PAPER_EDGE), pi)
                pi += 1
                s = (now * 0.25 + k / PAPERS_PER_ZONE) % 1.0
                th = now * (2.2 + 0.15 * (k % 4)) + k * 1.35
                r = self._funnel_hw(zw, s) * 0.9 * (fade + scatter * 1.6)
                cth, sth = math.cos(th), math.sin(th)
                cx_ = ax_ + r * cth
                cy_ = gy - 4 - s * zh - scatter * (40.0 + 30.0 * k / PAPERS_PER_ZONE)
                pw = max(1.0, 7.0 * abs(cth))                     # 모서리로 보이면 얇게
                ph = 5.0
                tilt = 2.0 * math.sin(th + k)
                self.cv.coords(paper,
                               cx_ - pw / 2, cy_ - ph / 2 + tilt,
                               cx_ + pw / 2, cy_ - ph / 2 - tilt,
                               cx_ + pw / 2, cy_ + ph / 2 - tilt,
                               cx_ - pw / 2, cy_ + ph / 2 + tilt)
                if sth < 0:
                    self.cv.tag_lower(paper, slot["inner"])
                else:
                    self.cv.tag_raise(paper, slot["outer"])
                self._show(paper)
        for slot in self.zone_pool[len(zones):]:
            for it in self._zone_slot_items(slot):
                self._hide(it)
        self._pool_hide_from(self.paper_pool, pi)

        # 아이템 (무기/1UP)
        items = snap.get("items", [])
        for i, itd in enumerate(items):
            box, txt = self._pool_get(self.item_pool, lambda: (
                self.cv.create_rectangle(0, 0, 0, 0, fill="#1c2230", outline="#ffd166", width=2),
                self.cv.create_text(0, 0, text="", font=(FONT, 8, "bold"), fill="#ffd166")), i)
            s = 14
            x, y = itd["x"], itd["y"]
            kind = itd.get("kind", "?")
            it_t = self._fnum(itd.get("t", 9.0))
            blink = it_t < 2.5 and int(it_t * 8) % 2 == 0
            if kind == "coin":
                # v1.9: 바닥의 돈 — 금색 동전 (타원 + 진한 금 테 + ₩), 살짝 떠오르는 bob
                self._hide(box)
                self._hide(txt)
                if not blink:
                    bob = 1.5 * math.sin(now * 5.0 + x * 0.05)
                    cr = 6.0 + 0.6 * math.sin(now * 5.0 + x * 0.05)
                    self._oval(x - cr, y - 7 - cr + bob, x + cr, y - 7 + cr + bob, fill=COIN_FILL, outline=COIN_EDGE, width=2)
                    self._txt(x, y - 7 + bob, "₩", size=7, fill=_dim_color(COIN_EDGE, 0.6))
                continue
            glyph, gcol = INV_GLYPH.get(kind, (ITEM_GLYPH.get(kind, "?"), "#ffd166"))
            self.cv.coords(box, x - s / 2, y - s, x + s / 2, y)
            self.cv.coords(txt, x, y - s / 2)
            self.cv.itemconfig(txt, text=glyph, fill=gcol)
            self.cv.itemconfig(box, outline=gcol)
            st = "hidden" if blink else "normal"
            self.cv.itemconfig(box, state=st)
            self.cv.itemconfig(txt, state=st)
        for box, txt in self.item_pool[len(items):]:
            self._hide(box)
            self._hide(txt)

        # 이펙트
        n_dust = 0
        for i, fx in enumerate(snap.get("effects", [])):
            pair = self._pool_get(self.effect_pool, lambda: self._text2(0, 0, "", size=10, anchor="center"), i)
            kind = fx["kind"]
            if kind == "dust":
                # 착지/솟구침 먼지: 회색 타원 3개가 옆으로 퍼지며 살짝 떠오름 (글자 대신)
                for it in pair:
                    self._hide(it)
                k = 1.0 - min(1.0, max(0.0, float(fx.get("t", 0.0) or 0.0) / DUST_TTL))
                dx0, dy0 = fx["x"], fx["y"]
                for j in range(3):
                    ov = self._pool_get(self.dust_pool, lambda: self.cv.create_oval(
                        0, 0, 0, 0, fill=DUST_FILL, outline=DUST_EDGE), n_dust)
                    n_dust += 1
                    cx_ = dx0 + (j - 1) * (6.0 + 14.0 * k)
                    cy_ = dy0 - 2.0 - 6.0 * k - (2.0 if j == 1 else 0.0)
                    r = 2.0 + 4.0 * k * (1.0 - 0.5 * k)
                    self.cv.coords(ov, cx_ - r, cy_ - r, cx_ + r, cy_ + r)
                    self._show(ov)
                continue
            if kind == "text":
                self._set_text2(pair, fx["x"], fx["y"] - int(fx.get("t", 0) * 40), fx.get("text") or "", fill="#ffd166")
            elif kind == "elem":
                # 속성 상성 표시: "강!" 주황 / "약" 회색, 위로 떠오름
                txt = fx.get("text") or ""
                fill = ELEM_STRONG_FG if "강" in txt else ELEM_WEAK_FG
                self._set_text2(pair, fx["x"], fx["y"] - 10 - int(fx.get("t", 0) * 40), txt, fill=fill)
            elif kind == "hit":
                self._set_text2(pair, fx["x"], fx["y"], "✦", fill="#fff28a")
            elif kind in ("slash", "word", "coin", "boxopen"):
                for it in pair:
                    self._hide(it)
                self._draw_special_effect(fx, kind, now)
                continue
            else:
                self._set_text2(pair, fx["x"], fx["y"], "•", fill="#ffb3b3")
            for it in pair:
                self._show(it)
        for pair in self.effect_pool[len(snap.get("effects", [])):]:
            for it in pair:
                self._hide(it)
        self._pool_hide_from(self.dust_pool, n_dust)

        # v1.9: 근접 궤적 · 아군 · 낙하 타자 단어
        self._draw_melee(snap, now)
        self._draw_allies(snap, now)
        self._draw_words(snap, now)
        self._draw_ult(snap, now)
        self._fx_end()

    # --- v2.0 현기 궁극 "해머 강타": 바닥을 따라 퍼지는 충격 고리 + 갈라진 금 + 먼지
    def _draw_quake_zone(self, x: float, gy: float, w: float, t: float, ttl: float, now: float) -> None:
        u = 1.0 - min(1.0, max(0.0, t / max(0.001, ttl)))         # 0 방금 → 1 끝
        hw = w / 2.0
        fade = min(1.0, max(0.0, t / 0.3))                        # 마지막 0.3 초 흐려짐
        edge = _lerp_color(MELEE_AMBER, TEXT_SHADOW, 1.0 - fade)
        for j in range(3):                                        # 충격 고리 3개, 중심에서 바깥으로
            ph = min(1.0, u * 1.8 - j * 0.22)
            if ph <= 0.0:
                continue
            rw = hw * ph
            rh = 5.0 + 5.0 * ph
            self._oval(x - rw, gy - rh, x + rw, gy + rh, outline=edge, width=3 if j == 0 else 2)
        crack = min(1.0, u * 2.2)
        for k in range(6):                                        # 갈라진 금: 좌우 3줄씩 지그재그
            d = -1 if k < 3 else 1
            L = hw * crack * (0.55 + 0.15 * (k % 3))
            yk = 1.0 + 2.0 * (k % 3)
            pts = [x, gy + yk]
            n = 4
            for i in range(1, n + 1):
                pts.append(x + d * L * i / n)
                pts.append(gy + yk + (2.5 if i % 2 else -2.0) * (1.0 + 0.3 * (k % 3)))
            self._line(pts, fill=_lerp_color("#4a3a22", TEXT_SHADOW, 1.0 - fade), width=2)
        for k in range(8):                                        # 먼지: 양옆으로 퍼지며 떠오름
            ph = min(1.0, u * 1.6)
            px = x + (k - 3.5) / 3.5 * hw * ph
            py = gy - 5.0 - 16.0 * ph * (0.6 + 0.4 * math.sin(k * 1.9 + now * 3.0))
            r = (3.0 + 3.0 * ph) * (0.5 + 0.5 * fade)
            self._oval(px - r * 1.3, py - r, px + r * 1.3, py + r, fill=DUST_FILL, outline=DUST_EDGE)

    # --- v2.0 궁극 스킬 사진 연출: 캐릭터 발 위치에 인물 누끼가 1배 → 2배로 "팍" 터져 나왔다가 사라짐 (약 1초)
    def _draw_ult(self, snap: dict, now: float) -> None:
        hud = snap.get("hud") or {}
        ult = hud.get("ult")
        p = snap.get("player") or {}
        key = p.get("palette")
        base_h = self.bank.ult_base_h(key) if (ult and key) else 0
        if not ult or base_h <= 0 or not p.get("visible", True) or p.get("anim") == "death":
            if self.ult_item is not None:
                self._hide(self.ult_item)
            return
        t = self._fnum(ult.get("t"))
        ttl = self._fnum(ult.get("ttl")) or 1.0
        u = 1.0 - min(1.0, max(0.0, t / max(0.001, ttl)))         # 0 시작 → 1 끝
        A, B = 0.3, 0.65                                          # 0~0.3 s 팽창(오버슈트) · ~0.65 s 유지 · ~1.0 s 소멸
        if u < A:
            s_ = u / A
            e = 1.0 - (1.0 - s_) ** 3
            k = 1.0 + e * (1.0 + 0.22 * math.sin(s_ * math.pi))
        elif u < B:
            k = 2.0 + 0.04 * math.sin(now * 28.0)
        else:
            s_ = (u - B) / (1.0 - B)
            k = 2.0 * (1.0 - s_) ** 2
        scale = max(1, int(p.get("scale", 2)) // 2)
        hpx = base_h * scale * k
        x, y = int(p["x"]), int(p["y"])
        elem = p.get("element")
        color = self._elem_color(hud, elem) if elem else "#ffd166"
        light = _light_color(color, 0.6)
        dark = _dim_color(color, 0.45)
        cy = y - hpx * 0.55                                       # 가슴 높이 = 오라 중심
        # 오라 (사진 뒤): 시작 섬광 → 회전하는 방사형 광선 → 바깥으로 퍼지는 고리 → 발밑 충격 타원
        if u < 0.15:                                              # 시작 섬광: 흰 원이 빠르게 커지며 속성색으로
            fs = u / 0.15
            fr = hpx * (0.3 + 0.75 * fs)
            self._oval(x - fr, cy - fr, x + fr, cy + fr, fill=_lerp_color("#ffffff", light, fs), outline="")
        if k > 0.3:
            n = 12
            r_out = hpx * (0.62 + 0.08 * math.sin(now * 19.0)) * (1.0 if u < B else max(0.0, 1.0 - (u - B) / (1.0 - B)))
            r_in = hpx * 0.40
            rot = now * 2.4
            pts = []
            for i in range(n * 2):
                a = rot + i * math.pi / n
                r = r_out if i % 2 == 0 else r_in
                pts.append(x + math.cos(a) * r)
                pts.append(cy + math.sin(a) * r * 1.15)
            self._poly(pts, fill=dark, outline=light, width=1, smooth=False)
        for j in range(3):
            ph = (u * 2.6 + j / 3.0) % 1.0 if u < B else min(1.0, (u - B) / (1.0 - B) * 1.5 + j * 0.2)
            rr = hpx * (0.45 + 0.85 * ph)
            self._oval(x - rr, cy - rr * 1.1, x + rr, cy + rr * 1.1,
                       outline=_lerp_color(light, dark, ph), width=max(1, int(3 - 2 * ph)))
        gw = hpx * (0.6 + 1.4 * min(1.0, u * 2.0))
        self._oval(x - gw, y - 5, x + gw, y + 5, outline=color, width=2, dash=(5, 3))
        # 사진: 하단을 캐릭터 발에 맞춰 정렬, 바라보는 방향으로 좌우 반전
        if k < 0.45:
            if self.ult_item is not None:
                self._hide(self.ult_item)
            return
        res = self.bank.ult_photo(key, hpx, bool(p.get("flip")))
        if res is None:
            return
        img, _w, _h = res
        if self.ult_item is None:
            self.ult_item = self.cv.create_image(0, 0, anchor="s")
        shake = int(2 * math.sin(now * 70.0)) if u < A else 0
        self.cv.coords(self.ult_item, x + shake, y + 1)
        self.cv.itemconfig(self.ult_item, image=img, state="normal")
        self.cv.tag_raise(self.ult_item)

    # --- v1.9 특수 탄 (폭탄 / 폭발 / 지면 충격파)
    def _draw_special_bullet(self, b: dict, kind: str, gy: float, now: float) -> None:
        x, y = float(b["x"]), float(b["y"])
        w, h = max(4.0, self._fnum(b.get("w")) or 12.0), max(4.0, self._fnum(b.get("h")) or 12.0)
        if kind == "bomb":
            # 결재 도장 폭탄: 어두운 몸통 + 빨간 띠 + 도화선 불꽃
            hw, hh = w / 2.0, h / 2.0
            self._rect(x - hw, y - hh, x + hw, y + hh, fill=BOMB_BODY, outline=TEXT_SHADOW)
            self._rect(x - hw + 1, y - hh * 0.3, x + hw - 1, y + hh * 0.3, fill=BOMB_BAND, outline="")
            self._rect(x - hw * 0.35, y - hh - 3, x + hw * 0.35, y - hh, fill=TEXT_SHADOW, outline="")
            spark = int(now * 20) % 2 == 0
            sr = 2.5 if spark else 1.5
            self._oval(x - sr, y - hh - 5 - sr, x + sr, y - hh - 5 + sr,
                       fill="#fff5cc" if spark else "#ffd166", outline="")
        elif kind == "blast":
            r = self._fnum(b.get("r")) or w / 2.0
            r = max(4.0, r)
            ttl = self._fnum(b.get("ttl"))
            u = 0.0
            if ttl > 0:
                u = 1.0 - min(1.0, max(0.0, self._fnum(b.get("t")) / ttl))        # 0 새것 → 1 사라짐
            outer = _lerp_color(BLAST_OUT, BLAST_DIM, u)
            inner = _lerp_color(BLAST_IN, BLAST_DIM, u)
            self._oval(x - r, y - r, x + r, y + r, fill=_lerp_color(_dim_color(BLAST_IN, 0.55), BLAST_DIM, u),
                       outline=outer, width=3)
            r2 = r * 0.62
            self._oval(x - r2, y - r2, x + r2, y + r2, fill="", outline=inner, width=2)
            if u < 0.5:
                r3 = r * 0.25
                self._oval(x - r3, y - r3, x + r3, y + r3, fill=_light_color(BLAST_OUT, 0.6), outline="")
        else:  # wave: 바닥을 따라가는 톱니 모양 호박색 폴리곤
            hw = w / 2.0
            n = max(3, int(w // 6))
            pts = [x - hw, gy + 2]
            for i in range(n + 1):
                t = i / n
                px = x - hw + w * t
                peak = h * (0.55 + 0.45 * math.sin(now * 25.0 + i * 1.9))
                pts += [px, gy + 2 - (peak if i % 2 else h * 0.25)]
            pts += [x + hw, gy + 2]
            self._poly(pts, fill=WAVE_FILL, outline=WAVE_EDGE, width=1, smooth=False)

    # --- v1.9 특수 이펙트 (근접 궤적 잔상 / 단어 완성 / 돈 획득 / 박스 오픈)
    def _draw_special_effect(self, fx: dict, kind: str, now: float) -> None:
        x, y = float(fx["x"]), float(fx["y"])
        t = self._fnum(fx.get("t"))
        ttl = self._fnum(fx.get("ttl")) or FX_TTL.get(kind, 0.5)
        u = 1.0 - min(1.0, max(0.0, t / max(0.001, ttl)))        # 0 방금 → 1 끝
        if kind == "slash":
            style = fx.get("text") or "knife"
            color = {"hammer": MELEE_AMBER, "whip": MELEE_CYAN}.get(style, MELEE_WHITE)
            r = 22.0 + 10.0 * u
            self._poly(self._crescent_points(x, y, r, 7.0 * (1.0 - u), -1.0, 1.0),
                       fill=_lerp_color(color, TEXT_SHADOW, u * 0.8), outline="")
        elif kind == "word":
            size = int(WORD_SIZE + 12 * u)
            fill = _lerp_color("#fff5cc", ELEM_DIM_FG, u)
            self._txt(x, y - 10.0 * u, fx.get("text") or "", size=size, fill=fill)
        elif kind == "coin":
            txt = fx.get("text") or ""
            if txt and not txt.startswith("+"):
                txt = "+" + txt
            if "₩" not in txt:
                txt = txt.replace("+", "+₩", 1) if txt else "+₩"
            self._txt(x, y - 34.0 * u, txt, size=11, fill=_lerp_color(MONEY_FG, ELEM_DIM_FG, u * u))
        else:  # boxopen: 색종이 6장 흩날림
            cols = ("#ff6b6b", "#ffd166", "#7dffea", "#c084fc", "#4ade80", "#ffa94d")
            for j in range(6):
                a = -math.pi * 0.85 + j * (math.pi * 0.7 / 5)
                d = 14.0 + 38.0 * u
                cx_ = x + math.cos(a) * d
                cy_ = y + math.sin(a) * d + 30.0 * u * u        # 포물선 낙하
                sz = 3.0 - 1.0 * u
                if int(now * 16 + j) % 2:
                    self._rect(cx_ - sz, cy_ - sz * 0.6, cx_ + sz, cy_ + sz * 0.6, fill=cols[j], outline="")
                else:
                    self._rect(cx_ - sz * 0.6, cy_ - sz, cx_ + sz * 0.6, cy_ + sz, fill=cols[j], outline="")

    # --- v1.9 근접 궤적 (hud.melee_t / melee_style / melee_hit)
    def _melee_range(self, palette) -> float:
        cinfo = (self.config.get("characters") or {}).get(palette) or {}
        melee = cinfo.get("melee") if isinstance(cinfo, dict) else None
        if isinstance(melee, dict):
            r = self._fnum(melee.get("range"))
            if r > 0:
                return r
        return 45.0

    def _draw_melee(self, snap: dict, now: float) -> None:
        hud = snap.get("hud") or {}
        mt = self._fnum(hud.get("melee_t"))
        p = snap.get("player") or {}
        if mt <= 0 or not p.get("visible", True) or p.get("anim") == "death":
            return
        style = hud.get("melee_style") or "hip"
        if style == "hip":
            return                                   # 복면: 기존 흔들기만
        hit = max(1, min(3, int(hud.get("melee_hit") or 1)))
        fdir = -1.0 if p.get("flip") else 1.0
        px, py = float(p["x"]), float(p["y"]) - 30.0
        k = min(1.0, mt / 0.25)                       # 1 방금 → 0 끝
        gy = snap["ground_y"]
        if style == "knife":
            # 얇은 흰 초승달 3장 (콤보 수만큼), 바깥쪽이 먼저 흐려진다
            for j in range(hit):
                r = 24.0 + 7.0 * j
                col = _lerp_color(MELEE_WHITE, TEXT_SHADOW, (1.0 - k) * 0.8 + 0.12 * j)
                a0 = -0.95 + 0.12 * j
                a1 = 0.95 - 0.12 * j
                if fdir < 0:
                    a0, a1 = math.pi - a1, math.pi - a0
                self._poly(self._crescent_points(px, py, r, 3.5, a0, a1), fill=col, outline="")
        elif style == "hammer":
            # 두꺼운 호박색 호 (위 → 앞 → 아래로 내려침) + 바닥 충격 고리
            a0, a1 = -1.9, 0.7
            if fdir < 0:
                a0, a1 = math.pi - a1, math.pi - a0
            col = _lerp_color(MELEE_AMBER, TEXT_SHADOW, (1.0 - k) * 0.7)
            self._poly(self._crescent_points(px, py + 4, 36.0, 11.0, a0, a1, 9), fill=col,
                       outline=_light_color(MELEE_AMBER, 0.5), width=1)
            rw = 16.0 + 30.0 * (1.0 - k)
            self._oval(px + fdir * 30 - rw, gy - 4, px + fdir * 30 + rw, gy + 4,
                       fill="", outline=_lerp_color(WAVE_EDGE, TEXT_SHADOW, 1.0 - k), width=2)
        elif style == "whip":
            # 앞으로 길게 뻗는 청록 사인파 (사거리만큼), 끝이 뾰족하게 흔들린다
            rng = self._melee_range(p.get("palette"))
            pts = []
            n = 14
            amp = 7.0 * k
            for i in range(n + 1):
                t = i / n
                pts.append(px + fdir * (8.0 + rng * t))
                pts.append(py - 6.0 + amp * math.sin(t * math.pi * 3.0 - now * 40.0) * (0.3 + 0.7 * t))
            col = _lerp_color(MELEE_CYAN, TEXT_SHADOW, (1.0 - k) * 0.7)
            self._line(pts, fill=col, width=2, smooth=True)
            self._line(pts, fill=_light_color(MELEE_CYAN, 0.7), width=1, smooth=True)
            tip = 3.0
            self._oval(pts[-2] - tip, pts[-1] - tip, pts[-2] + tip, pts[-1] + tip, fill=_light_color(MELEE_CYAN, 0.8), outline="")

    # --- v1.9 아군: 분신(플레이어 스프라이트) / 드론 / 찹츄 (렌더러 내장 픽셀아트)
    def _new_ally_slot(self) -> dict:
        slot = {
            "img": self.cv.create_image(0, 0, anchor="nw"),
            "frame": self.cv.create_rectangle(0, 0, 0, 0, outline=DECOY_EDGE, width=1, dash=(3, 3)),
            "rects": [self.cv.create_rectangle(0, 0, 0, 0, fill="", outline="") for _ in range(10)],
            "ovals": [self.cv.create_oval(0, 0, 0, 0, fill="", outline="") for _ in range(3)],
            "lines": [self.cv.create_line(0, 0, 0, 0, fill=TEXT_FG) for _ in range(3)],
            "label": self._text2(0, 0, "", size=8, anchor="s"),
        }
        return slot

    def _ally_slot_items(self, slot: dict):
        yield slot["img"]
        yield slot["frame"]
        yield from slot["rects"]
        yield from slot["ovals"]
        yield from slot["lines"]
        yield from slot["label"]

    def _px_rect(self, item, x, y, w, h, fill, outline=DOG_DARK):
        self.cv.coords(item, x, y, x + w, y + h)
        self.cv.itemconfig(item, fill=fill, outline=outline, state="normal")

    def _draw_allies(self, snap: dict, now: float) -> None:
        allies = snap.get("allies") or []
        n = 0
        for a in allies:
            if not isinstance(a, dict):
                continue
            slot = self._pool_get(self.ally_pool, self._new_ally_slot, n)
            n += 1
            for it in self._ally_slot_items(slot):
                self._hide(it)
            kind = a.get("kind")
            try:
                ax, ay = float(a["x"]), float(a["y"])
            except (KeyError, TypeError, ValueError):
                continue
            flip = bool(a.get("flip"))
            fdir = -1 if flip else 1
            rects, ovals, lines = slot["rects"], slot["ovals"], slot["lines"]
            if kind == "decoy":
                if int(now * 30) % 6 == 0:
                    continue                                   # 깜빡임: 가짜라는 표시
                try:
                    im, iax, iay = self._sprite(a.get("anim") or "idle", a.get("frame", 0),
                                                a.get("palette") or snap["player"].get("palette"), flip, a.get("scale", 2))
                except Exception:
                    continue
                x0, y0 = int(ax) - iax, int(ay) - iay
                self.cv.coords(slot["img"], x0, y0)
                self.cv.itemconfig(slot["img"], image=im, state="normal")
                self.cv.coords(slot["frame"], x0 - 3, y0 - 3, x0 + im.width() + 3, y0 + im.height() + 3)
                self._show(slot["frame"])
                self._set_text2(slot["label"], ax, y0 - 5, "분신", fill=DECOY_EDGE)
                for it in slot["label"]:
                    self._show(it)
            elif kind == "drone":
                # 14×10 도트(2px 단위): 몸통 · 윗판 · 로터 2개(프레임 교대) · 빨간 눈 · 다리
                u = 2
                bob = 3.0 * math.sin(now * 4.0 + ax * 0.01)
                cx_, cy_ = ax, ay + bob
                bx, by = cx_ - 7 * u, cy_ - 3 * u
                self._px_rect(rects[0], bx, by, 14 * u, 6 * u, DRONE_BODY)                 # 몸통
                self._px_rect(rects[1], bx + 2 * u, by - 1 * u, 10 * u, 2 * u, DRONE_TOP)  # 윗판
                self._px_rect(rects[2], bx + 3 * u, by + 6 * u, 2 * u, 1 * u, DRONE_BODY)  # 다리
                self._px_rect(rects[3], bx + 9 * u, by + 6 * u, 2 * u, 1 * u, DRONE_BODY)
                self._px_rect(rects[4], bx + 6 * u, by - 3 * u, 2 * u, 2 * u, DRONE_BODY)  # 로터 축
                parity = int(now * 16) % 2
                for j, rx in enumerate((bx + 1 * u, bx + 8 * u)):
                    wdt = 5 * u if (j + parity) % 2 else 3 * u
                    self._px_rect(rects[5 + j], rx + (5 * u - wdt) / 2, by - 4 * u, wdt, u, DRONE_ROTOR, outline="")
                ex_ = bx + (10 * u if fdir > 0 else 2 * u)
                self._px_rect(rects[7], ex_, by + 2 * u, 2 * u, 2 * u, DRONE_EYE, outline="")   # 눈
                if int(now * 6) % 2:
                    self._px_rect(rects[8], ex_ + (2 * u if fdir > 0 else -u), by + 2 * u + 1, u, u, _light_color(DRONE_EYE, 0.6), outline="")
                self._set_text2(slot["label"], cx_, by - 5 * u - 2, "드론", fill=DRONE_ROTOR)
                for it in slot["label"]:
                    self._show(it)
            elif kind == "dog":
                # 20×14 도트(2px 단위) 찹츄: 몸통 · 머리 · 귀 · 꼬리(흔들) · 다리 4(달릴 때 교대) · 눈 · 코
                u = 2
                moving = (a.get("anim") in ("run", "walk", "jump")) or abs(self._fnum(a.get("vx"))) > 1
                step = int(now * 10) % 2 if moving else 0
                bx, by = ax - 10 * u, ay - 14 * u
                hx = bx + (12 * u if fdir > 0 else 0)                                        # 머리 x
                self._px_rect(rects[0], bx + 3 * u, by + 5 * u, 13 * u, 6 * u, DOG_FILL)      # 몸통
                self._px_rect(rects[1], hx, by + 2 * u, 8 * u, 7 * u, DOG_FILL)               # 머리
                self._px_rect(rects[2], hx + (5 * u if fdir > 0 else u), by + 1 * u, 2 * u, 3 * u, _dim_color(DOG_FILL, 0.75))  # 귀
                legs = ((4, 0), (7, 1), (11, 1), (14, 0))
                for j, (lx, ph) in enumerate(legs):
                    off = (u if (ph + step) % 2 else 0) if moving else 0
                    self._px_rect(rects[3 + j], bx + lx * u, by + 11 * u - off, 2 * u, 3 * u, DOG_FILL)
                tail_x = bx + (2 * u if fdir > 0 else 17 * u)
                wag = 1 if int(now * 8) % 2 else -1
                self._px_rect(rects[7], tail_x, by + 3 * u + wag * u, 2 * u, 3 * u, _dim_color(DOG_FILL, 0.8))  # 꼬리
                eye_x = hx + (6 * u if fdir > 0 else u)
                self._px_rect(rects[8], eye_x, by + 4 * u, u, u, DOG_DARK, outline="")       # 눈
                nose_x = hx + (7 * u if fdir > 0 else 0)
                self._px_rect(rects[9], nose_x, by + 6 * u, u, u, DOG_DARK, outline="")      # 코
                self._set_text2(slot["label"], ax, by - 3, "찹츄", fill=DOG_FILL)
                for it in slot["label"]:
                    self._show(it)
        for slot in self.ally_pool[n:]:
            for it in self._ally_slot_items(slot):
                self._hide(it)

    # --- v1.9 낙하 타자 단어: 어두운 알약 배경 + 입력한 앞부분(청록)/나머지(흰) + 착지 안내선
    def _new_word_slot(self) -> dict:
        slot = {
            "guide": self.cv.create_line(0, 0, 0, 0, fill=HUD_EDGE, dash=(3, 4)),
            "capL": self.cv.create_oval(0, 0, 0, 0, fill=WORD_BG, outline=HUD_EDGE),
            "capR": self.cv.create_oval(0, 0, 0, 0, fill=WORD_BG, outline=HUD_EDGE),
            "body": self.cv.create_rectangle(0, 0, 0, 0, fill=WORD_BG, outline=""),
            "top": self.cv.create_line(0, 0, 0, 0, fill=HUD_EDGE),
            "bot": self.cv.create_line(0, 0, 0, 0, fill=HUD_EDGE),
            "mark": self._text2(0, 0, "", size=11, anchor="center"),
            "typed": self._text2(0, 0, "", size=WORD_SIZE, anchor="w"),
            "rest": self._text2(0, 0, "", size=WORD_SIZE, anchor="w"),
            "sparks": [self.cv.create_text(0, 0, text="✦", font=(FONT, 8, "bold"), fill="#fff5cc") for _ in range(4)],
            "hint": self._text2(0, 0, "", size=8, anchor="n", fill="#fff5cc"),
        }
        return slot

    def _word_slot_items(self, slot: dict):
        for k in ("guide", "capL", "capR", "body", "top", "bot"):
            yield slot[k]
        yield from slot["mark"]
        yield from slot["typed"]
        yield from slot["rest"]
        yield from slot["sparks"]
        yield from slot["hint"]

    def _draw_words(self, snap: dict, now: float) -> None:
        words = snap.get("words") or []
        gy = snap["ground_y"]
        n = 0
        for wd in words:
            if not isinstance(wd, dict):
                continue
            slot = self._pool_get(self.word_pool, self._new_word_slot, n)
            n += 1
            text = str(wd.get("text") or "")
            try:
                typed = max(0, min(len(text), int(wd.get("typed") or 0)))
            except (TypeError, ValueError):
                typed = 0
            wx, wy = self._fnum(wd.get("x")), self._fnum(wd.get("y"))
            kind = wd.get("kind") or "wipe"
            edge, tcol, mark = WORD_STYLE.get(kind, WORD_STYLE["wipe"])
            head, tail = text[:typed], text[typed:]
            w_head = self._measure(head, WORD_SIZE) if head else 0
            w_tail = self._measure(tail, WORD_SIZE) if tail else 0
            pad, mark_w, hh = 10, 16, 14                                   # hh = 알약 반높이
            total = w_head + w_tail + pad * 2 + mark_w
            x0, x1 = wx - total / 2.0, wx + total / 2.0
            # 알약: 양 끝 타원 + 가운데 사각 + 위아래 테두리선
            self.cv.coords(slot["capL"], x0, wy - hh, x0 + 2 * hh, wy + hh)
            self.cv.coords(slot["capR"], x1 - 2 * hh, wy - hh, x1, wy + hh)
            self.cv.coords(slot["body"], x0 + hh, wy - hh, x1 - hh, wy + hh)
            self.cv.coords(slot["top"], x0 + hh, wy - hh, x1 - hh, wy - hh)
            self.cv.coords(slot["bot"], x0 + hh, wy + hh, x1 - hh, wy + hh)
            gear = kind == "gear"
            ecol = edge if not gear else ("#fff5cc" if int(now * 6) % 2 else edge)
            for k in ("capL", "capR"):
                self.cv.itemconfig(slot[k], outline=ecol, width=2 if gear else 1, state="normal")
            for k in ("top", "bot"):
                self.cv.itemconfig(slot[k], fill=ecol, width=2 if gear else 1, state="normal")
            self._show(slot["body"])
            # 표식 (× ₩ ♥ ✦) 알약 왼쪽 안
            self._set_text2(slot["mark"], x0 + pad + 4, wy, mark, fill=edge)
            for it in slot["mark"]:
                self._show(it)
            tx = x0 + pad + mark_w
            # 입력한 앞부분 (청록) + 나머지 (흰/금색)
            self._set_text2(slot["typed"], tx, wy, head, fill=WORD_TYPED)
            rest_col = tcol
            if gear:
                rest_col = "#fff5cc" if int(now * 8) % 2 == 0 else tcol       # 금색 반짝임
            self._set_text2(slot["rest"], tx + w_head, wy, tail, fill=rest_col)
            for it in slot["typed"] + slot["rest"]:
                self._show(it)
            # 착지 안내선: 알약 아래 → 바닥 (점선)
            self.cv.coords(slot["guide"], wx, wy + hh + 2, wx, gy)
            self.cv.itemconfig(slot["guide"], fill=_dim_color(edge, 0.7), state="normal")
            # gear: 알약 주위를 도는 ✦ 4개
            for j, sp in enumerate(slot["sparks"]):
                if not gear:
                    self._hide(sp)
                    continue
                a = now * 2.2 + j * math.pi / 2.0
                sx = wx + math.cos(a) * (total / 2.0 + 8)
                sy = wy + math.sin(a) * (hh + 6)
                self.cv.coords(sp, sx, sy)
                self.cv.itemconfig(sp, fill="#fff5cc" if (j + int(now * 5)) % 2 else edge, state="normal")
            # 처음 1.5초: "타이핑!" 힌트
            wt = self._fnum(wd.get("t"))
            if wt < WORD_HINT_T and typed == 0:
                self._set_text2(slot["hint"], wx, wy + hh + 3, "타이핑!", fill="#fff5cc" if int(now * 4) % 2 else edge)
                for it in slot["hint"]:
                    self._show(it)
            else:
                for it in slot["hint"]:
                    self._hide(it)
            for it in self._word_slot_items(slot):
                self.cv.tag_raise(it)
        for slot in self.word_pool[n:]:
            for it in self._word_slot_items(slot):
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
            self.hud_items["money"] = self._text2(0, 0, "", size=10, anchor="nw", fill=MONEY_FG)   # v1.9
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
            right += 2 + self._measure(" · %s" % ename, 10)
        else:
            for it in self.hud_items["elem"]:
                self._hide(it)
        # v1.9: 돈 "₩ 12,340" (금색) — 점수 줄 끝에
        if hud.get("money") is not None:
            mtxt = "  " + self._money_text(hud.get("money"))
            self._set_text2(self.hud_items["money"], right + 2, 8, mtxt, fill=MONEY_FG)
            for it in self.hud_items["money"]:
                self._show(it)
            right += 2 + self._measure(mtxt, 10)
        else:
            for it in self.hud_items["money"]:
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
        self._draw_inventory(snap)

    # --- v1.9 인벤토리 바 (오른쪽 위, 보스 HP 바 아래) + 슬로우 비네트
    def _inv_all_items(self):
        ui = self.inv_ui
        for sl in ui["slots"]:
            yield sl["box"]
            yield sl["num"]
            yield from sl["glyph"]
            yield sl["label"]
            yield sl["count"]
        yield ui["slow_top"]
        yield ui["slow_bot"]
        yield from ui["slow_txt"]

    def _draw_inventory(self, snap):
        hud = snap.get("hud") or {}
        if not self.inv_ui:
            slots = []
            for _ in range(INV_SLOTS):
                slots.append({
                    "box": self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=1),
                    "num": self.cv.create_text(0, 0, text="", font=(FONT, 7, "normal"), fill=LOCKED_FG, anchor="nw"),
                    "glyph": self._text2(0, 0, "", size=13, anchor="center"),
                    "label": self.cv.create_text(0, 0, text="", font=(FONT, 7, "normal"), fill="#c7d2e0", anchor="s"),
                    "count": self.cv.create_text(0, 0, text="", font=(FONT, 8, "bold"), fill=MONEY_FG, anchor="ne"),
                })
            self.inv_ui = {
                "slots": slots,
                "slow_top": self.cv.create_rectangle(0, 0, 0, 0, fill=SLOW_FG, outline=""),
                "slow_bot": self.cv.create_rectangle(0, 0, 0, 0, fill=SLOW_FG, outline=""),
                "slow_txt": self._text2(0, 0, "", size=11, anchor="n", fill=SLOW_FG),
            }
        ui = self.inv_ui
        if (snap.get("state") in ("town", "shop") or hud.get("shop") or hud.get("town")
                or hud.get("inventory") is None):        # 구 스냅샷(인벤토리 없음)에서는 바 자체를 숨긴다
            for it in self._inv_all_items():          # 패널 화면에서는 오른쪽 위 바를 숨긴다 (돈은 패널에 표시)
                self._hide(it)
            return
        now = time.perf_counter()
        inv = hud.get("inventory")
        if not isinstance(inv, list):
            inv = []
        flash = hud.get("inv_flash")
        x1 = self.W - 16
        x0 = x1 - INV_SLOTS * INV_SLOT - (INV_SLOTS - 1) * INV_GAP
        y0 = 28
        for i, sl in enumerate(ui["slots"]):
            sx = x0 + i * (INV_SLOT + INV_GAP)
            ent = inv[i] if i < len(inv) else None
            kind = ent.get("kind") if isinstance(ent, dict) else None
            try:
                cnt = int(ent.get("count", 1) or 1) if isinstance(ent, dict) else 0
            except (TypeError, ValueError):
                cnt = 1
            self.cv.coords(sl["box"], sx, y0, sx + INV_SLOT, y0 + INV_SLOT)
            if flash == i:
                pulse = 0.5 + 0.5 * math.sin(now * 18.0)
                self.cv.itemconfig(sl["box"], outline=_lerp_color(MONEY_FG, "#fff5cc", pulse), width=3, state="normal")
            else:
                self.cv.itemconfig(sl["box"], outline=HUD_EDGE if kind else _dim_color(HUD_EDGE, 0.7), width=1, state="normal")
            self.cv.coords(sl["num"], sx + 3, y0 + 1)
            self.cv.itemconfig(sl["num"], text=str(i + 1), state="normal")
            if kind:
                glyph, gcol = INV_GLYPH.get(kind, (ITEM_GLYPH.get(kind, "?"), "#ffd166"))
                self._set_text2(sl["glyph"], sx + INV_SLOT // 2, y0 + 16, glyph, fill=gcol)
                for it in sl["glyph"]:
                    self._show(it)
                self.cv.coords(sl["label"], sx + INV_SLOT // 2, y0 + INV_SLOT - 2)
                self.cv.itemconfig(sl["label"], text=INV_LABEL.get(kind, kind), fill="#c7d2e0", state="normal")
                if cnt > 1:
                    self.cv.coords(sl["count"], sx + INV_SLOT - 3, y0 + 1)
                    self.cv.itemconfig(sl["count"], text="×%d" % cnt, state="normal")
                else:
                    self._hide(sl["count"])
            else:
                for it in sl["glyph"]:
                    self._hide(it)
                self.cv.coords(sl["label"], sx + INV_SLOT // 2, y0 + INV_SLOT // 2 + 6)
                self.cv.itemconfig(sl["label"], text="—", fill=LOCKED_FG, state="normal")
                self._hide(sl["count"])
        # 슬로우(야근 커피): 위아래 가장자리 파란 띠 맥동 + 남은 초
        slow_t = self._fnum(hud.get("slow_t"))
        if slow_t > 0:
            pulse = 0.5 + 0.5 * math.sin(now * 5.0)
            col = _lerp_color(_dim_color(SLOW_FG, 0.5), SLOW_FG, pulse)
            th = 3 + int(2 * pulse)
            self.cv.coords(ui["slow_top"], 0, 0, self.W, th)
            self.cv.coords(ui["slow_bot"], 0, self.H - th, self.W, self.H)
            for k in ("slow_top", "slow_bot"):
                self.cv.itemconfig(ui[k], fill=col, state="normal")
            self._set_text2(ui["slow_txt"], self.W // 2, 6, "슬로우 %d초" % int(math.ceil(slow_t)), fill=_light_color(SLOW_FG, 0.3))
            for it in ui["slow_txt"]:
                self._show(it)
        else:
            self._hide(ui["slow_top"]); self._hide(ui["slow_bot"])
            for it in ui["slow_txt"]:
                self._hide(it)
        for it in self._inv_all_items():
            self.cv.tag_raise(it)

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

    def _new_upgrade_row(self) -> tuple:
        """스탯 강화 카드 한 장: (선택 박스, 라벨, 부제). 상점(_draw_shop)과 마을 스탯 탭이 함께 쓴다."""
        return (self.cv.create_rectangle(0, 0, 0, 0, outline="#ffd166", width=2),
                self._text2(0, 0, "", size=11, anchor="n"),
                self._text2(0, 0, "", size=9, anchor="n", bold=False, fill="#9fc9ff"))

    def _draw_upgrade_rows(self, ui_rows: list, rows: list, sel: int, x_left: int, width: int, cy: int) -> None:
        """rows(기존 shop items 형식)를 x_left 부터 width 안에 한 줄로 그린다. ui_rows 는 _new_upgrade_row 풀
        (부족하면 키움). 선택 카드만 박스, 남는 카드는 숨김. 항목마다 show/hide 를 여기서 끝낸다."""
        while len(ui_rows) < len(rows):          # 항목 수가 늘어도(v1.7: 7개) 풀을 키운다
            ui_rows.append(self._new_upgrade_row())
        cell = (width - 40) // max(1, len(rows))
        # 칸이 좁으면(7개 항목) 라벨 글꼴을 줄인다
        lsize = 11 if cell >= 110 else (10 if cell >= 92 else 9)
        ssize = 9 if cell >= 92 else 8
        for i, (row, (box, label, sub)) in enumerate(zip(rows, ui_rows)):
            if not isinstance(row, dict):
                row = {}
            x = x_left + 20 + cell * i + cell // 2
            self.cv.coords(box, x - cell // 2 + 4, cy - 8, x + cell // 2 - 4, cy + 54)
            self.cv.itemconfig(box, state="normal" if i == sel else "hidden")
            fg = TEXT_FG if row.get("afford") else LOCKED_FG
            for it in label:
                self.cv.itemconfig(it, font=(FONT, lsize, "bold"), state="normal")
            for it in sub:
                self.cv.itemconfig(it, font=(FONT, ssize, "normal"), state="normal")
            self._set_text2(label, x, cy + 2, str(row.get("label", row.get("key", ""))), fill=fg)
            try:
                lv, mx = int(row.get("level", 0) or 0), int(row.get("max", 0) or 0)
            except (TypeError, ValueError):
                lv, mx = 0, 0
            if row.get("key") == "next":
                info = ""
            elif mx <= 0:                                 # v1.7: max 0 = 무제한 → "Lv n" 만
                info = "%s점 · Lv%d" % (format(row.get("cost", 0), ","), lv)
            elif lv >= mx:
                info = "최대 (Lv%d)" % lv
            else:
                info = "%s점 · Lv%d/%d" % (format(row.get("cost", 0), ","), lv, mx)
            self._set_text2(sub, x, cy + 26, info)
        for box, label, sub in ui_rows[len(rows):]:
            self._hide(box)
            for it in label + sub:
                self._hide(it)

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
        cx, cy = self.W // 2, self.H // 2
        pw, ph = min(self.W - 40, 840), min(self.H - 20, 250)
        top, bottom = cy - ph // 2, cy + ph // 2
        self.cv.coords(ui["panel"], cx - pw // 2, top, cx + pw // 2, bottom)
        self._set_text2(ui["title"], cx, top + 10, "상점 — 점수로 강화 (쓴 점수는 기록에서 빠짐)")
        self._set_text2(ui["score"], cx, top + 34, "보유 점수 %s" % format(snap["hud"].get("score", 0), ","))
        # v1.7: 현재 유효 스탯 (상점 포함). shop.stats 우선, 없으면 hud.stats
        stats_txt = self._stats_text(shop.get("stats") or snap["hud"].get("stats"))
        self._set_text2(ui["stats"], cx, top + 56, stats_txt)
        sel = shop.get("index", 0)
        self._draw_upgrade_rows(ui["rows"], rows, sel, cx - pw // 2, pw, cy)
        self._set_text2(ui["msg"], cx, bottom - 26, shop.get("msg") or "")
        self._set_text2(ui["help"], cx, bottom - 8, "← → 선택 · Space 구매 / 다음 스테이지")
        for it in (ui["panel"], *ui["title"], *ui["score"], *ui["stats"], *ui["msg"], *ui["help"]):
            self._show(it)
        for it in self._shop_all_items():
            self.cv.tag_raise(it)                 # 월드 아이템보다 위

    # ------------------------------------------------------------ v1.9 마을 (state == "town")
    TOWN_TAB_KEYS = ("stat", "shop", "store", "gamble")
    TOWN_TAB_LABELS = ("스탯", "상점", "창고", "도박")
    TOWN_HELP = {"stat": "← → 선택 · Enter 구매 · Tab/↑↓ 탭 전환",
                 "shop": "← → 선택 · Enter 구매 · Tab/↑↓ 탭 전환",
                 "store": "Enter 장착/해제 · C 판매 · ↓ 줄 전환",
                 "gamble": "← → 선택 · Enter 실행 · C 판돈 변경 · Tab 탭 전환"}

    def _new_card(self, lines: int, tag: bool, extra: int) -> dict:
        c = {"box": self.cv.create_rectangle(0, 0, 0, 0, fill=CARD_FILL, outline=HUD_EDGE, width=1),
             "sel": self.cv.create_rectangle(0, 0, 0, 0, fill="", outline=CARD_SEL, width=2),
             "extra": [self.cv.create_rectangle(0, 0, 0, 0, fill="", outline="") for _ in range(extra)],
             "tag": self.cv.create_rectangle(0, 0, 0, 0, fill="", outline="") if tag else None,
             "tagtxt": self._text2(0, 0, "", size=8, anchor="center") if tag else None,
             "lines": [self._text2(0, 0, "", size=9, anchor="n") for _ in range(lines)]}
        return c

    def _card_items(self, c: dict):
        yield c["box"]
        yield c["sel"]
        yield from c["extra"]
        if c["tag"] is not None:
            yield c["tag"]
            yield from c["tagtxt"]
        for pair in c["lines"]:
            yield from pair

    def _hide_card(self, c: dict) -> None:
        for it in self._card_items(c):
            self._hide(it)

    def _card_line(self, c: dict, i: int, x, y, text, size=9, fill=TEXT_FG, bold=True, anchor="n") -> None:
        pair = c["lines"][i]
        f = (FONT, int(size), "bold" if bold else "normal")
        for it in pair:
            self.cv.itemconfig(it, font=f, anchor=anchor, state="normal")
        self._set_text2(pair, x, y, text, fill=fill)

    def _card_tag(self, c: dict, cx, y, rarity) -> None:
        """희귀도 태그: 어두운 채움 + 희귀도 색 글자. 유니크는 ✦ 반짝임."""
        col = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
        label = RARITY_LABEL.get(rarity, str(rarity or "일반"))
        if rarity == "unique":
            label = ("✦ %s ✦" if int(time.perf_counter() * 5) % 2 else "· %s ·") % label
        w = self._measure(label, 8) + 12
        self.cv.coords(c["tag"], cx - w / 2, y, cx + w / 2, y + 14)
        self.cv.itemconfig(c["tag"], fill=_dim_color(col, 0.25), outline=_dim_color(col, 0.6), state="normal")
        self._set_text2(c["tagtxt"], cx, y + 7, label, fill=col)
        for it in c["tagtxt"]:
            self._show(it)

    def _fit(self, text: str, size: int, maxw: int) -> str:
        text = str(text)
        if self._measure(text, size) <= maxw:
            return text
        while len(text) > 1 and self._measure(text + "…", size) > maxw:
            text = text[:-1]
        return text + "…"

    @staticmethod
    def _eq_stats_text(eq: dict) -> str:
        st = eq.get("stats") if isinstance(eq, dict) else None
        if not isinstance(st, dict):
            return ""
        return "힘+%s 민+%s 지+%s" % (st.get("str", 0), st.get("agi", 0), st.get("int", 0))

    @staticmethod
    def _eq_price(eq: dict):
        for k in ("price", "buy_price", "cost", "sell_price"):
            v = eq.get(k)
            if v is not None:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    pass
        return None

    def _town_all_items(self):
        ui = self.town_ui
        if not ui:
            return
        yield ui["panel"]
        yield from ui["title"]
        yield from ui["money"]
        for pair, line in ui["tabs"]:
            yield from pair
            yield line
        yield ui["next_box"]
        yield from ui["next_txt"]
        yield from ui["msg"]
        yield from ui["help"]
        yield from ui["stats"]
        yield from ui["score"]
        for box, label, sub in ui["rows"]:
            yield box
            yield from label
            yield from sub
        for c in ui["cards"] + ui["eq"] + ui["grid"]:
            yield from self._card_items(c)
        for g in ui["gamble"]:
            yield g["box"]
            yield from g["title"]
            for pair in g["lines"]:
                yield from pair
            yield g["coin"]
            yield g["coin_hi"]
            yield from g["reels"]
            for pair in g["reeltxt"]:
                yield from pair

    def _draw_town(self, snap):
        hud = snap.get("hud") or {}
        town = hud.get("town") if snap.get("state") == "town" else None
        if not isinstance(town, dict):
            if self.town_ui:
                for it in self._town_all_items():
                    self._hide(it)
            return
        if not self.town_ui:
            self.town_ui = {
                "panel": self.cv.create_rectangle(0, 0, 0, 0, fill=HUD_BG, outline=HUD_EDGE, width=2),
                "title": self._text2(0, 0, "", size=12, anchor="ne"),
                "money": self._text2(0, 0, "", size=11, anchor="ne", fill=MONEY_FG),
                "tabs": [(self._text2(0, 0, "", size=12, anchor="nw"),
                          self.cv.create_line(0, 0, 0, 0, fill=CARD_SEL, width=2)) for _ in range(4)],
                "next_box": self.cv.create_rectangle(0, 0, 0, 0, fill=CARD_FILL, outline=HUD_EDGE, width=2),
                "next_txt": self._text2(0, 0, "", size=11, anchor="center"),
                "msg": self._text2(0, 0, "", size=10, anchor="s", fill="#ffb3b3"),
                "help": self._text2(0, 0, "", size=9, anchor="s", bold=False, fill="#c7d2e0"),
                "stats": self._text2(0, 0, "", size=10, anchor="n", bold=False, fill="#9fc9ff"),
                "score": self._text2(0, 0, "", size=11, anchor="n", fill="#ffd166"),
                "rows": [],
                "cards": [],
                "eq": [],
                "grid": [],
                "gamble": [],
            }
        ui = self.town_ui
        now = time.perf_counter()
        cx, cy = self.W // 2, self.H // 2
        pw, ph = min(self.W - 40, 1180), min(self.H - 20, 250)
        left, top = cx - pw // 2, cy - ph // 2
        right, bottom = cx + pw // 2, cy + ph // 2
        self.cv.coords(ui["panel"], left, top, right, bottom)
        self._show(ui["panel"])
        # 탭 줄
        tab_key = town.get("tab") if town.get("tab") in self.TOWN_TAB_KEYS else "stat"
        tabs = town.get("tabs") if isinstance(town.get("tabs"), list) else []
        tx = left + 16
        ty = top + 6
        for j, (pair, line) in enumerate(ui["tabs"]):
            label = str(tabs[j]) if j < len(tabs) else self.TOWN_TAB_LABELS[j]
            active = self.TOWN_TAB_KEYS[j] == tab_key
            self._set_text2(pair, tx, ty, label, fill=TEXT_FG if active else LOCKED_FG)
            for it in pair:
                self._show(it)
            w = self._measure(label, 12)
            if active:
                self.cv.coords(line, tx - 2, ty + 20, tx + w + 2, ty + 20)
                self._show(line)
            else:
                self._hide(line)
            tx += w + 28
        try:
            stage_no = int(town.get("stage") or hud.get("stage_no") or 0)
        except (TypeError, ValueError):
            stage_no = 0
        # 오른쪽: 다음 스테이지 버튼 + 돈 + 제목
        nb_w = 132
        nb_x1 = right - 16
        nb_x0 = nb_x1 - nb_w
        self.cv.coords(ui["next_box"], nb_x0, top + 6, nb_x1, top + 30)
        self._set_text2(ui["next_txt"], (nb_x0 + nb_x1) // 2, top + 18, "다음 스테이지 ▶")
        self._set_text2(ui["money"], nb_x0 - 14, top + 8, self._money_text(hud.get("money")))
        self._set_text2(ui["title"], nb_x0 - 14 - self._measure(self._money_text(hud.get("money")), 11) - 14, top + 9,
                        "마을 · %d 스테이지 클리어" % stage_no if stage_no else "마을")
        for it in (ui["next_box"], *ui["next_txt"], *ui["money"], *ui["title"]):
            self._show(it)
        try:
            index = int(town.get("index") or 0)
        except (TypeError, ValueError):
            index = 0
        cy0, cy1 = top + 38, bottom - 40                     # 탭 내용 영역 (아래 msg/help 두 줄 여유)
        # 탭별 내용 — 안 쓰는 탭의 항목은 숨긴다
        n_items = 0
        if tab_key == "stat":
            n_items = self._town_stat(ui, town, hud, index, left, right, cy0, cy1)
        else:
            for box, label, sub in ui["rows"]:
                self._hide(box)
                for it in label + sub:
                    self._hide(it)
            for it in ui["stats"] + ui["score"]:
                self._hide(it)
        if tab_key == "shop":
            n_items = self._town_shop(ui, town, index, left, right, cy0, cy1, now)
        else:
            for c in ui["cards"]:
                self._hide_card(c)
        if tab_key == "store":
            n_items = self._town_store(ui, town, index, left, right, cy0, cy1)
        else:
            for c in ui["eq"] + ui["grid"]:
                self._hide_card(c)
        if tab_key == "gamble":
            n_items = self._town_gamble(ui, town, index, left, right, cy0, cy1, now)
        else:
            for g in ui["gamble"]:
                self._hide_gamble(g)
        # 마지막 항목 = 다음 스테이지 버튼
        on_next = index >= n_items
        pulse = 0.5 + 0.5 * math.sin(now * 6.0)
        self.cv.itemconfig(ui["next_box"], outline=_lerp_color(CARD_SEL, "#fff5cc", pulse) if on_next else HUD_EDGE,
                           fill=_dim_color(CARD_SEL, 0.3) if on_next else CARD_FILL, width=2)
        self.cv.itemconfig(ui["next_txt"][1], fill=CARD_SEL if on_next else "#c7d2e0")
        self._set_text2(ui["msg"], cx, bottom - 20, str(town.get("msg") or ""))
        self._set_text2(ui["help"], cx, bottom - 5, self.TOWN_HELP.get(tab_key, ""))
        for it in ui["msg"] + ui["help"]:
            self._show(it)
        for it in self._town_all_items():
            self.cv.tag_raise(it)                 # 월드 아이템보다 위

    def _town_stat(self, ui, town, hud, index, left, right, cy0, cy1) -> int:
        stat = town.get("stat") if isinstance(town.get("stat"), dict) else {}
        rows = list(stat.get("items") or [])
        if rows and isinstance(rows[-1], dict) and rows[-1].get("key") == "next":
            rows = rows[:-1]                                  # 마지막 "다음 스테이지" 는 오른쪽 버튼으로
        cx = (left + right) // 2
        self._set_text2(ui["score"], cx, cy0, "보유 점수 %s" % format(hud.get("score", 0) or 0, ","))
        self._set_text2(ui["stats"], cx, cy0 + 20, self._stats_text(stat.get("stats") or hud.get("stats")))
        for it in ui["score"] + ui["stats"]:
            self._show(it)
        self._draw_upgrade_rows(ui["rows"], rows, index, left, right - left, (cy0 + cy1) // 2 - 10)
        return len(rows)

    def _draw_giftbox(self, c: dict, cx, y, size, now) -> None:
        """랜덤박스: 보라 상자 + 금색 리본 십자 + 뚜껑, 위에 '?' (extra 사각형 3개 + 글줄 1개)."""
        hw = size / 2.0
        bob = 1.5 * math.sin(now * 4.0)
        r0, r1, r2 = c["extra"][0], c["extra"][1], c["extra"][2]
        self.cv.coords(r0, cx - hw, y + 8 + bob, cx + hw, y + size + bob)
        self.cv.itemconfig(r0, fill="#7c3aed", outline=TEXT_SHADOW, state="normal")
        self.cv.coords(r1, cx - hw - 3, y + bob, cx + hw + 3, y + 10 + bob)            # 뚜껑
        self.cv.itemconfig(r1, fill="#a78bfa", outline=TEXT_SHADOW, state="normal")
        self.cv.coords(r2, cx - 3, y + bob, cx + 3, y + size + bob)                    # 리본(세로)
        self.cv.itemconfig(r2, fill=CARD_SEL, outline="", state="normal")

    def _town_shop(self, ui, town, index, left, right, cy0, cy1, now) -> int:
        shop = town.get("shop") if isinstance(town.get("shop"), dict) else {}
        stock = list(shop.get("stock") or [])
        afford = shop.get("afford") if isinstance(shop.get("afford"), list) else []
        n = len(stock)
        while len(ui["cards"]) < n:
            ui["cards"].append(self._new_card(lines=7, tag=True, extra=3))
        cell = (right - left - 32) // max(1, n)
        y0, y1 = cy0 + 2, cy1 - 4
        for i, eq in enumerate(stock):
            c = ui["cards"][i]
            x = left + 16 + cell * i + cell // 2
            bx0, bx1 = x - cell // 2 + 3, x + cell // 2 - 3
            selected = i == index
            self.cv.coords(c["box"], bx0, y0, bx1, y1)
            self.cv.itemconfig(c["box"], outline=HUD_EDGE, fill=_light_color(CARD_FILL, 0.06) if selected else CARD_FILL,
                               state="normal")
            if selected:
                self.cv.coords(c["sel"], bx0 - 2, y0 - 4, bx1 + 2, y1 + 2)   # 살짝 떠 보이게
                self._show(c["sel"])
            else:
                self._hide(c["sel"])
            ok = bool(afford[i]) if i < len(afford) else True
            eq = eq if isinstance(eq, dict) else {}
            price = self._eq_price(eq)
            price_txt = self._money_text(price) if price is not None else ""
            price_col = MONEY_FG if ok else _dim_color("#ff5252", 0.75)
            maxw = cell - 14
            if eq.get("kind") == "box":
                for it in c["tagtxt"]:
                    self._hide(it)
                self._hide(c["tag"])
                self._card_line(c, 0, x, y0 + 6, "랜덤박스", size=8, fill=LOCKED_FG, bold=False)
                self._draw_giftbox(c, x, y0 + 24, min(40, cell - 30), now)
                self._card_line(c, 1, x, y0 + 30 + min(40, cell - 30) * 0.35, "?", size=16, fill="#fff5cc")
                self._card_line(c, 2, x, y0 + 84, "무엇이 나올까", size=8, fill="#c7d2e0", bold=False)
                self._card_line(c, 3, x, y0 + 100, price_txt, size=9, fill=price_col)
                self._card_line(c, 4, x, y0 + 118, "장비·아이템·돈", size=8, fill=LOCKED_FG, bold=False)
                for k in (5, 6):
                    self._card_line(c, k, x, y0, "", size=8)
                continue
            for it in c["extra"]:
                self._hide(it)
            rarity = eq.get("rarity") or "normal"
            rcol = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
            slot = eq.get("slot")
            self._card_line(c, 0, x, y0 + 6, SLOT_LABEL.get(slot, str(slot or "")), size=8, fill=LOCKED_FG, bold=False)
            self._card_line(c, 1, x, y0 + 20, self._fit(eq.get("name") or "?", 9, maxw), size=9,
                            fill=TEXT_FG if ok else "#c7d2e0")
            self._card_tag(c, x, y0 + 40, rarity)
            try:
                lv = int(eq.get("level", 0) or 0)
            except (TypeError, ValueError):
                lv = 0
            self._card_line(c, 2, x, y0 + 60, "Lv %d" % lv, size=9, fill=rcol)
            self._card_line(c, 3, x, y0 + 80, price_txt, size=10, fill=price_col)
            st = eq.get("stats") if isinstance(eq.get("stats"), dict) else {}
            for k, (skey, sname) in enumerate((("str", "힘"), ("agi", "민"), ("int", "지"))):
                try:
                    v = int(st.get(skey, 0) or 0)
                except (TypeError, ValueError):
                    v = 0
                self._card_line(c, 4 + k, x, y0 + 104 + 15 * k, "%s +%d" % (sname, v), size=8,
                                fill="#c7d2e0" if v > 0 else LOCKED_FG, bold=False)
        for c in ui["cards"][n:]:
            self._hide_card(c)
        return n

    def _town_store(self, ui, town, index, left, right, cy0, cy1) -> int:
        store = town.get("store") if isinstance(town.get("store"), dict) else {}
        equipped = store.get("equipped") if isinstance(store.get("equipped"), dict) else {}
        items = list(store.get("items") or [])
        mode = store.get("mode") or "list"
        while len(ui["eq"]) < len(SLOT_ORDER):
            ui["eq"].append(self._new_card(lines=3, tag=False, extra=0))
        while len(ui["grid"]) < 24:
            ui["grid"].append(self._new_card(lines=2, tag=False, extra=0))
        inner = right - left - 32
        # 위: 장착 6칸
        cell = inner // len(SLOT_ORDER)
        ey0, ey1 = cy0 + 2, cy0 + 60
        row_on = mode == "equipped"
        for j, slot in enumerate(SLOT_ORDER):
            c = ui["eq"][j]
            x = left + 16 + cell * j + cell // 2
            bx0, bx1 = x - cell // 2 + 3, x + cell // 2 - 3
            self.cv.coords(c["box"], bx0, ey0, bx1, ey1)
            self.cv.itemconfig(c["box"], outline=_light_color(HUD_EDGE, 0.25) if row_on else _dim_color(HUD_EDGE, 0.7),
                               fill=CARD_FILL, state="normal")
            if row_on and j == index:
                self.cv.coords(c["sel"], bx0 - 2, ey0 - 2, bx1 + 2, ey1 + 2)
                self._show(c["sel"])
            else:
                self._hide(c["sel"])
            eq = equipped.get(slot)
            self._card_line(c, 0, x, ey0 + 4, SLOT_LABEL.get(slot, slot), size=8, fill=LOCKED_FG, bold=False)
            if isinstance(eq, dict):
                rarity = eq.get("rarity") or "normal"
                rcol = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
                self._card_line(c, 1, x, ey0 + 18, self._fit(eq.get("name") or "?", 9, cell - 14), size=9, fill=TEXT_FG)
                self._card_line(c, 2, x, ey0 + 36, "%s · Lv %s" % (RARITY_LABEL.get(rarity, rarity), eq.get("level", 0)),
                                size=8, fill=rcol, bold=False)
            else:
                self._card_line(c, 1, x, ey0 + 22, "—", size=11, fill=LOCKED_FG)
                self._card_line(c, 2, x, ey0 + 40, "", size=8)
        # 아래: 창고 12×2
        gcell = inner // 12
        gh = 40
        gy0 = ey1 + 10
        list_on = mode != "equipped"
        for k, c in enumerate(ui["grid"]):
            col, row = k % 12, k // 12
            x = left + 16 + gcell * col + gcell // 2
            y = gy0 + row * (gh + 6)
            bx0, bx1 = x - gcell // 2 + 2, x + gcell // 2 - 2
            self.cv.coords(c["box"], bx0, y, bx1, y + gh)
            eq = items[k] if k < len(items) else None
            self.cv.itemconfig(c["box"], outline=_light_color(HUD_EDGE, 0.25) if list_on else _dim_color(HUD_EDGE, 0.7),
                               fill=CARD_FILL if isinstance(eq, dict) else _dim_color(CARD_FILL, 0.8), state="normal")
            if list_on and k == index:
                self.cv.coords(c["sel"], bx0 - 2, y - 2, bx1 + 2, y + gh + 2)
                self._show(c["sel"])
            else:
                self._hide(c["sel"])
            if isinstance(eq, dict):
                rarity = eq.get("rarity") or "normal"
                rcol = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
                self._card_line(c, 0, x, y + 4, self._fit(eq.get("name") or "?", 8, gcell - 10), size=8, fill=rcol)
                self._card_line(c, 1, x, y + 21, "%s Lv%s" % (SLOT_LABEL.get(eq.get("slot"), "")[:3], eq.get("level", 0)),
                                size=8, fill="#c7d2e0", bold=False)
            else:
                self._card_line(c, 0, x, y + 12, "—", size=9, fill=_dim_color(LOCKED_FG, 0.8))
                self._card_line(c, 1, x, y + 24, "", size=8)
        return len(SLOT_ORDER) if row_on else len(items)

    def _new_gamble_panel(self) -> dict:
        return {"box": self.cv.create_rectangle(0, 0, 0, 0, fill=CARD_FILL, outline=HUD_EDGE, width=1),
                "title": self._text2(0, 0, "", size=11, anchor="n"),
                "lines": [self._text2(0, 0, "", size=9, anchor="n") for _ in range(5)],
                "coin": self.cv.create_oval(0, 0, 0, 0, fill=COIN_FILL, outline=COIN_EDGE, width=2),
                "coin_hi": self.cv.create_oval(0, 0, 0, 0, fill="#fff5cc", outline=""),
                "reels": [self.cv.create_rectangle(0, 0, 0, 0, fill=WORD_BG, outline=HUD_EDGE, width=2) for _ in range(3)],
                "reeltxt": [self._text2(0, 0, "", size=20, anchor="center") for _ in range(3)]}

    def _hide_gamble(self, g: dict) -> None:
        self._hide(g["box"]); self._hide(g["coin"]); self._hide(g["coin_hi"])
        for it in g["title"]:
            self._hide(it)
        for pair in g["lines"] + g["reeltxt"]:
            for it in pair:
                self._hide(it)
        for it in g["reels"]:
            self._hide(it)

    def _gamble_line(self, g: dict, i: int, x, y, text, size=9, fill=TEXT_FG, bold=True) -> None:
        pair = g["lines"][i]
        f = (FONT, int(size), "bold" if bold else "normal")
        for it in pair:
            self.cv.itemconfig(it, font=f, state="normal")
        self._set_text2(pair, x, y, text, fill=fill)

    def _town_gamble(self, ui, town, index, left, right, cy0, cy1, now) -> int:
        gm = town.get("gamble") if isinstance(town.get("gamble"), dict) else {}
        games = gm.get("games") if isinstance(gm.get("games"), list) else ["강화 도박", "더블업", "슬롯"]
        n = 3
        while len(ui["gamble"]) < n:
            ui["gamble"].append(self._new_gamble_panel())
        try:
            active = int(gm.get("game") if gm.get("game") is not None else index)
        except (TypeError, ValueError):
            active = 0
        if index < n:
            active = index
        inner = right - left - 32
        cell = inner // n
        y0, y1 = cy0 + 2, cy1 - 4
        reels = gm.get("reels") if isinstance(gm.get("reels"), list) else None
        stake = gm.get("stake")
        try:
            streak = int(gm.get("streak") or 0)
        except (TypeError, ValueError):
            streak = 0
        for i in range(n):
            g = ui["gamble"][i]
            x = left + 16 + cell * i + cell // 2
            bx0, bx1 = x - cell // 2 + 4, x + cell // 2 - 4
            is_on = i == active
            self.cv.coords(g["box"], bx0, y0, bx1, y1)
            self.cv.itemconfig(g["box"], outline=CARD_SEL if is_on else HUD_EDGE, width=2 if is_on else 1,
                               fill=_light_color(CARD_FILL, 0.06) if is_on else CARD_FILL, state="normal")
            title = str(games[i]) if i < len(games) else ("강화 도박", "더블업", "슬롯")[i]
            self._set_text2(g["title"], x, y0 + 6, ("◆ %s" % title) if is_on else title, fill=CARD_SEL if is_on else "#c7d2e0")
            for it in g["title"]:
                self._show(it)
            # 기본: 코인/릴 숨김, 글줄 5개 비움
            self._hide(g["coin"]); self._hide(g["coin_hi"])
            for it in g["reels"]:
                self._hide(it)
            for pair in g["lines"] + g["reeltxt"]:
                for it in pair:
                    self._hide(it)
            if i == 0:
                # 강화 도박: 대상 장비 카드(글줄) + 확률표
                target = gm.get("target")
                items = ((town.get("store") or {}).get("items") if isinstance(town.get("store"), dict) else None) or []
                eq = None
                if isinstance(target, dict):
                    eq = target
                elif isinstance(target, int) and 0 <= target < len(items):
                    eq = items[target]
                if isinstance(eq, dict):
                    rarity = eq.get("rarity") or "normal"
                    rcol = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
                    self._gamble_line(g, 0, x, y0 + 30, self._fit(eq.get("name") or "?", 10, cell - 30), size=10, fill=TEXT_FG)
                    self._gamble_line(g, 1, x, y0 + 50, "%s · %s · Lv %s" % (SLOT_LABEL.get(eq.get("slot"), eq.get("slot", "")),
                                                                            RARITY_LABEL.get(rarity, rarity), eq.get("level", 0)),
                                      size=9, fill=rcol, bold=False)
                    cost = self._eq_price({"price": gm.get("cost")}) if gm.get("cost") is not None else None
                    self._gamble_line(g, 2, x, y0 + 70, ("비용 " + self._money_text(cost)) if cost is not None else "", size=9, fill=MONEY_FG)
                else:
                    self._gamble_line(g, 0, x, y0 + 34, "대상 장비 없음", size=10, fill=LOCKED_FG)
                    self._gamble_line(g, 1, x, y0 + 54, "창고에 장비를 넣어 두세요", size=8, fill=LOCKED_FG, bold=False)
                self._gamble_line(g, 3, x, y0 + 96, "60% ↑2   /   30% –   /   10% ↓3", size=10, fill="#c7d2e0")
                self._gamble_line(g, 4, x, y0 + 118, "강화 레벨을 걸고 주사위를 굴린다", size=8, fill=LOCKED_FG, bold=False)
            elif i == 1:
                # 더블업: 판돈 · 연속 ×N · 뒤집히는 코인
                self._gamble_line(g, 0, x - 60, y0 + 34, "판돈", size=9, fill=LOCKED_FG, bold=False)
                self._gamble_line(g, 1, x - 60, y0 + 50, self._money_text(stake) if stake is not None else "₩ —", size=11, fill=MONEY_FG)
                self._gamble_line(g, 2, x - 60, y0 + 76, "연속", size=9, fill=LOCKED_FG, bold=False)
                self._gamble_line(g, 3, x - 60, y0 + 92, "×%d" % max(1, 2 ** min(streak, 3)), size=16, fill="#fff5cc" if streak else "#c7d2e0")
                self._gamble_line(g, 4, x, y0 + 124, "50% 로 두 배 · 연속 성공 최대 ×8", size=8, fill=LOCKED_FG, bold=False)
                ccx, ccy = x + 50, y0 + 74
                squash = abs(math.cos(now * 6.0)) if reels is None else 1.0
                rw = 6 + 18 * squash
                self.cv.coords(g["coin"], ccx - rw, ccy - 24, ccx + rw, ccy + 24)
                self._show(g["coin"])
                if squash > 0.5:
                    self.cv.coords(g["coin_hi"], ccx - rw * 0.35, ccy - 14, ccx + rw * 0.15, ccy - 4)
                    self._show(g["coin_hi"])
            else:
                # 슬롯: 릴 3개 (None 이면 돌아가는 반짝임) + 배당 문구
                for j in range(3):
                    rx = x + (j - 1) * 52
                    ry = y0 + 52
                    self.cv.coords(g["reels"][j], rx - 22, ry - 22, rx + 22, ry + 22)
                    spinning = reels is None or j >= len(reels)
                    self.cv.itemconfig(g["reels"][j], outline=_lerp_color(HUD_EDGE, CARD_SEL, 0.5 + 0.5 * math.sin(now * 10 + j))
                                       if spinning else HUD_EDGE, state="normal")
                    if spinning:
                        sym = SLOT_SYMBOLS[int(now * 14 + j * 2) % len(SLOT_SYMBOLS)]
                        col = _dim_color("#c7d2e0", 0.6 if int(now * 28 + j) % 2 else 0.9)
                    else:
                        sym = str(reels[j])
                        col = {"7": "#ff5252", "★": CARD_SEL, "₩": "#4ade80", "◆": "#4cc9f0", "♥": "#ff6b6b"}.get(sym, TEXT_FG)
                    self._set_text2(g["reeltxt"][j], rx, ry, sym, fill=col)
                    for it in g["reeltxt"][j]:
                        self._show(it)
                pay = gm.get("text") or gm.get("payout_text") or ""
                if not pay and gm.get("payout") is not None:
                    pay = "배당 " + self._money_text(gm.get("payout"))
                self._gamble_line(g, 0, x, y0 + 84, str(pay), size=10, fill=MONEY_FG if pay else LOCKED_FG)
                self._gamble_line(g, 1, x, y0 + 104, "777 잭팟 ×30 + 유니크 · ★★★ 레어 · ₩₩₩ ×10", size=8, fill="#c7d2e0", bold=False)
                self._gamble_line(g, 2, x, y0 + 118, "판돈 %s" % (self._money_text(stake) if stake is not None else "—"), size=8, fill=LOCKED_FG, bold=False)
        for g in ui["gamble"][n:]:
            self._hide_gamble(g)
        return n


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
        try:                                   # v2.0 궁극 스킬 사진 사다리 (팀 없음). 에셋이 없어도 기동은 계속
            self.bank.preload_ult(list(CHAR_KEYS))
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
        self._write_balance_log()

    def _write_balance_log(self) -> None:
        """v1.9: 스테이지 종료(클리어/게임 오버) 기록을 세이브 파일 옆 balance_log.jsonl 에 한 줄씩 덧붙인다."""
        drain = getattr(self.world, "drain_log", None)
        if drain is None:
            return
        try:
            recs = drain()
            if not recs:
                return
            path = os.path.join(os.path.dirname(self.save_path), self.config.get("balance_log", "balance_log.jsonl"))
            with open(path, "a", encoding="utf-8") as f:
                for rec in recs:
                    rec = dict(rec)
                    rec["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    rec["version"] = VERSION
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
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
            elif snap["state"] in ("shop", "town", "game_over") and getattr(self.world, "balance_log", None):
                self._write_balance_log()       # 스테이지가 끝난 직후 바로 기록
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
