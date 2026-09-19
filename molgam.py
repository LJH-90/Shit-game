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
import re
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


# config_version 이 오르면(새 exe 동봉본 > exe 옆 파일) 이 블록들은 동봉본을 따른다 (updater.reset_blocks: 숫자·불·리스트 덮어쓰기,
# name/title/label 같은 사용자 문구와 파일에만 있는 키는 유지). 업데이터는 exe 만 바꾸므로 exe 옆 stages.json 이 v1.x 수치
# (적 HP 1/3, 몬스터 없음)로 남던 문제 — v2.1 부터 stages.json 도 config_version 을 갖는다.
DATA_RESET_BLOCKS = {
    "config.json": ("equipment", "characters"),
    "stages.json": ("_comment", "_comment_difficulty", "departments", "executive_stages", "ranks", "difficulty", "curve",
                    "wave", "progression", "final_bosses", "mid_bosses", "monsters_from_stage"),
}


def _config_version(d) -> int:
    try:
        return int((d or {}).get("config_version", 1) or 1)
    except (TypeError, ValueError, AttributeError):
        return 1


def load_config_file(name: str):
    """exe 옆 파일을 우선 쓰되, 새 버전 exe 에 동봉된 파일에만 있는 키는 채워 넣고 저장한다.
    (업데이트 후에도 사용자가 바꾼 핫키·이름은 그대로, 새 캐릭터·설정 키는 추가)
    v2.0: 동봉본의 "config_version" 이 더 크면 DATA_RESET_BLOCKS[name] 블록은 동봉본을 따른다 — merge_missing 은 키만
    채우므로 v1.6 config.json 의 레거시 장비 수치, v1.x stages.json 의 적 HP(1/3)·몬스터 목록이 그대로 남던 문제."""
    ext = os.path.join(base_dir(), name)
    bun = os.path.join(bundled_dir(), name)
    if os.path.abspath(ext) == os.path.abspath(bun) or not (os.path.isfile(ext) and os.path.isfile(bun)):
        return load_json(name)
    with open(ext, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(bun, "r", encoding="utf-8") as f:
        bundled = json.load(f)
    if not (isinstance(data, dict) and isinstance(bundled, dict)):
        return data
    old_ver = _config_version(data)            # merge_missing 이 config_version 키를 채우기 전에 읽는다
    changed = updater.merge_missing(data, bundled)
    if old_ver < _config_version(bundled):
        updater.reset_blocks(data, bundled, DATA_RESET_BLOCKS.get(name, ()))
        data["config_version"] = bundled["config_version"]
        changed = True
    if changed:
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
try:                                 # v2.0: 현재 캐릭터가 못 쓰는 특전 라벨 꼬리표 (마을 카드/비교표에서 흐리게)
    from game import PERK_OFF_SUFFIX  # noqa: E402
except ImportError:
    PERK_OFF_SUFFIX = " (미적용)"
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
EB_CORE, EB_RING, EB_GLINT, EB_GHOST = "#ff3b3b", "#1b0f12", "#fff1c9", "#ff7a70"   # v2.0 적탄: 핵 / 테 / 하이라이트 / 잔상
EB_TRAIL_LEN = 12.0                                  # 잔상 간격(px) ≈ 30 fps 한 프레임 이동량(320 px/s)
EB_TRAIL_MAX = 120                                   # 화면 탄 수가 이보다 많으면 잔상 생략
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
COIN_BLINK_T = 3.0                                   # v2.0: 바닥 돈 소멸 전 깜빡임(초, game.COIN_BLINK_T 와 동일)
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
RARITY_COLORS = {"normal": "#c7d2e0", "rare": "#4cc9f0", "unique": "#ff9f43"}   # v2.0 마을: 유니크 = 주황 (금색은 커서·돈 전용)
RARITY_LABEL = {"normal": "일반", "rare": "레어", "unique": "유니크"}
SLOT_LABEL = {"hat": "안전모", "gloves": "작업 장갑", "suit": "사신 정장", "shoes": "운동화",
              "weapon": "사무용 무기", "acc": "사원증"}
SLOT_ORDER = ("hat", "gloves", "suit", "shoes", "weapon", "acc")
SLOT_SYMBOLS = ("₩", "★", "◆", "♥", "7")
# ---- v2.0 마을 화면 (시안 v1 "슬롯 선반") 토큰. 알파 없음: 흐림은 _lerp_color(색, T_PANEL, k) 로 미리 섞고 #010203 은 절대 안 나온다.
T_GROUND, T_PANEL, T_CARD, T_SEL = "#12161f", "#1a1f2b", "#1f2634", "#262e40"
T_EDGE, T_TEXT, T_MUTED, T_GOLD, T_POS, T_NEG = "#3a4558", "#eef2fa", "#8a95a8", "#ffd166", "#4ade80", "#ff6b6b"
T_FLAT = "#1c2230"                                   # 상점 0번 "비교 기준" 카드 (테두리 없음)
T_CELL_EDGE = "#2f3848"                              # 빈 칸 홈 테두리
T_LIP = ("#5a6475", "#3a4558", "#242b39")            # 선반턱: 밝은선 1px / 바 3px / 밑띠 3px
T_LIP_ON = ("#f8dea1", "#ffd166", "#71613b")         # 커서 줄 선반턱 (금색)
SLOT_HUES = {"hat": "#f59e0b", "gloves": "#22c55e", "suit": "#a78bfa", "shoes": "#38bdf8", "weapon": "#ef4444", "acc": "#f472b6"}
SHELF_ORDER = ("hat", "acc", "suit", "gloves", "weapon", "shoes")   # 선반 = 몸 순서 (머리 → 목 → 몸통 → 손 → 총 → 발)
SLOT_EFFECT_KEY = {"hat": "shield", "gloves": "rate", "suit": "magic", "shoes": "speed", "weapon": "damage", "acc": "money"}
EFFECT_LABEL = {"shield": "실드", "rate": "연사", "magic": "마법", "speed": "이동", "damage": "물리", "money": "돈", "jump": "점프"}
PCT_KEYS = ("rate", "speed", "money", "jump")        # 비교표/카드에서 % 로 적는 효과
PCT_LABELS = ("연사", "이동", "돈", "점프")             # 비교표 행에 fmt 가 없을 때 라벨로 % 판정
STAT_LABEL = {"str": "힘", "agi": "민첩", "int": "지혜"}
STAT_SHORT = {"str": "힘", "agi": "민", "int": "지"}
TOWN_STAT_HUES = {"str": "#f87171", "agi": "#4ade80", "int": "#60a5fa", "rate": "#fbbf24", "shield": "#7dd3fc", "life": "#f472b6"}
TOWN_GAMBLE_HUES = ("#f59e0b", "#4ade80", "#a78bfa")
DOLL_DOTS = {"hat": (0.445, 0.20), "acc": (0.41, 0.39), "suit": (0.27, 0.51),     # 인형 위 부위 점 (스프라이트 폭·높이 비율)
             "gloves": (0.55, 0.57), "weapon": (0.80, 0.62), "shoes": (0.35, 0.875)}
TOWN_W, TOWN_H = 1456, 340                           # 시안 패널 폭 / 기준 높이 (넓으면 가운데, 높으면 선반 피치 ↑)
TOWN_CARD_PITCH = 216                                # 선반 카드 한 칸 (208 + 8). 띠가 1528 보다 좁으면 카드 3 → 2 → 1 장으로 줄이고
TOWN_RIGHT_COL = 1200                                # 시안 x ≥ 1200 (비교표·헤더 돈/점수·푸터 카드·"+N")을 그만큼 왼쪽으로 민다
TOWN_LAYOUT_VERSION = 3                              # 바뀌면 town_ui 풀을 다시 만든다


def _grect(x, y, w, h) -> list:
    return [x, y, x + w, y, x + w, y + h, x, y + h]


# 16px 격자 글리프: [(종류, 점)] — "fg" 는 글리프 색, "bg" 는 바탕색으로 뚫는 구멍. 스티커·카드·비교표가 같은 표를 쓴다 (이모지 없음).
TOWN_GLYPHS = {
    "hat": [("fg", [2, 10, 2, 8, 4, 4, 8, 2, 12, 4, 14, 8, 14, 10]), ("fg", _grect(0, 10, 16, 3))],
    "acc": [("fg", [7.5, 0, 8.5, 0, 5.5, 4.5, 4.5, 4.5]), ("fg", [7.5, 0, 8.5, 0, 11.5, 4.5, 10.5, 4.5]),
            ("fg", _grect(4, 4, 8, 11)), ("bg", _grect(7, 5, 2, 1)), ("bg", _grect(6, 8, 4, 4))],
    "suit": [("fg", [1, 4, 6, 1, 8, 4, 10, 1, 15, 4, 15, 8, 13, 8, 13, 15, 3, 15, 3, 8, 1, 8]), ("bg", [7, 4, 9, 4, 9, 9, 8, 11, 7, 9])],
    "gloves": [("fg", [4, 15, 4, 7, 6, 4, 9, 4, 11, 7, 11, 9, 13, 8, 15, 10, 12, 12, 12, 15])],
    "weapon": [("fg", _grect(1, 11, 15, 3)), ("fg", [1, 7, 12, 4, 13, 7, 2, 10]), ("fg", _grect(0, 9, 3, 3))],
    "shoes": [("fg", [1, 14, 1, 10, 3, 10, 5, 5, 9, 5, 10, 9, 15, 11, 15, 14])],
    "box": [("fg", _grect(1, 5, 14, 10)), ("fg", _grect(0, 3, 16, 3)), ("bg", _grect(7, 3, 2, 12)), ("bg", _grect(3, 0, 10, 3))],
    "str": [("fg", _grect(0, 5, 4, 6)), ("fg", _grect(12, 5, 4, 6)), ("fg", _grect(4, 7, 8, 2))],              # 덤벨
    "agi": [("fg", [9, 0, 3, 9, 7, 9, 5, 16, 13, 6, 9, 6, 11, 0])],                                              # 번개
    "int": [("fg", _grect(2, 2, 12, 12)), ("bg", _grect(4, 5, 8, 1)), ("bg", _grect(4, 8, 8, 1)), ("bg", _grect(4, 11, 5, 1))],  # 책
    "rate": [("fg", _grect(1, 3, 6, 2)), ("fg", _grect(4, 7, 6, 2)), ("fg", _grect(7, 11, 6, 2))],             # 탄 3발
    "shield": [("fg", [2, 2, 14, 2, 14, 9, 8, 15, 2, 9])],
    "life": [("fg", [8, 15, 1, 8, 1, 4, 4, 1, 8, 4, 12, 1, 15, 4, 15, 8])],                                     # 하트
    "dice": [("fg", _grect(2, 2, 12, 12)), ("bg", _grect(4, 4, 2, 2)), ("bg", _grect(10, 10, 2, 2)), ("bg", _grect(7, 7, 2, 2))],
    "coin": [("fg", [8, 1, 12, 2, 15, 6, 15, 10, 12, 14, 8, 15, 4, 14, 1, 10, 1, 6, 4, 2]), ("bg", _grect(7, 5, 2, 6))],
    "reel": [("fg", _grect(1, 3, 4, 10)), ("fg", _grect(6, 3, 4, 10)), ("fg", _grect(11, 3, 4, 10))],
}
TOWN_GLYPH_PARTS = 5                                 # 글리프 하나가 쓰는 폴리곤 수 (최대 fg 3 + bg 2)
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
        self.halo_pool: list[int] = []              # v2.0: 스프라이트 적탄 테 2장/탄 — 전용 풀 (공용 fx 풀 순서 보존)
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
        self._fx_shown = dict(self._fx_n)           # 직전 _fx_end 까지 보이던 개수 — 그 뒤 항목은 이미 숨겨져 있다
        self.word_pool: list[dict] = []             # 낙하 타자 단어 알약 슬롯
        self.ally_pool: list[dict] = []             # 아군(분신/드론/찹츄) 슬롯
        self.inv_ui: dict = {}                      # 인벤토리 바 + 돈 + 슬로우 비네트
        self.town_ui: dict = {}                     # 마을 화면
        self._fonts: dict = {}                      # tkinter.font.Font 캐시 (글자 폭 측정)
        self._measured: dict = {}                   # (text, size, bold) -> px (v2.0 마을 화면 폭 캐시)
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
        # [n, shown) 만 숨긴다 — 그 뒤는 지난 프레임에 이미 숨겼다 (탄막 뒤 600개 풀을 매 프레임 다시 숨기지 않게)
        n, shown = self._fx_n, self._fx_shown
        for k, pool in (("poly", self.fx_poly_pool), ("line", self.fx_line_pool),
                        ("oval", self.fx_oval_pool), ("rect", self.fx_rect_pool)):
            for it in pool[n[k]:shown[k]]:
                self.cv.itemconfig(it, state="hidden")
            shown[k] = n[k]
        for pair in self.fx_text_pool[n["text"]:shown["text"]]:
            for it in pair:
                self._hide(it)
        shown["text"] = n["text"]

    def _fx_new(self, it: int) -> int:
        """새 fx 도형은 캔버스 맨 위에 생긴다 → 글자 풀(동전 ₩ · +₩ · 단어)을 다시 그 위로. 풀이 자랄 때만 불려 비용 ≈ 0."""
        for pair in self.fx_text_pool:
            for t in pair:
                self.cv.tag_raise(t)
        return it

    def _poly(self, pts, fill="", outline="", width=1, smooth=True):
        it = self._pool_get(self.fx_poly_pool, lambda: self._fx_new(self.cv.create_polygon(
            0, 0, 0, 0, 0, 0, fill="", outline="", smooth=True, splinesteps=6)), self._fx_n["poly"])
        self._fx_n["poly"] += 1
        if len(pts) < 6:
            pts = list(pts) + [pts[-2] if pts else 0, pts[-1] if pts else 0] * 3
        self.cv.coords(it, *pts)
        self.cv.itemconfig(it, fill=fill, outline=outline, width=width, smooth=smooth, state="normal")
        return it

    def _line(self, pts, fill=TEXT_FG, width=1, dash=None, smooth=False):
        it = self._pool_get(self.fx_line_pool, lambda: self._fx_new(self.cv.create_line(0, 0, 0, 0, fill=TEXT_FG)),
                            self._fx_n["line"])
        self._fx_n["line"] += 1
        self.cv.coords(it, *pts)
        self.cv.itemconfig(it, fill=fill, width=width, dash=dash or (), smooth=smooth, state="normal")
        return it

    def _oval(self, x0, y0, x1, y1, fill="", outline="", width=1, dash=None):
        it = self._pool_get(self.fx_oval_pool, lambda: self._fx_new(self.cv.create_oval(0, 0, 0, 0, fill="", outline="")),
                            self._fx_n["oval"])
        self._fx_n["oval"] += 1
        self.cv.coords(it, x0, y0, x1, y1)
        self.cv.itemconfig(it, fill=fill, outline=outline, width=width, dash=dash or (), state="normal")
        return it

    def _rect(self, x0, y0, x1, y1, fill="", outline="", width=1, dash=None):
        it = self._pool_get(self.fx_rect_pool, lambda: self._fx_new(self.cv.create_rectangle(0, 0, 0, 0, fill="", outline="")),
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
        key = (text, size, bold)
        w = self._measured.get(key)                  # v2.0: 마을 화면이 프레임마다 수백 번 재는 폭 → 캐시 (Tcl 왕복 절약)
        if w is not None:
            return w
        f = self._font(size, bold)
        if f is None:
            w = int(len(text) * abs(size) * 0.9)
        else:
            try:
                w = int(f.measure(text))
            except tk.TclError:
                w = int(len(text) * abs(size) * 0.9)
        if len(self._measured) > 4096:
            self._measured.clear()
        self._measured[key] = w
        return w

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
        if self.town_ui:                          # v2.0: 마을 풀은 캐시를 함께 비운다 (select 전환의 전체 숨김 포함)
            self._town_hide_all()

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
        n_halo = 0
        trail_ok = len(snap["bullets"]) <= EB_TRAIL_MAX     # 탄막이 짙으면 잔상 생략
        for i, b in enumerate(snap["bullets"]):
            it = self._pool_get(self.bullet_pool, lambda: self.cv.create_rectangle(0, 0, 0, 0, outline=""), i)
            # v1.7: sprite 탄(보스 투사체)은 사각형 대신 이미지(중심 앵커). 에셋이 없으면 사각형으로 대체
            im = self._bullet_image(b)
            hw, hh = b["w"] / 2, b["h"] / 2
            if im is not None:
                img_it = self._pool_get(self.bullet_img_pool, lambda: self.cv.create_image(0, 0, anchor="center"), n_img)
                n_img += 1
                if b["owner"] != "player":
                    # v2.0: 스프라이트 적탄 — 어두운 테 + 얇은 금색 안쪽 테를 이미지 아래에 깔아 어떤 배경에서도 보이게.
                    # 전용 halo_pool (생성 때 한 번만 이미지 아래로): 공용 fx 풀 항목을 매 프레임 재정렬하면 풀 순서가 깨진다
                    x_, y_ = float(b["x"]), float(b["y"])
                    for pad, col, wd in ((4, EB_RING, 3), (2, WARN_FAR, 1)):
                        ho = self._pool_get(self.halo_pool, self._new_halo, n_halo)
                        n_halo += 1
                        self.cv.coords(ho, x_ - hw - pad, y_ - hh - pad, x_ + hw + pad, y_ + hh + pad)
                        self.cv.itemconfig(ho, outline=col, width=wd, state="normal")
                self.cv.coords(img_it, int(b["x"]), int(b["y"]))
                self.cv.itemconfig(img_it, image=im, state="normal")
                self._hide(it)
                continue
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
            if b["owner"] != "player":
                # v2.0: 적탄은 사각형 대신 테 두른 핵 + 하이라이트 + 잔상 (히트박스는 그대로)
                self._hide(it)
                self._draw_enemy_bullet(b, hw, hh, trail_ok)
                continue
            self.cv.coords(it, b["x"] - hw, b["y"] - hh, b["x"] + hw, b["y"] + hh)   # x,y = 중심
            if kind == "laser":
                fill = LASER_COLOR
            elif kind == "missile":
                fill = MISSILE_COLOR
            else:
                fill = PLAYER_BULLET
            self.cv.itemconfig(it, fill=fill, state="normal")
        self._pool_hide_from(self.bullet_pool, len(snap["bullets"]))
        self._pool_hide_from(self.bullet_img_pool, n_img)
        self._pool_hide_from(self.halo_pool, n_halo)
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
            if kind == "coin":
                # v2.0: 바닥에 남는 돈 — 금액 자릿수(tier)만큼 커지고 쌓이는 동전 더미 + ₩ + 금액 라벨, 소멸 3초 전 깜빡임
                self._hide(box)
                self._hide(txt)
                if it_t < COIN_BLINK_T and int(it_t * 8) % 2 == 0:
                    continue
                val = int(self._fnum(itd.get("value")))
                tier = min(4, int(math.log10(max(1, val))))
                cr = 6.0 + tier + 0.6 * math.sin(now * 5.0 + x * 0.05)
                bob = 1.5 * math.sin(now * 5.0 + x * 0.05)
                for ox, oy in ((3, 5), (-3, 3), (0, 0))[2 - min(2, tier):]:     # 뒤 → 앞 순서로 쌓기 (1..3 장)
                    self._oval(x + ox - cr, y - 7 + oy - cr + bob, x + ox + cr, y - 7 + oy + cr + bob,
                               fill=COIN_FILL, outline=COIN_EDGE, width=2)
                self._txt(x, y - 7 + bob, "₩", size=7 + tier // 2, fill=_dim_color(COIN_EDGE, 0.6))
                px_ = self._fnum((snap.get("player") or {}).get("x"))
                if val >= 100 or abs(px_ - x) < 80:
                    self._txt(x, y - 7 - cr - 9 + bob, "₩{:,}".format(val), size=8, fill=MONEY_FG)
                continue
            blink = it_t < 2.5 and int(it_t * 8) % 2 == 0
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
    def _new_halo(self) -> int:
        """스프라이트 적탄 테 1장. 생성 때 한 번만 모든 탄 이미지 아래(플레이어·적 위)로 내린다; 이후 재정렬 없음."""
        it = self.cv.create_oval(0, 0, 0, 0, fill="", outline="")
        self.cv.tag_lower(it, self.bullet_img_pool[0])      # 첫 탄 이미지를 막 꺼낸 뒤에만 불린다
        return it

    def _draw_enemy_bullet(self, b: dict, hw: float, hh: float, trail: bool) -> None:
        """v2.0: 적탄 — 어두운 테(밝은 배경용) + 채도 높은 빨간 핵(어두운 배경용) + 하이라이트 + 진행 반대쪽 잔상 2점.
        히트박스(w,h)는 그대로, 그림만 ~16 px 로 키움. 스냅샷에 vx/vy 가 없으면(0) 잔상 없이 핵만 그린다."""
        x, y = float(b["x"]), float(b["y"])
        ro = max(7.0, max(hw, hh) + 3.0)                     # 8x4 -> 7, 회장 도장 20x20 -> 13
        vx, vy = self._fnum(b.get("vx")), self._fnum(b.get("vy"))
        sp = math.hypot(vx, vy)
        if trail and sp > 1.0:
            ux, uy = vx / sp, vy / sp
            for k, rr in ((1.0, 0.45), (0.55, 0.65)):        # 먼 잔상부터 (아래에 깔림)
                gx, gy_ = x - ux * EB_TRAIL_LEN * k, y - uy * EB_TRAIL_LEN * k
                r = ro * rr
                self._oval(gx - r, gy_ - r, gx + r, gy_ + r, fill=EB_GHOST, outline=EB_RING, width=1)
        self._oval(x - ro, y - ro, x + ro, y + ro, fill=EB_CORE, outline=EB_RING, width=2)
        g = max(1.5, ro * 0.3)
        cx, cy = x - ro * 0.35, y - ro * 0.35
        self._oval(cx - g, cy - g, cx + g, cy + g, fill=EB_GLINT, outline="")

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
            self.hud_items["perks"] = []      # v2.0: 퍽 칩 줄 (텍스트 쌍 풀, 필요한 만큼 생성)
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
        # v2.0: 퍽 칩 줄 — 장착 레어+ 장비의 퍽 라벨을 등급 색으로 (충전형 second_wind / pit_save 는 ● 남음 / ○ 소진)
        chips = [d for d in hud.get("perks") if isinstance(d, dict)] if isinstance(hud.get("perks"), list) else []
        pool = self.hud_items["perks"]
        while len(pool) < len(chips):
            pool.append(self._text2(0, 0, "", size=8, anchor="nw"))
        px = 12
        for i, d in enumerate(chips):
            label = str(d.get("label") or d.get("key") or "")
            if d.get("key") in ("second_wind", "pit_save"):
                label = ("○ " if d.get("used") else "● ") + label
            txt = "[%s]" % label
            col = RARITY_COLORS["unique"] if d.get("rank") == 2 else RARITY_COLORS["rare"]
            self._set_text2(pool[i], px, bottom - 2, txt, fill=_dim_color(col, 0.6) if d.get("used") else col)
            for it in pool[i]:
                self._show(it)
            px += self._measure(txt, 8) + 6
        for pair in pool[len(chips):]:
            for it in pair:
                self._hide(it)
        if chips:
            right = max(right, px + 2)
            bottom += 16
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

    # ------------------------------------------------------------ v2.0 마을 (state == "town") — 시안 v1 "슬롯 선반"
    # 왼쪽 페이퍼돌 · 가운데 몸 순서(SHELF_ORDER)의 선반 6줄(장착 카드 + 창고/재고 카드 3장 + 여유칸) · 오른쪽 고정 비교표 ·
    # 아래 키 범례 + 슬롯 태그 메시지. 아이템은 전부 풀(한 번 생성, TOWN_LAYOUT_VERSION 이 바뀌면 재생성)이고 프레임마다
    # coords/itemconfig 만 바꾼다(_tset 이 바뀐 값만 보낸다). 글자는 픽셀 크기(음수 폰트)라 HTML 시안의 px 와 1:1 이고
    # 알파는 없으니 흐림은 _lerp_color(색, T_PANEL, k) 로 미리 섞는다. 그리는 순서 = 생성 순서: 패널 → 선반턱 → 스티커 →
    # 카드 → 인형 → 비교표 → 푸터/헤더. hud.town 의 키가 빠져도(구버전 스냅샷) _town_norm 이 채워 넣는다.
    TOWN_TAB_KEYS = ("stat", "shop", "store", "gamble")
    TOWN_TAB_LABELS = ("스탯 강화", "장비 상점", "창고", "도박장")
    TOWN_TAB_W = (96, 96, 64, 80)
    TOWN_LEGEND = {"store": (("←→", "카드"), ("↑↓", "선반"), ("Enter", "장착"), ("C", "판매"), ("Tab", "탭")),
                   "shop": (("←→", "상품"), ("↑↓", "선반"), ("Enter", "구매"), ("Tab", "탭")),
                   "stat": (("↑↓", "항목"), ("Enter", "강화"), ("Tab", "탭")),
                   "gamble": (("↑↓", "게임"), ("Enter", "실행"), ("C", "판돈"), ("Tab", "탭"))}
    TOWN_AFTER_LABEL = {"equip": "장착 후", "unequip": "해제 후", "buy": "구매 후", "box": "개봉 후",
                        "stat": "강화 후", "gamble": "기대 결과", "next": "다음"}
    TOWN_KEYS = ("Enter", "Space", "Tab", "Esc", "←→", "↑↓", "←", "→", "↑", "↓", "C")
    TOWN_STAT_NAMES = {"str": "힘", "agi": "민첩", "int": "지혜", "rate": "연사", "shield": "실드", "life": "목숨"}
    TOWN_GAMBLE_GLYPHS = ("dice", "coin", "reel")
    TOWN_BOX_SUB = "장비 · 아이템 · 돈 중 하나"

    # --- 풀 생성/갱신 유틸
    def _tfont(self, px: int, bold: bool = True):
        return (FONT, -int(px), "bold" if bold else "normal")

    def _tw(self, text, px: int, bold: bool = True) -> int:
        return self._measure(str(text), -int(px), bold)

    def _titem(self, it: int) -> int:
        self.town_ui["_all"].append(it)
        return it

    def _ttext(self, px: int = 12, bold: bool = True, anchor: str = "w", fill: str = T_TEXT) -> int:
        return self._titem(self.cv.create_text(0, 0, text="", font=self._tfont(px, bold), fill=fill, anchor=anchor,
                                               state="hidden", tags=("town",)))

    def _trect(self, fill: str = T_CARD, outline: str = "", width: int = 1, dash=None) -> int:
        kw = {"fill": fill, "outline": outline, "width": width, "state": "hidden", "tags": ("town",)}
        if dash:
            kw["dash"] = dash
        return self._titem(self.cv.create_rectangle(0, 0, 0, 0, **kw))

    def _tpoly(self, fill: str = T_TEXT) -> int:
        return self._titem(self.cv.create_polygon(0, 0, 0, 0, 0, 0, fill=fill, outline="", state="hidden", tags=("town",)))

    def _tline(self, fill: str = T_TEXT, width: int = 2) -> int:
        return self._titem(self.cv.create_line(0, 0, 0, 0, fill=fill, width=width, state="hidden", tags=("town",)))

    def _tset(self, it: int, xy=None, **cfg) -> None:
        """풀 아이템 갱신: 좌표/설정 중 바뀐 것만 tk 로 보내고 이번 프레임에 쓴 것으로 표시한다."""
        ui = self.town_ui
        ui["_used"].add(it)
        c = ui["_cache"].get(it)
        if c is None:
            c = ui["_cache"][it] = {}
        if xy is not None:
            xy = tuple(int(round(v)) for v in xy)
            if c.get("xy") != xy:
                self.cv.coords(it, *xy)
                c["xy"] = xy
        cfg["state"] = "normal"
        ch = {k: v for k, v in cfg.items() if c.get(k) != v}
        if ch:
            self.cv.itemconfig(it, **ch)
            c.update(ch)

    def _town_hide_all(self) -> None:
        ui = self.town_ui
        if not ui:
            return
        for it in ui.get("_all", ()):
            self._hide(it)
        ui["_cache"] = {}
        ui["_visible"] = False

    def _town_all_items(self):
        ui = self.town_ui
        if ui:
            yield from ui.get("_all", ())

    def _tglyph_new(self) -> list:
        return [self._tpoly() for _ in range(TOWN_GLYPH_PARTS)]

    def _tglyph(self, g: list, kind: str, x: float, y: float, size: float, fg: str, bg: str) -> None:
        """16px 격자 글리프(TOWN_GLYPHS)를 (x, y) 에 size 로 그린다. 안 쓰는 부품은 숨겨진 채 남는다."""
        parts = TOWN_GLYPHS.get(kind) or ()
        k = size / 16.0
        for i, it in enumerate(g):
            if i >= len(parts):
                break
            which, pts = parts[i]
            xy = tuple((x + p * k) if j % 2 == 0 else (y + p * k) for j, p in enumerate(pts))
            self._tset(it, xy, fill=fg if which == "fg" else bg)

    def _tkeycap(self, kc: tuple, x: float, y: float, label: str, fg: str = T_TEXT, bg: str = T_CARD,
                 edge: str = T_EDGE, h: int = 16, px: int = 10, pad: int = 4, width: int = 1) -> int:
        """키캡 (rect, text) 를 왼쪽 위 (x, y) 에 그리고 폭을 돌려준다."""
        w = self._tw(label, px) + pad * 2
        self._tset(kc[0], (x, y, x + w - 1, y + h - 1), fill=bg, outline=edge, width=width)
        self._tset(kc[1], (x + w / 2.0, y + h / 2.0), text=label, fill=fg, font=self._tfont(px, True), anchor="center")
        return w

    def _tcard_new(self, ghost: bool) -> dict:
        return {"box": self._trect(), "chip": self._trect(), "stamp": self._trect(fill="", width=2),
                "stamp_t": self._ttext(10, anchor="center"), "tag": self._trect(), "tag_t": self._ttext(10, anchor="center"),
                "name": self._ttext(12), "lv": self._ttext(10, anchor="e"), "price": self._ttext(10),
                "tok": [self._ttext(10) for _ in range(4)],                      # 2줄째 값 ("+3", "+12%")
                "tokl": [self._ttext(10, bold=False, fill=T_MUTED) for _ in range(4)],   # 2줄째 라벨 ("힘", "연사") — 흐린색
                "glyph": self._tglyph_new() if ghost else None}

    def _town_build(self) -> dict:
        """마을 풀 전체 생성 (생성 순서 = z 순서)."""
        self.town_ui = ui = {"ver": TOWN_LAYOUT_VERSION, "_all": [], "_cache": {}, "_used": set(), "_visible": False}
        ui["back"] = self._trect(fill=T_GROUND)              # 띠 전체 바닥색 (1920/2560 은 패널 양옆이 바닥색, 플레이 HUD 가림)
        ui["panel"] = self._trect(fill=T_PANEL, outline=T_EDGE)
        ui["rule"] = self._trect(fill=T_EDGE)
        ui["shelves"] = []
        for _ in range(6):
            sh = {"groove": self._trect(fill=T_GROUND), "lip": [self._trect() for _ in range(3)],
                  "box": self._trect(fill=T_CARD, outline=T_EDGE), "tab": self._tpoly(), "glyph": self._tglyph_new(),
                  "label": self._ttext(12), "sub": self._ttext(10, bold=False),
                  "cells": [self._trect(fill=T_GROUND, outline=T_CELL_EDGE) for _ in range(3)],
                  "card0": self._tcard_new(True), "cards": [self._tcard_new(False) for _ in range(3)],
                  "more": self._ttext(10, anchor="e", fill=T_MUTED), "less": self._ttext(10, anchor="center", fill=T_MUTED)}
            ui["shelves"].append(sh)
        ui["reels"] = [(self._trect(fill=T_GROUND, outline=T_EDGE), self._ttext(14, anchor="center")) for _ in range(3)]
        # 인형
        ui["name"] = self._ttext(14)
        ui["trait"] = self._ttext(10, bold=False, fill=T_MUTED)
        ui["sprite"] = self._titem(self.cv.create_image(0, 0, anchor="nw", state="hidden", tags=("town",)))
        ui["lead"] = self._tline()
        ui["dots"] = [self._trect(outline=T_GROUND) for _ in range(6)]
        ui["eq_lbl"] = self._ttext(11, bold=False, fill=T_MUTED)
        ui["eq_sq"] = [self._trect() for _ in range(6)]
        ui["cap_lbl"] = self._ttext(11, bold=False, fill=T_MUTED)
        ui["cap_ticks"] = [self._trect() for _ in range(24)]
        # 비교표
        cp = {"box": self._trect(fill=T_CARD, outline=T_EDGE), "stripe": self._trect(), "name": self._ttext(14),
              "glyph": self._tglyph_new(), "sub1": self._ttext(10, bold=False, fill=T_MUTED), "sub2": self._ttext(10),
              "hdr": [self._ttext(10, bold=False, fill=T_MUTED, anchor=a) for a in ("w", "e", "e", "e")],
              "rules": [self._trect(fill=T_EDGE) for _ in range(3)],
              "rows": [{"glyph": self._tglyph_new(), "label": self._ttext(12, bold=False), "now": self._ttext(12, bold=False, anchor="e", fill=T_MUTED),
                        "after": self._ttext(12, anchor="e"), "delta": self._ttext(12, anchor="e")} for _ in range(4)],
              "perk_lbl": self._ttext(10, bold=False, fill=T_MUTED),
              "chips": [(self._trect(fill=T_EDGE), self._ttext(10, anchor="center")) for _ in range(2)],
              "perk_txt": self._ttext(10, bold=False, fill="#a3acbc"),
              "p1_lbl": self._ttext(10, bold=False, fill=T_MUTED), "p1_val": self._ttext(12),
              "p2": self._ttext(10, bold=False, fill=T_MUTED, anchor="e"), "p2_val": self._ttext(12, anchor="e"),
              "after_msg": self._ttext(10, bold=False, fill=T_MUTED)}
        ui["cmp"] = cp
        # 랜덤박스 줄 (상점) + 푸터
        ui["boxrow"] = {"box": self._trect(fill=T_CARD, outline=T_EDGE), "key": (self._trect(), self._ttext(10, anchor="center")),
                        "glyph": self._tglyph_new(), "name": self._ttext(12), "sub": self._ttext(10, bold=False, fill=T_MUTED),
                        "price": self._ttext(12, anchor="e")}
        # 다음 스테이지 카드 (상점 외 탭: 랜덤박스 줄 자리) — 커서가 "다음" 줄이면 금색 통채움 (peel)
        ui["nextrow"] = {"box": self._trect(fill=T_CARD, outline=T_EDGE), "key": (self._trect(), self._ttext(10, anchor="center")),
                         "name": self._ttext(12), "sub": self._ttext(10, bold=False, fill=T_MUTED)}
        ui["legend"] = [((self._trect(), self._ttext(10, anchor="center")), self._ttext(11, bold=False, fill=T_MUTED)) for _ in range(6)]
        ui["msg"] = [(self._trect(), self._ttext(11, bold=False)) for _ in range(10)]
        # 헤더
        ui["tabs"] = [{"box": self._trect(fill=T_CARD, outline=T_EDGE), "bar": self._trect(fill=T_GOLD), "cover": self._trect(fill=T_CARD),
                       "txt": self._ttext(14, anchor="center")} for _ in range(4)]
        ui["title"] = self._ttext(12, bold=False, fill=T_MUTED)
        ui["money"] = self._ttext(18, anchor="e", fill=T_GOLD)
        ui["score"] = self._ttext(12, bold=False, anchor="e", fill=T_MUTED)
        ui["next_box"] = self._trect(fill=T_GOLD, outline=T_GOLD)   # "다음" 줄일 때 헤더 버튼 통채움 + 3px 금색 턱
        ui["next_lip"] = self._trect(fill=T_GOLD)
        ui["next_key"] = (self._trect(), self._ttext(10, anchor="center"))
        ui["next_txt"] = self._ttext(11, bold=False, fill=T_MUTED)
        return ui

    # --- 숫자/문자 보조
    @staticmethod
    def _tint(v, default: int = 0) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _tmoney(v) -> str:
        try:
            return "₩" + format(int(v), ",")
        except (TypeError, ValueError):
            return "₩0"

    @staticmethod
    def _tfmt(v, fmt: str = "int", sign: bool = False) -> str:
        """비교표/카드 숫자. fmt "pct": 0.12 → 12% · "money": ₩1,234 · "int": 13. 문자열은 그대로."""
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        if fmt == "pct":
            n = int(round(f * 100))
            s = "%d%%" % abs(n)
        elif fmt == "money":
            n = int(round(f))
            s = "₩" + format(abs(n), ",")
        else:
            n = int(round(f)) if abs(f - round(f)) < 1e-6 else round(f, 1)
            s = format(abs(n), ",") if isinstance(n, int) else "%.1f" % abs(n)
        if n < 0:
            return "-" + s
        return ("+" + s) if (sign and n > 0) else s

    def _fit(self, text: str, size: int, maxw: int) -> str:
        text = str(text)
        if self._measure(text, size) <= maxw:
            return text
        while len(text) > 1 and self._measure(text + "…", size) > maxw:
            text = text[:-1]
        return text + "…"

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

    @staticmethod
    def _tsort_key(eq: dict):
        rank = {"unique": 0, "rare": 1, "normal": 2}
        return (rank.get(eq.get("rarity"), 3), -Renderer._tint(eq.get("level")), str(eq.get("name") or ""))

    # --- hud.town 정규화 (구버전 스냅샷도 같은 뷰로)
    def _town_norm(self, town: dict, hud: dict, snap: dict) -> dict:
        tab = town.get("tab") if town.get("tab") in self.TOWN_TAB_KEYS else "stat"
        tabs = town.get("tabs") if isinstance(town.get("tabs"), list) and len(town.get("tabs")) >= 4 else list(self.TOWN_TAB_LABELS)
        player = snap.get("player") if isinstance(snap.get("player"), dict) else {}
        ch = dict(town.get("char")) if isinstance(town.get("char"), dict) else {}
        ch.setdefault("key", player.get("palette") or "hyunki")
        ch.setdefault("name", hud.get("char_name") or "")
        ch.setdefault("trait", "")
        ch.setdefault("stats", hud.get("stats") if isinstance(hud.get("stats"), dict) else {})
        ch.setdefault("shield_max", hud.get("shield_max"))
        ch.setdefault("lives", hud.get("lives"))
        v = {"tab": tab, "tabs": [str(t) for t in tabs[:4]], "tab_index": self.TOWN_TAB_KEYS.index(tab),
             "msg": str(town.get("msg") or town.get("message") or ""),      # 직전 실행 결과(msg) 우선, 없으면 문맥 문구(message)
             "stage": self._tint(town.get("stage") or hud.get("stage_no")),
             "money": self._tint(town.get("money", hud.get("money"))), "score": self._tint(town.get("score", hud.get("score"))),
             "char": ch, "compare": town.get("compare") if isinstance(town.get("compare"), dict) else None,
             "legend": town.get("legend") if isinstance(town.get("legend"), list) else [list(p) for p in self.TOWN_LEGEND[tab]],
             "box": None, "shelves": []}
        cap = town.get("capacity") if isinstance(town.get("capacity"), dict) else {}
        store = town.get("store") if isinstance(town.get("store"), dict) else {}
        equipped = store.get("equipped") if isinstance(store.get("equipped"), dict) else {}
        if not equipped and isinstance(hud.get("equipped"), dict):
            equipped = hud["equipped"]
        n_eq = sum(1 for s in SHELF_ORDER if isinstance(equipped.get(s), dict))
        v["capacity"] = {"used": self._tint(cap.get("used", len(store.get("items") or []))), "cap": self._tint(cap.get("cap", store.get("cap", 24)), 24),
                         "equipped": self._tint(cap.get("equipped", n_eq))}
        v["equipped"] = equipped
        shop = town.get("shop") if isinstance(town.get("shop"), dict) else {}
        stock = [e for e in (shop.get("stock") or []) if isinstance(e, dict)]
        if tab == "shop":
            box = next((e for e in stock if e.get("kind") == "box"), None)
            if box is None and town.get("box") is not None:
                box = town.get("box") if isinstance(town.get("box"), dict) else {"price": town.get("box")}
            if box is not None:
                price = self._eq_price(box) or 0
                v["box"] = {"price": price, "afford": bool(box.get("afford", v["money"] >= price)), "label": str(box.get("label") or "랜덤박스"),
                            "sub": str(box.get("sub") or self.TOWN_BOX_SUB)}
        shelves = town.get("shelves") if isinstance(town.get("shelves"), list) else None
        if tab in ("store", "shop"):
            if shelves:
                v["shelves"] = [self._town_norm_shelf(sh, equipped, tab) for sh in shelves if isinstance(sh, dict)]
            else:
                v["shelves"] = self._town_legacy_shelves(tab, store, shop, stock, equipped)
        elif tab == "stat":
            v["shelves"] = self._town_stat_shelves(town, hud, shelves)
        else:
            v["shelves"] = self._town_gamble_shelves(town, shelves)
        n_rows = len(v["shelves"]) + (1 if v["box"] else 0) + 1
        v["rows_total"] = max(n_rows, self._tint(town.get("rows_total"), n_rows))
        cur = town.get("cursor") if isinstance(town.get("cursor"), dict) else None
        if cur is not None:
            row, col = self._tint(cur.get("row")), self._tint(cur.get("col"))
        else:
            row, col = self._town_legacy_cursor(tab, town, v, store, stock)
        row = row % max(1, v["rows_total"])
        v["cursor"] = {"row": row, "col": max(0, col)}
        v["on_next"] = row == v["rows_total"] - 1
        v["on_box"] = bool(v["box"]) and row == v["rows_total"] - 2
        if v["compare"] is None and not v["on_next"]:
            v["compare"] = self._town_derive_compare(v, tab, town, hud)
        return v

    def _town_norm_shelf(self, sh: dict, equipped: dict, tab: str) -> dict:
        slot = sh.get("slot")
        eq = sh.get("equipped") if isinstance(sh.get("equipped"), dict) else (equipped.get(slot) if isinstance(equipped.get(slot), dict) else None)
        raw = list(sh.get("cards") or [])
        n = sh.get("count")
        # v2.1 contract (game.py): cards[0] = 장착 카드(eq_view) 또는 None(고스트), count = len(cards) - 1 → 창고/재고 카드는 cards[1:]
        # (픽스처처럼 cards 가 창고/재고 카드만 담고 있으면 그대로 둔다)
        if raw and (raw[0] is None or (isinstance(n, int) and len(raw) == n + 1 and isinstance(raw[0], dict) and raw[0].get("is_equipped"))):
            if eq is None and isinstance(raw[0], dict):
                eq = raw[0]
            raw = raw[1:]
        cards = [c for c in raw if isinstance(c, dict)]
        ekey = sh.get("effect_key") or SLOT_EFFECT_KEY.get(slot, "")
        for c in cards:
            self._town_fill_deltas(c, eq, ekey)
        return {"slot": slot, "label": str(sh.get("label") or SLOT_LABEL.get(slot, slot)), "hue": SLOT_HUES.get(slot, T_MUTED), "glyph": slot,
                "effect_key": ekey, "effect_label": str(sh.get("effect_label") or EFFECT_LABEL.get(ekey, ekey)),
                "count": self._tint(sh.get("count"), len(cards)), "window": max(0, self._tint(sh.get("window"))),
                "equipped": eq, "cards": cards, "kind": tab}

    @staticmethod
    def _town_fill_deltas(c: dict, eq, ekey: str) -> None:
        """카드에 delta_stats / delta_effect 가 없으면(구버전) 장착 장비와 비교해 채운다."""
        st = c.get("stats") if isinstance(c.get("stats"), dict) else {}
        est = eq.get("stats") if isinstance(eq, dict) and isinstance(eq.get("stats"), dict) else {}
        if not isinstance(c.get("delta_stats"), dict):
            c["delta_stats"] = {k: Renderer._tint(st.get(k)) - Renderer._tint(est.get(k)) for k in ("str", "agi", "int")}
        if not isinstance(c.get("delta_effect"), dict):
            fx = c.get("effect") if isinstance(c.get("effect"), dict) else {}
            efx = eq.get("effect") if isinstance(eq, dict) and isinstance(eq.get("effect"), dict) else {}
            now = Renderer._fnum(efx.get(ekey)) if isinstance(eq, dict) else 0.0
            c["delta_effect"] = {"key": ekey, "now": now, "after": Renderer._fnum(fx.get(ekey))}

    def _town_legacy_shelves(self, tab: str, store: dict, shop: dict, stock: list, equipped: dict) -> list:
        items = [e for e in (store.get("items") or []) if isinstance(e, dict)] if tab == "store" else [e for e in stock if e.get("kind") != "box"]
        sells = store.get("sell") if isinstance(store.get("sell"), list) else []
        prices = shop.get("prices") if isinstance(shop.get("prices"), list) else []
        afford = shop.get("afford") if isinstance(shop.get("afford"), list) else []
        out = []
        for slot in SHELF_ORDER:
            eq = equipped.get(slot) if isinstance(equipped.get(slot), dict) else None
            ekey = SLOT_EFFECT_KEY.get(slot, "")
            cards = []
            for i, e in enumerate(items):
                if e.get("slot") != slot:
                    continue
                c = dict(e)
                c["index"] = i
                if tab == "store":
                    c["price"] = sells[i] if i < len(sells) else self._eq_price(e)
                else:
                    c["price"] = prices[i] if i < len(prices) else self._eq_price(e)
                    c["afford"] = bool(afford[i]) if i < len(afford) else True
                    name = e.get("name")
                    c["owned"] = sum(1 for w in (store.get("items") or []) if isinstance(w, dict) and w.get("name") == name)                         + sum(1 for w in equipped.values() if isinstance(w, dict) and w.get("name") == name)
                self._town_fill_deltas(c, eq, ekey)
                cards.append(c)
            cards.sort(key=self._tsort_key)
            out.append({"slot": slot, "label": SLOT_LABEL.get(slot, slot), "hue": SLOT_HUES.get(slot, T_MUTED), "glyph": slot,
                        "effect_key": ekey, "effect_label": EFFECT_LABEL.get(ekey, ekey), "count": len(cards), "window": 0,
                        "equipped": eq, "cards": cards, "kind": tab})
        return out

    def _town_legacy_cursor(self, tab: str, town: dict, v: dict, store: dict, stock: list) -> tuple:
        """구버전 town.index → (row, col). 마지막 항목은 언제나 다음 스테이지."""
        idx = self._tint(town.get("index"))
        shelves = v["shelves"]
        if tab in ("stat", "gamble"):
            return (min(idx, len(shelves)), 0)
        if tab == "store":
            if store.get("mode") == "equipped":
                slots = store.get("slot_order") if isinstance(store.get("slot_order"), list) else list(SLOT_ORDER)
                if idx < len(slots) and slots[idx] in SHELF_ORDER:
                    return (SHELF_ORDER.index(slots[idx]), 0)
                return (v["rows_total"] - 1, 0)
            for r, sh in enumerate(shelves):
                for k, c in enumerate(sh["cards"]):
                    if c.get("index") == idx:
                        sh["window"] = max(0, k - 2)
                        return (r, k + 1)
            return (v["rows_total"] - 1, 0)
        n_stock = sum(1 for e in stock if e.get("kind") != "box")
        if idx >= n_stock:
            return (v["rows_total"] - (2 if (idx == n_stock and v["box"]) else 1), 0)
        for r, sh in enumerate(shelves):
            for k, c in enumerate(sh["cards"]):
                if c.get("index") == idx:
                    sh["window"] = max(0, k - 2)
                    return (r, k + 1)
        return (0, 1)

    def _town_stat_shelves(self, town: dict, hud: dict, shelves) -> list:
        stat = town.get("stat") if isinstance(town.get("stat"), dict) else {}
        rows = [r for r in (stat.get("items") or []) if isinstance(r, dict) and r.get("key") != "next"]
        if shelves and not rows:
            rows = [sh for sh in shelves if isinstance(sh, dict)]
        score = self._tint(town.get("score", hud.get("score")))
        out = []
        for r in rows[:6]:
            key = str(r.get("key") or r.get("slot") or "")
            lv, mx, cost = self._tint(r.get("level")), self._tint(r.get("max")), self._tint(r.get("cost"))
            afford = bool(r.get("afford", (mx <= 0 or lv < mx) and score >= cost))
            out.append({"slot": key, "label": self.TOWN_STAT_NAMES.get(key, str(r.get("label") or key)), "hue": TOWN_STAT_HUES.get(key, T_MUTED),
                        "glyph": key, "effect_key": key, "effect_label": self.TOWN_STAT_NAMES.get(key, key), "count": 0, "window": 0,
                        "equipped": None, "cards": [], "kind": "stat",
                        "stat": {"label": str(r.get("label") or key), "cost": cost, "level": lv, "max": mx, "afford": afford}})
        return out

    def _town_gamble_shelves(self, town: dict, shelves) -> list:
        gm = town.get("gamble") if isinstance(town.get("gamble"), dict) else {}
        games = gm.get("games") if isinstance(gm.get("games"), list) else ["강화 도박", "더블업", "슬롯"]
        eq = gm.get("target_eq") if isinstance(gm.get("target_eq"), dict) else None
        stake, bet, streak = self._tint(gm.get("stake")), self._tint(gm.get("bet")), self._tint(gm.get("streak"))
        subs = ("대상 " + (SLOT_LABEL.get(eq.get("slot"), str(eq.get("slot"))) if eq else "없음"),
                "판돈 %d%%" % self._tint(gm.get("stake_pct"), 10), "판돈 " + self._tmoney(bet))
        out = []
        for i in range(3):
            out.append({"slot": "g%d" % i, "label": str(games[i]) if i < len(games) else "", "hue": TOWN_GAMBLE_HUES[i],
                        "glyph": self.TOWN_GAMBLE_GLYPHS[i], "effect_key": "", "effect_label": subs[i], "count": 0, "window": 0,
                        "equipped": None, "cards": [], "kind": "gamble",
                        "gamble": {"i": i, "eq": eq, "cost": self._tint(gm.get("target_cost")), "stake": stake, "bet": bet, "streak": streak,
                                   "reels": gm.get("reels") if isinstance(gm.get("reels"), list) else None,
                                   "text": str(gm.get("text") or gm.get("payout_text") or "")}})
        return out

    def _town_derive_compare(self, v: dict, tab: str, town: dict, hud: dict):
        """town.compare 가 없을 때(구버전/스탯/도박장) 커서 항목에서 비교표를 만든다."""
        row, col = v["cursor"]["row"], v["cursor"]["col"]
        shelves = v["shelves"]
        if v["on_box"] and v["box"]:
            b = v["box"]
            return {"name": b["label"], "rarity": "normal", "level": None, "slot": "box", "slot_label": "상점", "action": "box",
                    "rows": [], "perks": [], "buy": b["price"], "after_msg": "장비 60% · 아이템 25% · 돈 10% · 꽝 5%"}
        if row >= len(shelves):
            return None
        sh = shelves[row]
        st = v["char"].get("stats") if isinstance(v["char"].get("stats"), dict) else {}
        base = [(STAT_LABEL[k], self._tint(st.get(k))) for k in ("str", "agi", "int")]
        if sh["kind"] == "stat":
            s = sh["stat"]
            key = sh["slot"]
            rows = [{"label": lb, "now": n, "after": n + (1 if key == k else 0), "delta": (1 if key == k else None), "fmt": "int"}
                    for (lb, n), k in zip(base, ("str", "agi", "int"))]
            rows.append({"label": "점수", "now": v["score"], "after": v["score"] - s["cost"], "delta": -s["cost"], "fmt": "int"})
            lvtxt = ("Lv %d/%d" % (s["level"], s["max"])) if s["max"] > 0 else ("Lv %d" % s["level"])
            return {"name": s["label"], "rarity": "normal", "level": s["level"], "slot": key, "slot_label": sh["label"], "action": "stat",
                    "rows": rows, "perks": [], "buy": s["cost"], "unit": "점", "after_msg": "강화하면 %s · 점수 %s" % (lvtxt, format(max(0, v["score"] - s["cost"]), ",")),
                    "afford": s["afford"]}
        if sh["kind"] == "gamble":
            g = sh["gamble"]
            i = g["i"]
            if i == 0:
                eq = g["eq"]
                lv = self._tint(eq.get("level")) if eq else 0
                down = 1 if (eq and eq.get("rarity") == "unique") else 3
                rows = [{"label": "성공 60%", "now": g["cost"], "after": "Lv %d" % (lv + 2), "delta": "+2", "fmt": "money"},
                        {"label": "유지 30%", "now": g["cost"], "after": "Lv %d" % lv, "delta": "·", "fmt": "money"},
                        {"label": "실패 10%", "now": g["cost"], "after": "Lv %d" % max(0, lv - down), "delta": "-%d" % down, "fmt": "money"}]
                return {"name": eq.get("name") if eq else "대상 장비 없음", "rarity": (eq or {}).get("rarity", "normal"), "level": lv if eq else None,
                        "slot": (eq or {}).get("slot"), "slot_label": SLOT_LABEL.get((eq or {}).get("slot"), sh["label"]), "action": "gamble",
                        "cols": ("판돈", "기대 결과", "변화"), "rows": rows, "perks": [], "buy": g["cost"], "after_msg": "C 대상 장비 변경 · 장착 중인 장비만"}
            if i == 1:
                stk = g["stake"]
                mult = max(1, 2 ** min(g["streak"], 3))
                rows = [{"label": "성공 50%", "now": stk, "after": stk * 2, "delta": stk, "fmt": "money"},
                        {"label": "실패 50%", "now": stk, "after": 0, "delta": -stk, "fmt": "money"},
                        {"label": "연속 ×%d" % mult, "now": stk, "after": stk * mult * 2, "delta": "최대 ×8", "fmt": "money"}]
                return {"name": sh["label"], "rarity": "normal", "level": None, "slot": "g1", "slot_label": "도박장", "action": "gamble",
                        "cols": ("판돈", "기대 결과", "변화"), "rows": rows, "perks": [], "buy": stk, "after_msg": "C 판돈 비율 변경 (10% · 25% · 50%)"}
            bet = g["bet"]
            rows = [{"label": "7 7 7", "now": bet, "after": bet * 30, "delta": "+유니크", "fmt": "money"},
                    {"label": "₩ ₩ ₩", "now": bet, "after": bet * 10, "delta": "×10", "fmt": "money"},
                    {"label": "◆◆◆ · ♥♥♥", "now": bet, "after": bet * 5, "delta": "×5", "fmt": "money"},
                    {"label": "★ ★ ★", "now": bet, "after": "레어 장비", "delta": "·", "fmt": "money"}]
            return {"name": sh["label"], "rarity": "normal", "level": None, "slot": "g2", "slot_label": "도박장", "action": "gamble",
                    "cols": ("판돈", "기대 결과", "배당"), "rows": rows, "perks": [], "buy": bet, "after_msg": "C 판돈 변경 (₩100 · ₩500 · ₩2,000)"}
        # 창고/상점 (구버전 스냅샷): 커서 카드의 스탯 델타
        eq = sh["equipped"]
        card = None
        if col == 0:
            card = eq
        elif col - 1 < len(sh["cards"]):
            card = sh["cards"][col - 1]
        if not isinstance(card, dict):
            return None
        is_eq = col == 0
        ds = card.get("delta_stats") if isinstance(card.get("delta_stats"), dict) else {}
        cst = card.get("stats") if isinstance(card.get("stats"), dict) else {}
        rows = []
        for (lb, n), k in zip(base, ("str", "agi", "int")):
            d = -self._tint(cst.get(k)) if is_eq else self._tint(ds.get(k))
            rows.append({"label": lb, "now": n, "after": n + d, "delta": d or None, "fmt": "int"})
        de = card.get("delta_effect") if isinstance(card.get("delta_effect"), dict) else {}
        ekey = sh["effect_key"]
        fmt = "pct" if ekey in PCT_KEYS else "int"
        if is_eq:
            now = self._fnum((card.get("effect") or {}).get(ekey)) if isinstance(card.get("effect"), dict) else 0.0
            rows.append({"label": sh["effect_label"], "now": now, "after": 0.0, "delta": (-now or None), "fmt": fmt})
        else:
            now, after = self._fnum(de.get("now")), self._fnum(de.get("after"))
            rows.append({"label": sh["effect_label"], "now": now, "after": after, "delta": ((after - now) or None), "fmt": fmt})
        action = "unequip" if is_eq else ("equip" if tab == "store" else "buy")
        perks = [{"label": str(l), "text": str(t)} for l, t in zip(card.get("perk_labels") or [], list(card.get("perk_texts") or []) + [""] * 4)]
        return {"name": card.get("name") or "?", "rarity": card.get("rarity") or "normal", "level": self._tint(card.get("level")),
                "slot": sh["slot"], "slot_label": sh["label"], "action": action, "rows": rows, "perks": perks,
                "sell": (card.get("price") if tab == "store" else card.get("sell")), "enhance": card.get("enhance"),
                "buy": (card.get("price") if tab == "shop" else None), "after_msg": "", "afford": card.get("afford", True)}

    # --- 그리기
    def _draw_town(self, snap):
        hud = snap.get("hud") or {}
        town = hud.get("town") if snap.get("state") == "town" else None
        if not isinstance(town, dict):
            if self.town_ui and self.town_ui.get("_visible"):
                self._town_hide_all()
            return
        ui = self.town_ui
        if not ui or ui.get("ver") != TOWN_LAYOUT_VERSION:
            if ui:
                for it in ui.get("_all", ()):
                    self.cv.delete(it)
            ui = self._town_build()
        ui["_used"] = set()
        ui["_visible"] = True
        v = self._town_norm(town, hud, snap)
        W, H = self.W, self.H
        # 좁은 띠(1366/1440 노트북): 선반 카드 수를 줄이고 오른쪽 열(시안 x ≥ TOWN_RIGHT_COL)을 카드 피치만큼 왼쪽으로 민다
        n_cards = 3
        while n_cards > 1 and W < 72 + TOWN_W - (3 - n_cards) * TOWN_CARD_PITCH:
            n_cards -= 1
        dx = (3 - n_cards) * TOWN_CARD_PITCH
        ox = max(-72, (W - (TOWN_W - dx)) // 2 - 72)              # 시안 좌표(폭 1600, 패널 x72) → 화면 x
        # 여분 높이는 8칸(선반 피치 6 + 헤더 아래 1 + 푸터 위 1)으로 나눠 최대 8px 씩 주고, 그 블록을 세로 가운데에 놓는다
        u = min(8, max(0, (H - TOWN_H) // 8))
        pitch = 40 + u
        extra = 8 * u                                            # 푸터가 내려가는 양 (= 블록이 자라는 양)
        oy = max(0, (H - TOWN_H - extra) // 2)
        g = {"ox": ox, "oy": oy, "pitch": pitch, "u": u, "extra": extra, "now": time.perf_counter(), "cards": n_cards}
        if dx:
            X = lambda x: x + ox - (dx if x >= TOWN_RIGHT_COL else 0)   # noqa: E731
        else:
            X = lambda x: x + ox                                 # noqa: E731
        Y = lambda y: y + oy                                     # noqa: E731
        g["X"], g["Y"] = X, Y
        g["sy"] = Y(48) + u                                      # 첫 선반 y (헤더 아래 1칸)
        if v["tab"] == "gamble":                                 # 선반 3줄: 피치를 20px 늘리고 6줄 띠 안에 가운데 정렬 (빈 띠 제거)
            gp = pitch + 20
            off = (6 * pitch - 3 * gp) // 2
        else:
            gp, off = pitch, 0
        g["row_y"] = lambda i: g["sy"] + off + i * gp            # noqa: E731
        self._tset(ui["back"], (0, 0, W, H))
        self._tset(ui["panel"], (X(72), 0, X(72 + TOWN_W) - 1, H - 1))
        cur_row = v["cursor"]["row"]
        shelves = v["shelves"]
        cursor_shelf = shelves[cur_row] if cur_row < len(shelves) else None
        for i, sh in enumerate(shelves[:6]):
            self._town_shelf(ui["shelves"][i], sh, i, v, g, on=(i == cur_row))
        self._town_doll(ui, v, g, cursor_shelf, cur_row)
        self._town_compare(ui["cmp"], v, g)
        self._town_footer(ui, v, g)
        self._town_header(ui, v, g)
        # 이번 프레임에 안 쓴 풀 아이템은 숨김 (캐시로 중복 호출 없음)
        cache = ui["_cache"]
        for it in ui["_all"]:
            if it not in ui["_used"]:
                c = cache.get(it)
                if c is None:
                    c = cache[it] = {}
                if c.get("state") != "hidden":
                    self.cv.itemconfig(it, state="hidden")
                    c["state"] = "hidden"
        self.cv.tag_raise("town")                                # 월드 아이템보다 위 (생성 순서 유지)

    def _town_header(self, ui: dict, v: dict, g: dict) -> None:
        X, Y = g["X"], g["Y"]
        self._tset(ui["rule"], (X(80), Y(40), X(1519), Y(40)), fill=T_EDGE, outline="")
        tx = 80
        for j, t in enumerate(ui["tabs"]):
            w = self.TOWN_TAB_W[j]
            active = j == v["tab_index"]
            if active:
                self._tset(t["box"], (X(tx), Y(8), X(tx + w - 1), Y(40)), fill=T_CARD, outline=T_EDGE)
                self._tset(t["bar"], (X(tx), Y(8), X(tx + w - 1), Y(10)), fill=T_GOLD, outline="")
                self._tset(t["cover"], (X(tx + 1), Y(40), X(tx + w - 2), Y(41)), fill=T_CARD, outline="")
            self._tset(t["txt"], (X(tx + w / 2.0), Y(24)), text=v["tabs"][j], fill=T_TEXT if active else T_MUTED, font=self._tfont(14, active))
            tx += w + 8
        self._tset(ui["title"], (X(456), Y(25)), text=("마을 · %d스테이지 클리어" % v["stage"]) if v["stage"] else "마을")
        self._tset(ui["money"], (X(1520), Y(22)), text=self._tmoney(v["money"]))
        self._tset(ui["score"], (X(1408), Y(25)), text="점수 " + format(v["score"], ","))
        # 다음 스테이지: Esc 키캡 (Esc = "다음" 줄로 점프) · 커서가 그 줄이면 금색 통채움 버튼 + 바탕색 글자 + 3px 금색 턱 (peel)
        on = v["on_next"]
        label = "Enter" if on else "Esc"
        txt = "다음 스테이지 ▶"
        kw = self._tw(label, 10) + 8
        tw = self._tw(txt, 11, on)
        x0 = X(1320) - (kw + 4 + tw)
        if on:
            self._tset(ui["next_box"], (x0 - 8, Y(9), x0 + kw + 4 + tw + 8, Y(35)), fill=T_GOLD, outline=T_GOLD, width=1)
            self._tset(ui["next_lip"], (x0 - 8, Y(37), x0 + kw + 4 + tw + 8, Y(39)), fill=T_GOLD, outline="")
            self._tkeycap(ui["next_key"], x0, Y(14), label, fg=T_GOLD, bg=T_GROUND, edge=T_GROUND)
            self._tset(ui["next_txt"], (x0 + kw + 4, Y(22)), text=txt, fill=T_GROUND, font=self._tfont(11, True))
        else:
            self._tkeycap(ui["next_key"], x0, Y(13), label, fg=T_TEXT, bg=T_CARD, edge=T_EDGE)
            self._tset(ui["next_txt"], (x0 + kw + 4, Y(21)), text=txt, fill=T_MUTED, font=self._tfont(11, False))

    def _town_doll(self, ui: dict, v: dict, g: dict, cursor_shelf, cur_row: int) -> None:
        X, Y = g["X"], g["Y"]
        u = g["u"]                                               # 인형도 첫 선반과 같이 1칸 내려간다
        ch = v["char"]
        self._tset(ui["name"], (X(80), Y(57) + u), text=str(ch.get("name") or ""))
        trait = str(ch.get("trait") or "")
        bits = [(trait + " 특성") if trait else ""]
        if ch.get("lives") is not None:
            bits.append("목숨 %d" % self._tint(ch.get("lives")))
        self._tset(ui["trait"], (X(80), Y(74) + u), text=" · ".join(b for b in bits if b))
        img = None
        try:
            img = self.bank.get("idle", 0, ch.get("key") or "hyunki", False, 2)
        except Exception:
            img = None
        if img is not None:
            iw, ih = img.width(), img.height()
            ix, iy = X(80) + (128 - iw) // 2, Y(224) + u - ih
            self._tset(ui["sprite"], (ix, iy), image=img)
        else:
            iw, ih, ix, iy = 128, 120, X(80), Y(104) + u
        slots = [sh["slot"] for sh in v["shelves"]] if v["tab"] in ("store", "shop") else list(SHELF_ORDER)
        cur_slot = cursor_shelf["slot"] if (cursor_shelf and cursor_shelf["kind"] in ("store", "shop")) else None
        for k, slot in enumerate(SHELF_ORDER):
            fx, fy = DOLL_DOTS.get(slot, (0.5, 0.5))
            cx, cy = ix + fx * iw, iy + fy * ih
            s = 9 if slot == cur_slot else 7
            self._tset(ui["dots"][k], (cx - s // 2, cy - s // 2, cx + s // 2, cy + s // 2), fill=SLOT_HUES.get(slot, T_MUTED), outline=T_GROUND)
            if slot == cur_slot:
                self._tset(ui["lead"], (cx, cy, X(214), g["row_y"](cur_row) + 16), fill=SLOT_HUES.get(slot, T_MUTED))
        cap = v["capacity"]
        self._tset(ui["eq_lbl"], (X(80), Y(240) + u), text="장착 %d/6" % cap["equipped"])
        equipped = v["equipped"]
        for k, slot in enumerate(SHELF_ORDER):
            hue = SLOT_HUES.get(slot, T_MUTED)
            x = X(148 + 10 * k)
            if isinstance(equipped.get(slot), dict):
                self._tset(ui["eq_sq"][k], (x, Y(236) + u, x + 7, Y(243) + u), fill=hue, outline="")
            else:
                self._tset(ui["eq_sq"][k], (x, Y(236) + u, x + 7, Y(243) + u), fill="", outline=_lerp_color(hue, T_PANEL, 0.5))
        self._tset(ui["cap_lbl"], (X(80), Y(256) + u), text="창고 %d/%d" % (cap["used"], cap["cap"]))
        n_ticks = min(24, max(1, cap["cap"]))
        for k in range(24):
            x = X(80 + 5 * k)
            if k >= n_ticks:
                continue
            if k < cap["used"]:
                self._tset(ui["cap_ticks"][k], (x, Y(264) + u, x + 3, Y(271) + u), fill=T_TEXT, outline="")
            else:
                self._tset(ui["cap_ticks"][k], (x, Y(264) + u, x + 3, Y(271) + u), fill="", outline=T_EDGE)

    def _town_shelf(self, p: dict, sh: dict, i: int, v: dict, g: dict, on: bool) -> None:
        X, Y = g["X"], g["Y"]
        y = g["row_y"](i)
        hue = sh["hue"]
        x0, x1 = X(216), X(1207)
        cur_col = v["cursor"]["col"] if on else -1
        # 카드 창: 커서 카드가 보이는 nv 장(기본 3, 좁은 띠 2/1) 안에 들게 민다 (창고/상점만 카드가 있다)
        nv = int(g.get("cards", 3))
        cards = sh["cards"]
        win = sh["window"]
        if on and cur_col > 0:
            if cur_col - 1 < win:
                win = cur_col - 1
            elif cur_col - 1 >= win + nv:
                win = cur_col - nv
        win = max(0, min(win, max(0, len(cards) - nv)))
        if on:
            self._tset(p["groove"], (x0, y - 1, x1, y + 31), fill=T_GROUND, outline="")
        # 선반턱: 커서 줄은 금색인데 스티커(부위색 통채움) 밑에는 깔지 않는다 — 안전모(노랑)와 금색이 한 색으로 읽히지 않게
        lips = T_LIP_ON if on else T_LIP
        lx = X(344) if on else x0
        self._tset(p["lip"][0], (lx, y + 32, x1, y + 32), fill=lips[0], outline="")
        self._tset(p["lip"][1], (lx, y + 33, x1, y + 35), fill=lips[1], outline="")
        self._tset(p["lip"][2], (lx, y + 36, x1, y + 38), fill=lips[2], outline="")
        # 라벨 스티커: 28px 부위색 탭(챔퍼 3) · 커서 줄은 통째로 부위색 (peel)
        tw = 120 if on else 28
        self._tset(p["tab"], (x0 + 3, y, x0 + tw, y, x0 + tw, y + 32, x0 + 3, y + 32, x0, y + 29, x0, y + 3), fill=hue)
        if not on:
            self._tset(p["box"], (x0, y, x0 + 119, y + 31), fill=T_CARD, outline=T_EDGE)
        self._tglyph(p["glyph"], sh["glyph"], x0 + 6, y + 8, 16, T_GROUND, hue)
        self._tset(p["label"], (x0 + 36, y + 11), text=sh["label"], fill=T_GROUND if on else T_TEXT)
        if sh["kind"] == "store":
            sub = "%s · 보관 %d" % (sh["effect_label"], sh["count"])
        elif sh["kind"] == "shop":
            sub = "%s · 재고 %d" % (sh["effect_label"], sh["count"])
        elif sh["kind"] == "stat":
            sub = self._town_stat_values(sh, v)[0]                  # 현재 값 (카드 오른쪽 Lv 와 중복되지 않게)
        else:
            sub = sh["effect_label"]
        if win > 0:                                               # 왼쪽으로 숨은 카드 수도 스티커에 (오른쪽 +N 과 짝)
            sub += " · ‹%d" % win
        self._tset(p["sub"], (x0 + 36, y + 24), text=self._fit(sub, -10, 82), fill=_lerp_color(T_GROUND, hue, 0.3) if on else T_MUTED)
        if sh["kind"] == "stat":                                  # 한 장짜리 랙: 빈 홈 셀 없이 카드 한 장을 넓게
            self._town_stat_card(p["card0"], sh, X(344), y, 408, on, cur_col == 0, v)
            return
        if sh["kind"] == "gamble":
            self._town_gamble_card(p["card0"], sh, X(344), y, 408, on, cur_col == 0, v, g)
            return
        # 0번 = 장착 카드(창고) / 비교 기준(상점) / 고스트
        eq = sh["equipped"]
        mode0 = "equip" if sh["kind"] == "store" else "base"
        self._town_card(p["card0"], X(344), y, 192, eq, mode0, on, cur_col == 0, sh, v)
        for k in range(nv):
            x, w = X(544 + TOWN_CARD_PITCH * k), 208
            if k == 0 and win > 0:                                # 왼쪽 ‹N 차선: 첫 카드를 20px 줄인다 (오른쪽 +N 차선과 대칭)
                x, w = x + 20, 188
            idx = win + k
            if idx < len(cards):
                self._town_card(p["cards"][k], x, y, w, cards[idx], "item", on, cur_col == idx + 1, sh, v)
            else:
                self._tset(p["cells"][k], (x, y, x + w - 1, y + 31), fill=T_GROUND, outline=T_CELL_EDGE)
        more = len(cards) - (win + nv)
        if more > 0:
            self._tset(p["more"], (X(1207), y + 16), text="+%d" % more, fill=T_TEXT if on else T_MUTED)
        if win > 0:
            self._tset(p["less"], (X(550), y + 16), text="‹%d" % win, fill=T_TEXT if on else T_MUTED)

    def _town_card(self, c: dict, x: float, y: float, w: int, eq, mode: str, on: bool, cursor: bool, sh: dict, v: dict) -> None:
        """장비 카드. mode: "equip"(창고 0번, 장착 도장) · "base"(상점 0번, 평평한 비교 기준) · "item"(창고/재고 카드)."""
        hue = sh["hue"]
        dim = (lambda col: col) if on else (lambda col: _lerp_color(col, T_PANEL, 0.25))
        if not isinstance(eq, dict):                              # 고스트: 빈 슬롯 실루엣
            if cursor:
                self._tset(c["box"], (x + 1, y + 1, x + w - 2, y + 30), fill=T_PANEL, outline=T_GOLD, width=2, dash="")
            else:
                self._tset(c["box"], (x, y, x + w - 1, y + 31), fill=T_PANEL, outline=T_EDGE if on else _lerp_color(T_EDGE, T_PANEL, 0.25),
                           width=1, dash=(3, 3))
            if c["glyph"] is not None:
                self._tglyph(c["glyph"], sh["glyph"], x + 10, y + 8, 16, _lerp_color(hue, T_PANEL, 0.5 if on else 0.6), T_PANEL)
            self._tset(c["name"], (x + 34, y + 11), text=self._fit("%s 없음" % sh["label"], -12, w - 40),
                       fill=T_MUTED if on else _lerp_color(T_MUTED, T_PANEL, 0.25), font=self._tfont(12, True))
            self._tset(c["price"], (x + 34, y + 24), text=self._fit("빈 슬롯 · %s 효과 없음" % sh["effect_label"], -10, w - 40),
                       fill=_lerp_color(T_MUTED, T_PANEL, 0.15 if on else 0.4), font=self._tfont(10, False))
            return
        rarity = eq.get("rarity") or "normal"
        rcol = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
        afford = True
        if mode == "item" and sh["kind"] == "shop":
            afford = bool(eq.get("afford", v["money"] >= self._tint(eq.get("price"))))
        if cursor:
            self._tset(c["box"], (x + 1, y + 1, x + w - 2, y + 30), fill=T_SEL, outline=T_GOLD, width=2, dash="")
            self._tset(c["chip"], (x + 2, y + 2, x + 4, y + 29), fill=dim(hue), outline="")
        elif mode == "base":
            self._tset(c["box"], (x, y, x + w - 1, y + 31), fill=T_FLAT, outline="", width=1, dash="")
            self._tset(c["chip"], (x + 1, y + 1, x + 3, y + 30), fill=dim(hue), outline="")
        else:
            self._tset(c["box"], (x, y, x + w - 1, y + 31), fill=T_CARD, outline=dim(rcol), width=1, dash="")
            self._tset(c["chip"], (x + 1, y + 1, x + 3, y + 30), fill=dim(hue), outline="")
        nx = x + 10
        if mode == "equip":
            self._tset(c["stamp"], (nx + 1, y + 4, nx + 29, y + 16), fill="", outline=dim(hue), width=2)
            self._tset(c["stamp_t"], (nx + 15, y + 10), text="장착", fill=dim(hue))
            nx += 34
        rx = x + w - 6
        lv_col = _lerp_color(T_TEXT, T_PANEL, 0.35) if mode == "base" else T_TEXT
        lv_txt = "Lv%d" % self._tint(eq.get("level"))
        self._tset(c["lv"], (rx, y + 10), text=lv_txt, fill=dim(lv_col))
        right = rx - self._tw(lv_txt, 10) - 4
        owned = self._tint(eq.get("owned"))
        if mode == "item" and owned > 0:
            tg = "보유 %d" % owned
            tgw = self._tw(tg, 10) + 8
            self._tset(c["tag"], (right - tgw, y + 3, right - 1, y + 16), fill=dim(T_EDGE), outline="")
            self._tset(c["tag_t"], (right - tgw / 2.0, y + 10), text=tg, fill=dim(T_TEXT))
            right -= tgw + 4
        ncol = rcol
        if mode == "base":
            ncol = _lerp_color(rcol, T_PANEL, 0.35)
        elif not afford:
            ncol = _lerp_color(rcol, T_PANEL, 0.5)
        self._tset(c["name"], (nx, y + 11), text=self._fit(eq.get("name") or "?", -12, max(20, right - nx)), fill=dim(ncol), font=self._tfont(12, True))
        # 2줄째: [가격] 효과 델타 · 힘/민/지 델타 (item) — 장착/기준 카드는 절대값.
        # 토큰 = (라벨, 값, 값 색, 굵게): 라벨("힘", "연사")은 흐린색, 값("+3", "+12%")만 색을 입혀 숫자가 줄무늬가 아니라 숫자로 읽힌다
        toks = []
        tx = x + 10
        if mode == "base":
            toks.append(("", "비교 기준", _lerp_color(T_MUTED, T_PANEL, 0.25), False))
        elif mode == "item" and sh["kind"] == "shop":
            toks.append(("", self._tmoney(eq.get("price")), T_TEXT if afford else T_NEG, True))
        ekey = sh["effect_key"]
        elabel = sh["effect_label"]
        fmt = "pct" if ekey in PCT_KEYS else "int"
        abs_col = _lerp_color(T_TEXT, T_PANEL, 0.25)
        if mode == "item":
            de = eq.get("delta_effect") if isinstance(eq.get("delta_effect"), dict) else {}
            d = self._fnum(de.get("after")) - self._fnum(de.get("now"))
            if abs(d) > 1e-9:
                toks.append((elabel, self._tfmt(d, fmt, sign=True), T_POS if d > 0 else T_NEG, True))
            ds = eq.get("delta_stats") if isinstance(eq.get("delta_stats"), dict) else {}
            stats = [(k, self._tint(ds.get(k))) for k in ("str", "agi", "int")]
            stats = [s for s in stats if s[1]]
            stats.sort(key=lambda s: -abs(s[1]))
            for k, d in stats:
                toks.append((STAT_SHORT[k], "%+d" % d, T_POS if d > 0 else T_NEG, True))
            for lb in (eq.get("perk_labels") or [])[:2]:
                off = str(lb).endswith(PERK_OFF_SUFFIX)               # 이 캐릭터가 못 쓰는 특전: 더 흐리게
                toks.append(("", str(lb), _lerp_color(T_MUTED, T_PANEL, 0.35) if off else T_MUTED, False))
        else:
            fx = eq.get("effect") if isinstance(eq.get("effect"), dict) else {}
            val = self._fnum(fx.get(ekey))
            if abs(val) > 1e-9:
                toks.append((elabel, self._tfmt(val, fmt, sign=True), abs_col, True))
            st = eq.get("stats") if isinstance(eq.get("stats"), dict) else {}
            for k in ("str", "agi", "int"):
                d = self._tint(st.get(k))
                if d:
                    toks.append((STAT_SHORT[k], "%+d" % d, abs_col, True))
        budget = x + w - 6 - tx
        lw = lambda t: (self._tw(t[0], 10, False) + 3) if t[0] else 0        # noqa: E731  라벨 폭 (+3px 틈)
        widths = [lw(t) + self._tw(t[1], 10, t[3]) for t in toks]
        gap = 6
        while toks and sum(widths) + gap * (len(toks) - 1) > budget:
            toks.pop()
            widths.pop()
            if toks:
                lb, t, col, b = toks[-1]
                toks[-1] = (lb, t + "…", col, b)
                widths[-1] = lw(toks[-1]) + self._tw(toks[-1][1], 10, b)
        for k, it in enumerate(c["tok"]):
            if k >= len(toks):
                break
            lb, t, col, b = toks[k]
            vx = tx
            if lb:
                self._tset(c["tokl"][k], (tx, y + 24), text=lb, fill=dim(T_MUTED))
                vx += lw(toks[k])
            self._tset(it, (vx, y + 24), text=t, fill=dim(col), font=self._tfont(10, b))
            tx += widths[k] + gap
        if len(toks) > 4:                                          # 풀은 4개: 넘치면 price 슬롯을 5번째로 (라벨+값 한 덩어리)
            lb, t, col, b = toks[4]
            self._tset(c["price"], (tx, y + 24), text=(lb + " " + t) if lb else t, fill=dim(col), font=self._tfont(10, b))

    def _town_stat_card(self, c: dict, sh: dict, x: float, y: float, w: int, on: bool, cursor: bool, v: dict) -> None:
        s = sh["stat"]
        hue = sh["hue"]
        dim = (lambda col: col) if on else (lambda col: _lerp_color(col, T_PANEL, 0.25))
        if cursor:
            self._tset(c["box"], (x + 1, y + 1, x + w - 2, y + 30), fill=T_SEL, outline=T_GOLD, width=2, dash="")
            self._tset(c["chip"], (x + 2, y + 2, x + 4, y + 29), fill=hue, outline="")
        else:
            self._tset(c["box"], (x, y, x + w - 1, y + 31), fill=T_CARD, outline=dim(T_EDGE), width=1, dash="")
            self._tset(c["chip"], (x + 1, y + 1, x + 3, y + 30), fill=dim(hue), outline="")
        maxed = s["max"] > 0 and s["level"] >= s["max"]
        lv_txt = ("Lv %d/%d" % (s["level"], s["max"])) if s["max"] > 0 else ("Lv %d" % s["level"])
        rx = x + w - 6
        self._tset(c["lv"], (rx, y + 10), text=lv_txt, fill=dim(T_TEXT))
        self._tset(c["name"], (x + 10, y + 11), text=self._fit(s["label"], -12, rx - self._tw(lv_txt, 10) - 4 - (x + 10)),
                   fill=dim(T_MUTED if maxed else T_TEXT), font=self._tfont(12, True))
        cost = "MAX" if maxed else (format(s["cost"], ",") + "점")   # 금색은 커서 테두리 · 헤더 ₩ 전용: 비용은 흰색 / 부족 빨강
        self._tset(c["price"], (x + 10, y + 24), text=cost, fill=dim(T_MUTED if maxed else (T_TEXT if s["afford"] else T_NEG)),
                   font=self._tfont(10, True))
        preview = "최대 단계" if maxed else self._town_stat_values(sh, v)[1]     # "12 → 13" (스티커의 '현재 12' 와 짝)
        if preview:
            self._tset(c["tok"][0], (x + 10 + self._tw(cost, 10) + 8, y + 24), text=preview, fill=dim(T_MUTED), font=self._tfont(10, False))

    def _town_stat_values(self, sh: dict, v: dict) -> tuple:
        """스탯 강화 항목의 (스티커 부제 = 현재 값, 카드 2줄째 = 강화 미리보기). 값은 hud.town.char 에서 온다."""
        key = sh["slot"]
        lv = self._tint(sh["stat"]["level"])
        ch = v["char"]
        st = ch.get("stats") if isinstance(ch.get("stats"), dict) else {}
        if key in st:
            n = self._tint(st.get(key))
            return "현재 %d" % n, "%d → %d" % (n, n + 1)
        if key == "rate":
            p = 20 * lv
            return "현재 +%d%%" % p, "+%d%% → +%d%%" % (p, p + 20)
        if key == "shield":
            sm = self._tint(ch.get("shield_max"))
            return "최대 %d" % sm, "%d → %d" % (sm, sm + 1)
        if key == "life":
            n = self._tint(ch.get("lives"))
            return "현재 %d" % n, "%d → %d" % (n, min(9, n + 1))
        return "Lv %d" % lv, ""

    def _town_gamble_card(self, c: dict, sh: dict, x: float, y: float, w: int, on: bool, cursor: bool, v: dict, g: dict) -> None:
        gm = sh["gamble"]
        hue = sh["hue"]
        dim = (lambda col: col) if on else (lambda col: _lerp_color(col, T_PANEL, 0.25))
        if cursor:
            self._tset(c["box"], (x + 1, y + 1, x + w - 2, y + 30), fill=T_SEL, outline=T_GOLD, width=2, dash="")
            self._tset(c["chip"], (x + 2, y + 2, x + 4, y + 29), fill=hue, outline="")
        else:
            self._tset(c["box"], (x, y, x + w - 1, y + 31), fill=T_CARD, outline=dim(T_EDGE), width=1, dash="")
            self._tset(c["chip"], (x + 1, y + 1, x + 3, y + 30), fill=dim(hue), outline="")
        i = gm["i"]
        nx, rx = x + 10, x + w - 6
        if i == 0:
            eq = gm["eq"]
            if isinstance(eq, dict):
                rcol = RARITY_COLORS.get(eq.get("rarity") or "normal", RARITY_COLORS["normal"])
                lv_txt = "Lv%d" % self._tint(eq.get("level"))
                self._tset(c["lv"], (rx, y + 10), text=lv_txt, fill=dim(T_TEXT))
                self._tset(c["name"], (nx, y + 11), text=self._fit(eq.get("name") or "?", -12, rx - self._tw(lv_txt, 10) - 4 - nx), fill=dim(rcol),
                           font=self._tfont(12, True))
                down = 1 if eq.get("rarity") == "unique" else 3
                self._tset(c["price"], (nx, y + 24), text="비용 " + self._tmoney(gm["cost"]), fill=dim(T_TEXT if v["money"] >= gm["cost"] else T_NEG),
                           font=self._tfont(10, True))
                self._tset(c["tok"][0], (nx + self._tw("비용 " + self._tmoney(gm["cost"]), 10) + 6, y + 24),
                           text="60%% ↑2 · 30%% – · 10%% ↓%d" % down, fill=dim(T_MUTED), font=self._tfont(10, False))
            else:
                self._tset(c["name"], (nx, y + 11), text="장착한 장비 없음", fill=dim(T_MUTED), font=self._tfont(12, True))
                self._tset(c["price"], (nx, y + 24), text="창고 탭에서 장비를 장착하세요", fill=dim(_lerp_color(T_MUTED, T_PANEL, 0.3)), font=self._tfont(10, False))
        elif i == 1:
            mult = max(1, 2 ** min(gm["streak"], 3))
            self._tset(c["name"], (nx, y + 11), text="판돈 " + self._tmoney(gm["stake"]), fill=dim(T_TEXT), font=self._tfont(12, True))
            self._tset(c["lv"], (rx, y + 10), text="연속 ×%d" % mult, fill=dim(T_POS if gm["streak"] else T_TEXT))
            self._tset(c["price"], (nx, y + 24), text="50% 로 두 배 · 연속 성공 최대 ×8", fill=dim(T_MUTED), font=self._tfont(10, False))
        else:
            self._tset(c["name"], (nx, y + 11), text="판돈 " + self._tmoney(gm["bet"]), fill=dim(T_TEXT), font=self._tfont(12, True))
            txt = gm["text"] or "7 7 7 ×30 + 유니크 · ₩₩₩ ×10 · ★★★ 레어"
            self._tset(c["price"], (nx, y + 24), text=self._fit(txt, -10, w - 120), fill=dim(T_MUTED), font=self._tfont(10, False))
            reels = gm["reels"]
            now = g["now"]
            for j, (box, txt_it) in enumerate(self.town_ui["reels"]):
                bx = rx - 26 * (3 - j) + 2
                spinning = not reels or j >= len(reels)
                if spinning:
                    sym = SLOT_SYMBOLS[int(now * 14 + j * 2) % len(SLOT_SYMBOLS)]
                    col = _lerp_color(T_MUTED, T_PANEL, 0.5 if int(now * 28 + j) % 2 else 0.2)
                else:
                    sym = str(reels[j])
                    col = {"7": T_NEG, "★": T_GOLD, "₩": T_POS, "◆": "#4cc9f0", "♥": T_NEG}.get(sym, T_TEXT)
                self._tset(box, (bx, y + 4, bx + 23, y + 27), fill=T_GROUND, outline=dim(T_EDGE))
                self._tset(txt_it, (bx + 12, y + 16), text=sym, fill=dim(col))

    def _town_compare_empty(self, cp: dict, v: dict, g: dict) -> None:
        """compare 가 None(창고 고스트 / 재고 없는 상점 선반)일 때: 오른쪽 칸이 통째로 비지 않게 빈 비교표 틀 + 슬롯 이름 + 안내 한 줄."""
        row = v["cursor"]["row"]
        shelves = v["shelves"]
        if v["on_next"] or v["on_box"] or row >= len(shelves) or shelves[row]["kind"] not in ("store", "shop"):
            return
        sh = shelves[row]
        X, Y = g["X"], g["Y"]
        x0, y0 = X(1216), Y(46) + g["u"]
        h = 240 + 6 * g["u"]
        hue = _lerp_color(sh["hue"], T_PANEL, 0.45)
        self._tset(cp["box"], (x0, y0, x0 + 303, y0 + h - 1), fill=T_CARD, outline=T_EDGE)
        self._tset(cp["stripe"], (x0 + 1, y0 + 1, x0 + 302, y0 + 3), fill=hue, outline="")
        title = ("%s 없음" if sh["kind"] == "store" else "%s 재고 없음") % sh["label"]
        self._tset(cp["name"], (x0 + 12, y0 + 17), text=self._fit(title, -14, 280), fill=T_MUTED)
        self._tglyph(cp["glyph"], sh["glyph"], x0 + 12, y0 + 27, 12, hue, T_CARD)
        self._tset(cp["sub2"], (x0 + 28, y0 + 33), text=sh["label"] + " 슬롯", fill=hue)
        self._tset(cp["rules"][0], (x0 + 12, y0 + 58, x0 + 291, y0 + 58), fill=T_EDGE, outline="")
        n = sh["count"]
        if sh["kind"] == "store":
            lines = (("빈 슬롯 · %s 효과 없음" % sh["effect_label"]),
                     ("→ 창고 카드 %d장 중 하나를 고르면 비교표가 뜹니다" % n) if n else "창고에 해당 장비 없음 · 상점에서 사면 바로 장착")
        else:
            lines = ("이번 마을에는 재고가 없습니다", "↑↓ 다른 선반 · 랜덤박스에서 나올 수도 있습니다")
        self._tset(cp["hdr"][0], (x0 + 12, y0 + 72), text=self._fit(lines[0], -10, 280))
        self._tset(cp["after_msg"], (x0 + 12, y0 + 226), text=self._fit(lines[1], -10, 280))

    def _town_compare(self, cp: dict, v: dict, g: dict) -> None:
        cmp_ = v["compare"]
        if not isinstance(cmp_, dict):
            self._town_compare_empty(cp, v, g)
            return
        X, Y = g["X"], g["Y"]
        x0, y0 = X(1216), Y(46) + g["u"]
        h = 240 + 6 * g["u"]
        self._tset(cp["box"], (x0, y0, x0 + 303, y0 + h - 1), fill=T_CARD, outline=T_EDGE)
        rarity = cmp_.get("rarity") or "normal"
        rcol = RARITY_COLORS.get(rarity, RARITY_COLORS["normal"])
        action = cmp_.get("action") or "equip"
        slot = cmp_.get("slot")
        hue = SLOT_HUES.get(slot) or TOWN_STAT_HUES.get(slot) or (TOWN_GAMBLE_HUES[self._tint(str(slot)[1:])] if str(slot).startswith("g") and str(slot)[1:].isdigit() else T_MUTED)
        stripe = rcol if action in ("equip", "unequip", "buy") else hue
        self._tset(cp["stripe"], (x0 + 1, y0 + 1, x0 + 302, y0 + 3), fill=stripe, outline="")
        self._tset(cp["name"], (x0 + 12, y0 + 17), text=self._fit(cmp_.get("name") or "—", -14, 280), fill=stripe)
        # 부제: 글리프 · 희귀도 · Lv · 슬롯
        gx = x0 + 12
        glyph = cmp_.get("glyph") if cmp_.get("glyph") in TOWN_GLYPHS else (slot if slot in TOWN_GLYPHS else ("box" if action == "box" else None))
        if glyph is None and str(slot).startswith("g") and str(slot)[1:].isdigit():
            glyph = self.TOWN_GAMBLE_GLYPHS[int(str(slot)[1:]) % 3]
        if glyph:
            self._tglyph(cp["glyph"], glyph, gx, y0 + 27, 12, hue, T_CARD)
            gx += 16
        parts = []
        if action in ("equip", "unequip", "buy"):
            parts.append(RARITY_LABEL.get(rarity, str(rarity)))
        if cmp_.get("level") is not None:
            parts.append("Lv%d" % self._tint(cmp_.get("level")))
        sub1 = (" · ".join(parts) + " · ") if parts else ""
        self._tset(cp["sub1"], (gx, y0 + 33), text=sub1)
        gx += self._tw(sub1, 10, False)
        slot_label = str(cmp_.get("slot_label") or SLOT_LABEL.get(slot, ""))
        self._tset(cp["sub2"], (gx, y0 + 33), text=(slot_label + (" 슬롯" if action in ("equip", "unequip", "buy") else "")), fill=hue)
        cols = cmp_.get("cols") if isinstance(cmp_.get("cols"), (list, tuple)) and len(cmp_.get("cols")) >= 3 else \
            ("현재", self.TOWN_AFTER_LABEL.get(action, "장착 후"), "변화")
        hx = (x0 + 12, X(1368), X(1440), X(1508))
        rows = [r for r in (cmp_.get("rows") or []) if isinstance(r, dict)][:4]
        if rows:
            for k, it in enumerate(cp["hdr"]):
                self._tset(it, (hx[k], y0 + 49), text=("능력치" if k == 0 else str(cols[k - 1])))
            self._tset(cp["rules"][0], (x0 + 12, y0 + 58, x0 + 291, y0 + 58), fill=T_EDGE, outline="")
        for k, r in enumerate(rows):
            p = cp["rows"][k]
            ry = y0 + 72 + 22 * k
            fmt = r.get("fmt") or ("pct" if str(r.get("label")) in PCT_LABELS else "int")
            lx = x0 + 12
            if k == 3 and glyph and action in ("equip", "unequip", "buy"):
                self._tglyph(p["glyph"], glyph, lx, ry - 6, 12, hue, T_CARD)
                lx += 16
            self._tset(p["label"], (lx, ry), text=str(r.get("label") or ""), fill=T_TEXT if k == 3 else T_MUTED)
            self._tset(p["now"], (hx[1], ry), text=self._tfmt(r.get("now"), fmt))
            d = r.get("delta")
            dn = None
            if not isinstance(d, str):
                dn = self._fnum(d) if d is not None else 0.0
            changed = (dn is not None and abs(dn) > 1e-9) or (isinstance(d, str) and d not in ("", "·"))
            col = T_TEXT
            if dn is not None and abs(dn) > 1e-9:
                col = T_POS if dn > 0 else T_NEG
            elif isinstance(d, str) and d.startswith("-"):
                col = T_NEG
            elif isinstance(d, str) and d.startswith("+"):
                col = T_POS
            self._tset(p["after"], (hx[2], ry), text=self._tfmt(r.get("after"), fmt), fill=col if changed else T_TEXT, font=self._tfont(12, changed))
            dtxt = d if isinstance(d, str) else (self._tfmt(dn, fmt, sign=True) if (dn is not None and abs(dn) > 1e-9) else "·")
            self._tset(p["delta"], (hx[3], ry), text=dtxt, fill=col if changed else T_EDGE, font=self._tfont(12, changed))
        # 특전 칩 + 설명 한 줄: 장비(장착/해제/구매)와 특전이 있는 강화 도박에만. 스탯/도박/다음/상자는 특전 구역을 접고
        # 가격 줄을 22px 끌어올린다 ('특전 —' 같은 빈 줄 금지)
        perks = [p for p in (cmp_.get("perks") or []) if isinstance(p, dict)][:2]
        gear = action in ("equip", "unequip", "buy")
        show_perks = bool(perks) or (gear and bool(rows))
        if show_perks:
            self._tset(cp["rules"][1], (x0 + 12, y0 + 152, x0 + 291, y0 + 152), fill=T_EDGE, outline="")
            self._tset(cp["perk_lbl"], (x0 + 12, y0 + 166), text="특전")
        cx = x0 + 44
        for k, (rect, txt) in enumerate(cp["chips"]):
            if k >= len(perks):
                break
            lb = self._fit(str(perks[k].get("label") or ""), -10, max(24, x0 + 291 - cx - 8))
            off = lb.endswith(PERK_OFF_SUFFIX)                        # 이 캐릭터가 못 쓰는 특전: 칩을 흐리게
            cw = self._tw(lb, 10) + 8
            self._tset(rect, (cx, y0 + 158, cx + cw - 1, y0 + 173), fill=_lerp_color(T_EDGE, T_PANEL, 0.4) if off else T_EDGE, outline="")
            self._tset(txt, (cx + cw / 2.0, y0 + 166), text=lb, fill=_lerp_color(T_MUTED, T_PANEL, 0.3) if off else T_TEXT)
            cx += cw + 4
        if perks:
            ptxt = " · ".join(str(p.get("text") or "") for p in perks if p.get("text"))
            self._tset(cp["perk_txt"], (x0 + 44, y0 + 182), text=self._fit(ptxt, -10, 248), fill="#a3acbc")
        elif show_perks:
            self._tset(cp["perk_txt"], (x0 + 44, y0 + 166), text="없음", fill=_lerp_color(T_MUTED, T_PANEL, 0.3))
        py = 208 if show_perks else 186                            # 가격 줄 y (특전 구역이 없으면 22px 위로)
        self._tset(cp["rules"][2], (x0 + 12, y0 + py - 14, x0 + 291, y0 + py - 14), fill=T_EDGE, outline="")
        # 가격 줄: 판매 · 강화 / 구매 · 잔액 / 비용 · 잔여
        unit = str(cmp_.get("unit") or ("점" if action == "stat" else ""))
        money = v["money"]
        fmt_cost = (lambda n: format(self._tint(n), ",") + unit) if unit else self._tmoney
        afford = bool(cmp_.get("afford", True))
        p1 = p2 = None
        if action == "equip":
            p1 = ("판매", fmt_cost(cmp_.get("sell")), T_TEXT) if cmp_.get("sell") is not None else None
            p2 = ("장착 후 강화 " + fmt_cost(cmp_.get("enhance")), "", T_MUTED) if cmp_.get("enhance") is not None else None
        elif action == "unequip":
            if cmp_.get("enhance") is not None:
                p1 = ("강화", fmt_cost(cmp_.get("enhance")), T_GOLD if money >= self._tint(cmp_.get("enhance")) else T_NEG)
            p2 = ("판매가 " + fmt_cost(cmp_.get("sell")), "", T_MUTED) if cmp_.get("sell") is not None else None
        elif action == "buy" or action == "box":
            cost = self._tint(cmp_.get("buy"))
            ok = afford and money >= cost
            p1 = ("구매", fmt_cost(cost), T_GOLD if ok else T_NEG)
            p2 = ("잔액", fmt_cost(money - cost), T_TEXT) if ok else ("부족", fmt_cost(cost - money), T_NEG)
        elif action == "stat":
            cost = self._tint(cmp_.get("buy"))
            ok = afford and v["score"] >= cost
            p1 = ("비용", fmt_cost(cost), T_GOLD if ok else T_NEG)
            p2 = ("잔여", fmt_cost(v["score"] - cost), T_TEXT) if ok else ("부족", fmt_cost(cost - v["score"]), T_NEG)
        elif action == "gamble":
            cost = self._tint(cmp_.get("buy"))
            p1 = ("판돈", fmt_cost(cost), T_GOLD if money >= cost else T_NEG)
            p2 = ("잔액", fmt_cost(money), T_TEXT)
        if p1:
            self._tset(cp["p1_lbl"], (x0 + 12, y0 + py), text=p1[0])
            self._tset(cp["p1_val"], (x0 + 12 + self._tw(p1[0], 10, False) + 4, y0 + py), text=p1[1], fill=p1[2])
        if p2:
            if p2[1]:
                self._tset(cp["p2_val"], (X(1508), y0 + py), text=p2[1], fill=p2[2])
                self._tset(cp["p2"], (X(1508) - self._tw(p2[1], 12) - 4, y0 + py), text=p2[0])
            else:
                self._tset(cp["p2"], (X(1508), y0 + py), text=p2[0])
        self._tset(cp["after_msg"], (x0 + 12, y0 + py + 18), text=self._fit(str(cmp_.get("after_msg") or ""), -10, 280))

    def _town_msg_segments(self, msg: str, v: dict) -> list:
        """푸터 메시지 → [(kind, text)]: "key"(키캡) · "tag"(슬롯 태그, hue) · "text"."""
        labels = {}
        for sh in v["shelves"]:
            labels[sh["label"]] = sh["hue"]
        for k, lb in SLOT_LABEL.items():
            labels.setdefault(lb, SLOT_HUES.get(k, T_MUTED))
        out = []
        for chunk in re.split(r"(\[[^\]]+\])", msg):
            if not chunk:
                continue
            if chunk.startswith("[") and chunk.endswith("]"):
                inner = chunk[1:-1]
                if inner in labels:
                    out.append(("tag", inner, labels[inner]))
                elif inner in self.TOWN_KEYS:
                    out.append(("key", inner, None))
                else:
                    out.append(("text", chunk, None))
                continue
            for j, piece in enumerate(chunk.split(" · ")):
                if j:
                    out.append(("text", " · ", None))
                m = re.match(r"^(Enter|Space|Tab|Esc|←→|↑↓|[←→↑↓C])\s+", piece)
                if m:
                    out.append(("key", m.group(1), None))
                    piece = piece[m.end():]
                if piece:
                    out.append(("text", piece, None))
        return out

    def _town_footer(self, ui: dict, v: dict, g: dict) -> None:
        X, Y = g["X"], g["Y"]
        fy = Y(296) + g["extra"]
        # 키 범례 (왼쪽)
        x = X(80)
        for k, (kc, verb) in enumerate(ui["legend"]):
            if k >= len(v["legend"]):
                break
            entry = v["legend"][k]
            try:
                key, vb = str(entry[0]), str(entry[1])
            except (TypeError, IndexError, KeyError):
                continue
            kw = self._tkeycap(kc, x, fy + 8, key)
            self._tset(verb, (x + kw + 6, fy + 16), text=vb)
            x += kw + 6 + self._tw(vb, 11, False) + 14
        # 랜덤박스 줄 (상점)
        right = X(1520)
        if v["box"]:
            b = v["box"]
            br = ui["boxrow"]
            on = v["on_box"]
            bx, by = X(1216), fy
            if on:
                self._tset(br["box"], (bx + 1, by + 1, bx + 302, by + 30), fill=T_SEL, outline=T_GOLD, width=2)
            else:
                self._tset(br["box"], (bx, by, bx + 303, by + 31), fill=T_CARD, outline=T_EDGE, width=1)
            self._tkeycap(br["key"], bx + 8, by + 7, "Enter" if on else "↓", fg=T_GOLD if on else T_TEXT, edge=T_GOLD if on else T_EDGE)
            self._tglyph(br["glyph"], "box", bx + 44 + (12 if on else 0), by + 8, 16, T_TEXT, T_SEL if on else T_CARD)
            nx = bx + 68 + (12 if on else 0)
            self._tset(br["name"], (nx, by + 11), text=b["label"], fill=T_TEXT)
            self._tset(br["sub"], (nx, by + 24), text=b["sub"])
            self._tset(br["price"], (bx + 296, by + 16), text=self._tmoney(b["price"]), fill=T_TEXT if b["afford"] else T_NEG)
            right = X(1200)
        else:
            # 다음 스테이지 카드 (창고/스탯/도박장): "다음" 줄의 몸통 커서 — 커서가 오면 금색 통채움 + 바탕색 글자 (peel)
            nr = ui["nextrow"]
            on = v["on_next"]
            bx, by = X(1216), fy
            if on:
                self._tset(nr["box"], (bx + 1, by + 1, bx + 302, by + 30), fill=T_GOLD, outline=T_GOLD, width=2)
                kw = self._tkeycap(nr["key"], bx + 8, by + 7, "Enter", fg=T_GOLD, bg=T_GROUND, edge=T_GROUND)
                self._tset(nr["name"], (bx + 16 + kw, by + 11), text="다음 스테이지 ▶", fill=T_GROUND, font=self._tfont(12, True))
                self._tset(nr["sub"], (bx + 16 + kw, by + 24), text=("%d스테이지 시작" % (v["stage"] + 1)) if v["stage"] else "Enter 로 출발",
                           fill=_lerp_color(T_GROUND, T_GOLD, 0.3))
            else:
                self._tset(nr["box"], (bx, by, bx + 303, by + 31), fill=T_CARD, outline=T_EDGE, width=1)
                kw = self._tkeycap(nr["key"], bx + 8, by + 7, "Esc", fg=T_TEXT, bg=T_CARD, edge=T_EDGE)
                self._tset(nr["name"], (bx + 16 + kw, by + 11), text="다음 스테이지 ▶", fill=T_TEXT, font=self._tfont(12, True))
                self._tset(nr["sub"], (bx + 16 + kw, by + 24), text=("%d스테이지 시작 · Esc 로 선택" % (v["stage"] + 1)) if v["stage"] else "Esc 로 선택",
                           fill=T_MUTED)
            right = X(1200)
        # 컨텍스트 메시지 (오른쪽 정렬, 슬롯 태그 + 키캡)
        segs = self._town_msg_segments(v["msg"], v)[:len(ui["msg"])]
        widths = []
        for kind, text, hue in segs:
            if kind == "key":
                widths.append(self._tw(text, 10) + 8 + 4)
            elif kind == "tag":
                widths.append(self._tw(text, 10) + 8 + 4)
            else:
                widths.append(self._tw(text, 11, False))
        total = sum(widths)
        max_w = right - (x + 8)
        while segs and total > max_w:                              # 넘치면 앞의 조각부터 버린다 (핵심은 뒤쪽)
            segs.pop(0)
            total -= widths.pop(0)
        sx = right - total
        for k, (kind, text, hue) in enumerate(segs):
            rect, txt = ui["msg"][k]
            if kind == "key":
                self._tkeycap((rect, txt), sx, fy + 8, text)
            elif kind == "tag":
                w = self._tw(text, 10) + 8
                self._tset(rect, (sx, fy + 9, sx + w - 1, fy + 22), fill=hue, outline="")
                self._tset(txt, (sx + w / 2.0, fy + 16), text=text, fill=T_GROUND, font=self._tfont(10, True), anchor="center")
            else:
                self._tset(txt, (sx, fy + 16), text=text, fill=T_TEXT, font=self._tfont(11, False), anchor="w")
            sx += widths[k]


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
                               on_toggle=self._on_toggle, on_quit=self.quit, on_escape=self._on_escape)
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
                    rec["data"] = {"stages": _config_version(self.stages), "config": _config_version(self.config)}   # v2.1
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

    def _on_escape(self) -> None:
        """Esc (overlay logical key "quit"): in the town the first press is the "다음 스테이지" shortcut — the cursor jumps
        onto the exit row and Enter confirms (the header / footer keycap says Esc); a second Esc on that row quits like
        everywhere else. A window-close request (WM_DELETE_WINDOW) goes straight to quit() via Overlay.on_quit."""
        w = self.world
        if w.state == "town" and getattr(w, "town", None) is not None:
            try:
                on_next = w.town["cursor"]["row"] == len(w._town_list(w._town_tab())) - 1
            except (KeyError, TypeError, AttributeError):
                on_next = False
            if not on_next:
                w.key_down("escape")
                w.key_up("escape")
                return
        self.quit()

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
    except Exception as ex:
        # 핫키 등록 실패(RuntimeError)·깨진 cache.dat/config.json 등: 콘솔 없이 실행되므로 메시지 박스로 안내 (조용히 죽지 않게)
        try:
            import ctypes
            text = str(ex) if isinstance(ex, RuntimeError) else "%s: %s" % (type(ex).__name__, ex)
            ctypes.windll.user32.MessageBoxW(0, text, "MolGam", 0x10)
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
