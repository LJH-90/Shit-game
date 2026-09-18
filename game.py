# -*- coding: utf-8 -*-
"""
game.py — MolGam pure game logic (entities, physics, waves, stages, bosses, score, save).

No tkinter import. Contract: INTERFACES.md section C.
    python game.py --selftest   -> headless verification, exit 0 on success.

Coordinate system: band-local pixels, origin top-left, y grows downward.
Entity x,y = feet-centre anchor (drawing layer offsets via sprites.anchor()).
"""
from __future__ import annotations

import json
import math
import os
import random
import sys

try:                                   # v1.9 economy contract (INTERFACES.md). Missing -> minimal stand-in below.
    import economy
except ImportError:                    # pragma: no cover
    economy = None

CHAR_KEYS = ["jaehwi", "hyunki", "dongil", "masked"]   # "masked" is hidden until unlocked

# ---------------------------------------------------------------- constants
GRAVITY = 1800.0
WALK_SPEED = 220.0
JUMP_VEL = 620.0
BULLET_SPEED = 700.0
ENEMY_BULLET_SPEED = 320.0
FIRE_RATE = 6.0                 # player shots / s (base)
PLAYER_W, PLAYER_H = 12, 28   # 그리기 배율 1x 스프라이트(약 14x30px) 기준 히트박스
ENEMY_W, ENEMY_H = 12, 28
SHIELD_INV = 0.6                # s of invincibility after a shield charge absorbs a hit
MELEE_CD = 0.35                 # s between melee strikes (config "melee.cooldown" overrides)
MELEE_KNOCK_BOSS = 0.3          # bosses are shoved this fraction of the knockback
ZONE_H = 120                    # height of a skill zone above the ground
MAX_ZONES = 3
ULT_T = 1.0                     # v2.0: ultimate portrait burst (C skill) — grow, hold, vanish in about a second
DEFAULT_UNLOCK_STAGE = 5
DEFAULT_SHOP = {                # key: [label, base cost, cost growth per level, max level (0 = unlimited)]
    "str": ["힘 +1", 1500, 1.25, 0],
    "agi": ["민첩 +1", 1500, 1.25, 0],
    "int": ["지혜 +1", 1500, 1.25, 0],
    "rate": ["연사 +20%", 2500, 1.6, 5],
    "shield": ["실드 +1", 4000, 1.8, 3],
    "life": ["목숨 +1", 5000, 2.0, 3],
}
SHOP_ORDER = ("str", "agi", "int", "rate", "shield", "life", "next")
STAT_KEYS = ("agi", "str", "int")
MAX_ENEMIES, MAX_BULLETS, MAX_EFFECTS = 14, 400, 30   # v1.9: bullets effectively unlimited (enemy fire only capped)
DASH_SPEED = 520.0
STAMP_SPEED = 450.0
MISSILE_SPEED = 700.0           # v1.9: slower + tighter turn so missiles curl back instead of leaving the band
MISSILE_TURN = 14.0             # rad/s
SPREAD_ANGLE = 0.0436           # rad (±2.5°) between the three spread shots
PROJ_ANIM_FPS = 8               # sprite projectiles ("proj" anim) advance at a fixed rate
ITEM_TTL = 9.0                  # s an item stays on the floor
ITEM_KINDS = ("laser", "homing", "spread", "rapid", "life", "bomb", "coffee", "decoy", "drone", "dog", "coin")
ITEM_LABEL = {"laser": "레이저", "homing": "유도탄", "spread": "3연발", "rapid": "속사", "life": "1UP",
              "bomb": "결재 폭탄", "coffee": "야근 커피", "decoy": "분신", "drone": "보안 드론", "dog": "찹츄",
              "coin": "₩"}
ITEM_DROP_WEIGHT = {"laser": 4, "homing": 4, "spread": 4, "rapid": 4, "life": 1, "bomb": 2, "coffee": 2,
                    "decoy": 1.5, "drone": 1.5, "dog": 1.5}
WEAPON_TIME = {"laser": 10.0, "spread": 12.0, "rapid": 12.0}
HOMING_AMMO = 25
MAX_ITEMS = 10
INV_SLOTS = 5                   # v1.9: inventory slots (keys 1..5)
INV_STACK = 3                   # max count per slot
INV_FLASH_T = 0.4
BOMB_BOSS_FRAC = 0.15           # 결재 폭탄: bosses lose this fraction of max hp, grunts/elites die
COFFEE_T = 6.0                  # 야근 커피: slow duration
SLOW_FACTOR = 0.4               # enemies / enemy bullets run at this fraction of speed while slowed
DECOY_T, DECOY_HP, DECOY_FIRE = 8.0, 3, 0.25
DRONE_T, DRONE_FIRE = 15.0, 0.33
DOG_T, DOG_SPEED, DOG_DMG, DOG_KNOCK, DOG_CD = 10.0, 260.0, 2, 200.0, 0.6
COIN_TTL = 12.0
COIN_HOME_DELAY, COIN_HOME_SPEED = 0.5, 520.0
ENEMY_REACH_PAD = 22.0          # enemy melee reach = w*0.6 + this
ENEMY_ATTACK_T = 0.45
ENEMY_HIT_WINDOW = (0.15, 0.30)
ENEMY_MELEE_CD = (1.0, 1.6)
BOMB_FUSE = 0.8                 # bomber projectile: seconds on the ground before it blasts
BLAST_T = 0.3                   # a "blast" bullet grows from 0 to r over this time and then dies
BOSS_JUMP_ODDS = 1.0 / 6.0      # brawler bosses: jump 1 : dash 5
BRAWLER_DASH_T = 0.4
WORDS_PER_STAGE = 2
WORD_VY = 34.0
WORD_KINDS = ("wipe", "gear", "money", "life")
WORD_WEIGHTS = {"wipe": 4, "gear": 3, "money": 4, "life": 1}
WORD_BANK = {   # lowercase, no z x c p u (bound to game keys)
    "wipe": ["fire", "retire", "audit", "layoff", "storm", "delete", "erase", "boom", "sweep", "kaboom"],
    "gear": ["bonus", "golden", "reward", "loot", "gift", "shiny", "legend", "trophy", "jewel", "medal"],
    "money": ["salary", "money", "gold", "bonus", "wage", "invoice", "refund", "dollar", "won", "wealth"],
    "life": ["heal", "life", "revive", "medkit", "hero", "smile", "rest", "holiday"],
}
WORD_LETTERS = set("abdefghijklmnoqrstvwy")
BALANCE_LOG_MAX = 200
TOWN_EVERY = 5                  # a town (equipment shop / warehouse / gambling) after every 5th stage
TOWN_TABS = ("stat", "shop", "store", "gamble")
TOWN_TAB_LABEL = {"stat": "스탯 강화", "shop": "장비 상점", "store": "창고", "gamble": "도박장"}
GAMBLE_GAMES = ("강화 도박", "더블업", "슬롯")
DOUBLE_STAKES = (0.10, 0.25, 0.50)      # fraction of money staked per 더블업 round
SLOT_BETS = (100, 500, 2000)
TOWN_HINT = {"stat": "←→ 항목 · Enter 구매 · Tab 탭",
             "shop": "←→ 항목 · Enter 구매 · Tab 탭",
             "store": "←→ 항목 · Enter 장착/해제 · C 판매 · ↑↓ 줄 전환 · Tab 탭",
             "gamble": "←→ 게임 · Enter 플레이 · C 대상/배팅 변경 · Tab 탭"}
DEFAULT_PROGRESSION = {"hp_per_stage": 0.35, "boss_hp_per_stage": 0.08, "drop_grunt": 0.10, "drop_elite": 0.30}

# --- v1.6: stats / elements / mid bosses
ELEMENT_KEYS = ["cheongryong", "baekho", "jujak", "hyeonmu"]      # 청룡 · 백호 · 주작 · 현무
DEFAULT_ELEMENTS = {   # 상성: 청룡→현무→주작→백호→청룡 (앞이 뒤를 이김)
    "cheongryong": {"name": "청룡", "color": "#22c55e", "beats": "hyeonmu"},
    "baekho": {"name": "백호", "color": "#e5e7eb", "beats": "cheongryong"},
    "jujak": {"name": "주작", "color": "#ef4444", "beats": "baekho"},
    "hyeonmu": {"name": "현무", "color": "#3b82f6", "beats": "jujak"},
}
DEFAULT_ELEMENT_MULT = {"strong": 1.5, "weak": 0.5}
STAT_BASE = 5                   # stats are 1..10, 5 = neutral
SPEED_PER_AGI = 0.06            # move-speed multiplier = 1 + SPEED_PER_AGI * (agi - STAT_BASE)
JUMP_PER_AGI = 0.04             # jump multiplier      = 1 + JUMP_PER_AGI * (agi - STAT_BASE)
BULLET_PER_INT = 0.08           # bullet speed = BULLET_SPEED * (1 + BULLET_PER_INT * (int - STAT_BASE)); not laser

# --- v1.7: equipment (granted by a department stage's final boss; levels unlimited)
EQUIP_ORDER = ("hat", "gloves", "suit", "shoes")     # tie order when picking the lowest-level slot
DEFAULT_EQUIPMENT = {
    "hat": {"label": "안전모", "shield": 1},
    "gloves": {"label": "작업 장갑", "rate": 0.2},
    "suit": {"label": "사신 정장", "magic": 1},
    "shoes": {"label": "운동화", "speed": 0.12, "jump": 0.08},
}
EQUIP_BANNER_T = 2.0
MID_BANNER_T = 1.5
BRAWLER_ATTACK_T = 0.5          # s an attack / attack2 animation lasts
BRAWLER_HIT_WINDOW = (0.15, 0.35)   # contact damage window inside the melee attack
BRAWLER_HURT_T = 0.25
BRAWLER_HURT_CD = 1.5           # min s between hurt staggers (no stun-lock)
BRAWLER_JUMP_DIST = 260.0       # jump toward the player only when farther than this

# --- v1.8: tempo (enemies x2, +10 %/stage; spawn / wave gaps halved) and motion variety
ENEMY_SPEED_BASE = 2.0          # every enemy move speed (grunt / elite / boss) x2
ENEMY_SPEED_PER_STAGE = 0.10    # compound +10 % per stage on top of ENEMY_SPEED_BASE
ENEMY_SPEED_STAGE_CAP = 3.0     # the per-stage factor stops growing here (stage 13+)
WAVE_GAP = 0.5                  # s between the last kill of a wave and the next wave
BOSS_GAP = 0.5                  # s before a (mid) boss walks in
BOSS_NEXT_GAP = 0.6             # s between consecutive bosses of an executive stage
CLEAR_TO_SHOP = 1.0             # s the STAGE CLEAR pose is held before the shop opens
SPRINT_MULT = 1.9               # sprint burst speed factor (run anim plays faster too)
MOVE_T = {"walk": (0.8, 1.8), "sprint": (0.45, 0.9), "pause": (0.35, 0.8)}   # s per movement mode
MOVE_WEIGHTS = (("walk", 55), ("sprint", 25), ("pause", 20))
WARN_T = {"ground": 0.9, "sky": 1.0}     # s a spawn warning is shown before the enemy appears
SPECIAL_SPAWN_BASE = 0.15       # chance a wave slot bursts from the ground / drops from the sky (stage 1)
SPECIAL_SPAWN_PER_STAGE = 0.05
SPECIAL_SPAWN_MAX = 0.55
SPAWN_KEEP_OUT = 110.0          # px: no ground / sky spawn this close to the player
LAND_STUN = 0.3                 # s an enemy stands still after a drop / burst landing
POP_EXTRA = 40.0                # px a ground burst rises above the floor
SKY_Y = -60.0                   # spawn height (band-local) of a sky drop: fully above the band

ANIM_FPS = {"idle": 6, "run": 12, "jump": 1, "fall": 1, "shoot": 10, "shoot_run": 12,
            "crouch": 6, "crouch_shoot": 10, "death": 8, "victory": 6,
            "attack": 10, "attack2": 10, "hurt": 8}
DIFF_ORDER = ["easy", "normal", "hard"]                    # legacy (stages.json "difficulty" table keys)
DIFFICULTIES = ["easy", "normal", "hard", "harder", "hell", "crazy"]   # v1.9: chosen on the select screen
DIFF_LABEL = {"easy": "쉬움", "normal": "보통", "hard": "어려움", "harder": "하드", "hell": "헬", "crazy": "크레이지"}
DIFF_MULT = {"easy": 0.7, "normal": 1.0, "hard": 1.3, "harder": 1.6, "hell": 2.2, "crazy": 3.0}
DIFF_UNLOCK = {"hell": ("any", 20), "crazy": ("hell", 30)}   # difficulty -> (cleared-on, stages cleared)

DEFAULT_DIFFICULTY = {"easy": {"hp": 0.8, "speed": 0.9, "count": 0.8},
                      "normal": {"hp": 1.0, "speed": 1.0, "count": 1.0},
                      "hard": {"hp": 1.6, "speed": 1.25, "count": 1.4}}
DEFAULT_WAVE = {"base_count": 3, "per_wave": 1, "per_stage": 0.35, "per_cycle": 1, "max_count": 10,
                "elite_ratio_base": 0.2, "elite_ratio_per_wave": 0.1, "elite_ratio_max": 0.5,
                "spawn_stagger": 0.3}
DEFAULT_CHAR = {"name": "?", "trait": "", "damage": 1.0, "speed": 1.0, "fire_rate": 1.0,
                "jump": 1.0, "pierce": False}

CONFIRM_GUARD = 0.25      # s after a state change during which confirm/fire is ignored (Space = confirm+fire)


# ---------------------------------------------------------------- helpers
class _NoEconomy:
    """Stand-in when economy.py is missing: no gear, no drops, everything else keeps working."""
    SLOTS = ("hat", "gloves", "suit", "shoes", "weapon", "acc")

    class Warehouse:
        CAP = 24

        def __init__(self, data=None):
            self.items = []
            self.equipped = {k: None for k in _NoEconomy.SLOTS}

        def add(self, eq):
            return False

        def equip(self, idx):
            return None

        def unequip(self, slot):
            return False

        def remove(self, idx):
            return self.items.pop(idx)

        def effect(self):
            return {k: 0 for k in ("shield", "rate", "magic", "speed", "jump", "damage", "money", "str", "agi", "int")}

        def to_save(self):
            return {"items": [], "equipped": dict(self.equipped)}

    @staticmethod
    def money_drop(rng, kind, stage, diff_mult, acc_bonus):
        base = {"grunt": 30, "elite": 80, "mid": 300, "boss": 800, "word": 500}.get(kind, 0)
        return int(base * (1 + 0.05 * (stage - 1)) * diff_mult * (1 + acc_bonus))


if economy is None:
    economy = _NoEconomy


def load_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_data(base_dir: str | None = None) -> tuple[dict, dict]:
    """Convenience for the integration layer: (stages, config) from files next to this module."""
    base = base_dir or os.path.dirname(os.path.abspath(__file__))
    stages = load_json(os.path.join(base, "stages.json"), {}) or {}
    config = load_json(os.path.join(base, "config.json"), {}) or {}
    return stages, config


def _overlap(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


# ---------------------------------------------------------------- entities
class _Ent:
    __slots__ = ("x", "y", "vx", "vy", "on_ground", "facing", "anim", "frame", "anim_t", "hold_frame", "anim_rate")

    def __init__(self):
        self.anim_rate = 1.0        # playback speed factor (sprinting enemies run their anim faster)
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = True
        self.facing = 1
        self.anim = "idle"
        self.frame = 0
        self.anim_t = 0.0
        self.hold_frame = None      # int -> frame counter stops at this value (one-shot anims)

    def set_anim(self, name: str):
        if name != self.anim:
            self.anim = name
            self.frame = 0
            self.anim_t = 0.0

    def tick_anim(self, dt: float):
        fps = ANIM_FPS.get(self.anim, 8)
        if fps <= 0:
            return
        self.anim_t += dt * self.anim_rate
        step = 1.0 / fps
        while self.anim_t >= step:
            self.anim_t -= step
            if self.hold_frame is not None and self.anim in ("death", "victory") and self.frame >= self.hold_frame:
                self.anim_t = 0.0
                break
            self.frame += 1


class Player(_Ent):
    __slots__ = ("crouch", "fire_cd", "shoot_t", "inv_t", "dead", "death_t", "drop_t", "jump_buf", "on_platform",
                 "weapon", "weapon_t", "ammo", "shield", "skill_cd", "melee_t", "combo", "combo_t", "ult_t")

    def __init__(self):
        super().__init__()
        self.combo = 0              # v1.9: melee combo counter (knife 3-hit)
        self.combo_t = 0.0
        self.shield = 0
        self.skill_cd = 0.0
        self.ult_t = 0.0            # v2.0: portrait burst timer (ULT_T -> 0)
        self.melee_t = 0.0
        self.weapon = "normal"
        self.weapon_t = 0.0
        self.ammo = 0
        self.crouch = False
        self.fire_cd = 0.0
        self.shoot_t = 0.0
        self.inv_t = 0.0
        self.dead = False
        self.death_t = 0.0
        self.drop_t = 0.0
        self.jump_buf = 0.0
        self.on_platform = False


class Enemy(_Ent):
    __slots__ = ("id", "rank", "palette", "label", "hp", "hp_max", "speed", "fire_rate", "scale", "boss", "kind",
                 "pattern", "stop_dist", "fire_cd", "shoot_t", "death_t", "jump_cd", "burst_left", "burst_t",
                 "dash_t", "dash_cd", "dash_dir", "spread_cd", "summon_cd", "stamp_cd", "intro", "hop_vx", "w", "h",
                 "element", "mid", "attack_t", "attack_cd", "ranged_cd", "hurt_t", "hurt_cd", "hit_done",
                 "move_mode", "move_t", "land_t", "drop", "spawn_kind", "reach", "melee", "born", "lunge_t",
                 "proj", "target")

    def __init__(self):
        super().__init__()
        self.reach = 40.0           # v1.9: melee reach (px from centre)
        self.melee = False          # prefers melee (stops at reach instead of stop_dist)
        self.born = 0.0             # world play time at spawn (balance log: time to kill)
        self.lunge_t = 0.0          # slime lunge
        self.proj = None            # rank "proj" dict for sprite projectiles (None = plain shot)
        self.target = 0             # 0 = player, 1 = decoy (if any)
        self.move_mode = "walk"     # "walk" | "sprint" | "pause" (grunt / elite approach variety)
        self.move_t = 0.0           # s left in the current movement mode
        self.land_t = 0.0           # s of stillness left after a drop / burst landing
        self.drop = False           # falling in from the sky (not yet landed)
        self.spawn_kind = "side"    # "side" | "ground" | "sky"
        self.element = None         # ELEMENT_KEYS entry or None
        self.mid = False            # mid boss flag (palette boss with the "mid" AI, spawned mid-stage)
        self.attack_t = 0.0         # remaining time of the current attack / attack2 animation
        self.attack_cd = 0.0
        self.ranged_cd = 1.5
        self.hurt_t = 0.0
        self.hurt_cd = 0.0
        self.hit_done = False       # this attack already dealt its damage / fired its shot
        self.id = 0
        self.rank = ""
        self.palette = ""
        self.label = ""
        self.hp = 1
        self.hp_max = 1
        self.speed = 50.0
        self.fire_rate = 0.2
        self.scale = 2
        self.boss = False
        self.kind = "grunt"
        self.pattern = "mid"
        self.stop_dist = 200.0
        self.fire_cd = 1.0
        self.shoot_t = 0.0
        self.death_t = None
        self.jump_cd = 2.0
        self.burst_left = 0
        self.burst_t = 0.0
        self.dash_t = 0.0
        self.dash_cd = 3.0
        self.dash_dir = -1
        self.spread_cd = 2.0
        self.summon_cd = 6.0
        self.stamp_cd = 2.0
        self.intro = False
        self.hop_vx = 0.0
        self.w = ENEMY_W
        self.h = ENEMY_H

    @property
    def alive(self) -> bool:
        return self.death_t is None

    def box(self):
        hw = self.w / 2
        return (self.x - hw, self.y - self.h, self.x + hw, self.y)


class Bullet:
    __slots__ = ("x", "y", "w", "h", "vx", "vy", "owner", "dmg", "pierce", "hit", "dead", "stamp",
                 "kind", "ttl", "px", "py", "mdmg", "element", "sprite", "anim", "frame", "anim_t",
                 "gravity", "r", "fuse", "r_max")

    def __init__(self, x, y, w, h, vx, vy, owner, dmg=1, pierce=False, stamp=False, kind="normal", ttl=None,
                 mdmg=0, element=None, sprite=None, anim=None, gravity=False, r=0.0, fuse=None):
        self.gravity = gravity           # v1.9: parabolic projectile (bomb / boulder)
        self.r = r                       # blast radius (kind "blast": grows to r_max over BLAST_T)
        self.r_max = r
        self.fuse = fuse                 # seconds on the ground before a gravity bullet blasts (None = none)
        self.x, self.y, self.w, self.h = x, y, w, h
        self.sprite = sprite             # palette key of a sprite projectile (drawn instead of a rectangle)
        self.anim = anim                 # its anim name ("proj"); advanced by _update_bullets at PROJ_ANIM_FPS
        self.frame = 0
        self.anim_t = 0.0
        self.px, self.py = x, y          # previous position (swept collision)
        self.vx, self.vy = vx, vy
        self.owner = owner
        self.dmg = dmg                   # physical damage (element-independent)
        self.mdmg = mdmg                 # magic damage, scaled by the element multiplier
        self.element = element           # attacker element (ELEMENT_KEYS) or None
        self.pierce = pierce
        self.hit = set()
        self.dead = False
        self.stamp = stamp
        self.kind = kind                 # "normal" | "laser" | "missile" | "proj"
        self.ttl = ttl                   # seconds; None = until off-screen

    def swept_box(self):
        """Box covering the bullet's travel since the last tick (prevents tunnelling through thin targets)."""
        x0, x1 = (self.px, self.x) if self.px <= self.x else (self.x, self.px)
        y0, y1 = (self.py, self.y) if self.py <= self.y else (self.y, self.py)
        return (x0 - self.w / 2, y0 - self.h / 2, x1 + self.w / 2, y1 + self.h / 2)

    def box(self):
        return (self.x - self.w / 2, self.y - self.h / 2, self.x + self.w / 2, self.y + self.h / 2)


class Item:
    __slots__ = ("x", "y", "vy", "vx", "kind", "t", "on_ground", "value", "age")
    SIZE = 14

    def __init__(self, x, y, kind, value=0):
        self.x, self.y = float(x), float(y)
        self.vy = -260.0
        self.vx = 0.0
        self.kind = kind
        self.value = int(value)          # coin value (kind "coin")
        self.t = COIN_TTL if kind == "coin" else ITEM_TTL
        self.age = 0.0
        self.on_ground = False

    def box(self):
        s = Item.SIZE
        return (self.x - s / 2, self.y - s, self.x + s / 2, self.y)


class Ally(_Ent):
    """v1.9 item companions: decoy (분신) / drone (보안 드론) / dog (찹츄)."""
    __slots__ = ("kind", "t", "ttl", "hp", "fire_cd", "palette", "target_id")

    def __init__(self, kind, x, y, ttl, palette=""):
        super().__init__()
        self.kind = kind
        self.x, self.y = float(x), float(y)
        self.t = ttl
        self.ttl = ttl
        self.hp = DECOY_HP
        self.fire_cd = 0.0
        self.palette = palette
        self.target_id = 0

    def box(self):
        return (self.x - PLAYER_W / 2, self.y - PLAYER_H, self.x + PLAYER_W / 2, self.y)

    def shoot_anim_done(self) -> bool:
        return self.anim == "shoot" and self.anim_t == 0.0 and self.frame >= 2


# ---------------------------------------------------------------- world
class World:
    """See INTERFACES.md section C."""

    STATES = ("select", "play", "stage_clear", "shop", "game_over", "paused", "continue", "town")

    def __init__(self, stages: dict, config: dict, save: dict, width: int, height: int, seed: int | None = None):
        self.stages = stages or {}
        self.config = config or {}
        self.rng = random.Random(seed)
        self.width = max(320, int(width))
        self.height = max(120, int(height))
        self.ground_y = self.height - 10

        self.departments = list(self.stages.get("departments") or [])
        self.executives = list(self.stages.get("executive_stages") or [])
        self.ranks = dict(self.stages.get("ranks") or {})
        self.difficulty = dict(DEFAULT_DIFFICULTY)
        self.difficulty.update(self.stages.get("difficulty") or {})
        self.wave_cfg = dict(DEFAULT_WAVE)
        self.wave_cfg.update(self.stages.get("wave") or {})
        self.progression = dict(DEFAULT_PROGRESSION)
        self.progression.update(self.stages.get("progression") or {})
        if not self.departments:
            self.departments = [{"name": "총무팀", "waves": 3, "grunts": ["intern", "staff"], "elites": [],
                                 "boss": "teamlead", "boss_title": "팀장", "platforms": 1, "pits": 0, "lab": False}]

        chars = self.config.get("characters") or {}
        self.chars = {}
        for k in CHAR_KEYS:
            c = dict(DEFAULT_CHAR)
            c["name"] = k
            c.update(chars.get(k) or {})
            self.chars[k] = c
        self.char_names = [self.chars[k]["name"] for k in CHAR_KEYS]
        self.lives_max = int(self.config.get("lives", 3))
        # elements (사신): defaults merged with config "elements" / "element_mult"
        self.elements: dict[str, dict] = {}
        cfg_el = self.config.get("elements") or {}
        for k in ELEMENT_KEYS:
            el = dict(DEFAULT_ELEMENTS[k])
            el.update(cfg_el.get(k) or {})
            if el.get("beats") not in ELEMENT_KEYS:
                el["beats"] = DEFAULT_ELEMENTS[k]["beats"]
            self.elements[k] = el
        em = dict(DEFAULT_ELEMENT_MULT)
        em.update(self.config.get("element_mult") or {})
        self.element_mult = {"strong": float(em.get("strong", 1.5)), "weak": float(em.get("weak", 0.5))}
        self.mid_bosses = [m for m in (self.stages.get("mid_bosses") or [])
                           if isinstance(m, dict) and m.get("rank") in self.ranks]
        self.final_bosses = [k for k in (self.stages.get("final_bosses") or []) if k in self.ranks]
        # equipment: defaults merged with config "equipment"
        self.equipment: dict[str, dict] = {}
        cfg_eq = self.config.get("equipment") or {}
        for k in EQUIP_ORDER:
            eq = dict(DEFAULT_EQUIPMENT[k])
            eq.update(cfg_eq.get(k) or {})
            self.equipment[k] = eq
        self.anim_lens: dict[str, int] | None = None   # optional: integration may set {"death": n, ...} to hold last frame

        # --- save / persistent
        save = save or {}
        self.best = int(save.get("best", 0) or 0)
        self.save_stage = int(save.get("stage", 1) or 1)
        self.continue_stage = self.save_stage if self.save_stage > 1 else None
        self.select_index = 0
        sc = save.get("char")
        for i, k in enumerate(CHAR_KEYS):
            if sc in (k, self.chars[k]["name"]):
                self.select_index = i
        self.cont_index = 0
        self.element_index = 0
        if save.get("element") in ELEMENT_KEYS:
            self.element_index = ELEMENT_KEYS.index(save["element"])
        self.unlocked: set[str] = {k for k in (save.get("unlocked") or []) if k in CHAR_KEYS}
        # v1.9 meta progression (kept across game overs): money, warehouse, difficulty, clears, inventory
        self.money = max(0, int(save.get("money", 0) or 0))
        self.warehouse = economy.Warehouse(save.get("warehouse") if isinstance(save.get("warehouse"), dict) else None)
        self.best_clear: dict[str, int] = {}
        for k, v in (save.get("best_clear") or {}).items():
            if k in DIFFICULTIES:
                self.best_clear[k] = max(0, int(v))
        self.difficulty_index = DIFFICULTIES.index(save["difficulty"]) if save.get("difficulty") in DIFFICULTIES else 1
        if self._diff_locked(self.difficulty_key):
            self.difficulty_index = 1
        self.inventory: list[dict | None] = [None] * INV_SLOTS
        for i, it in enumerate((save.get("inventory") or [])[:INV_SLOTS]):
            if isinstance(it, dict) and it.get("kind") in ITEM_KINDS and it.get("kind") != "coin":
                self.inventory[i] = {"kind": it["kind"], "count": max(1, min(INV_STACK, int(it.get("count", 1))))}
        self.inv_flash: int | None = None
        self.inv_flash_t = 0.0
        self.allies: list[Ally] = []
        self.words: list[dict] = []
        self.words_left = 0                     # falling words still to spawn this stage
        self.word_next = 0.0                    # s until the next word may spawn
        self.slow_t = 0.0
        self.play_t = 0.0                       # seconds of play (balance log)
        self.town: dict | None = None
        self.balance_log: list[dict] = []       # per-stage balance records (drained by the integration layer)
        self._bal: dict = {}                    # the record being built for the current stage
        self.shop_stock: list[dict] = []        # equipment stock of the current town (refreshed every town)
        self.shop_stock_stage = 0
        self.saved_upgrades = dict(save.get("upgrades") or {})
        self.saved_equip = {k: int(v) for k, v in (save.get("equip") or {}).items() if k in EQUIP_ORDER}
        self.shop_items = {k: list(v) for k, v in DEFAULT_SHOP.items()}
        for k, v in (self.config.get("shop") or {}).items():
            if k in self.shop_items and isinstance(v, dict):
                row = self.shop_items[k]
                row[0] = str(v.get("label", row[0]))
                row[1] = int(v.get("cost", row[1]))
                row[2] = float(v.get("growth", row[2]))
                row[3] = int(v.get("max", row[3]))

        # --- runtime
        self.upgrades = {k: 0 for k in self.shop_items}
        self.equip = {k: 0 for k in EQUIP_ORDER}
        self._equip_msg: str | None = None      # last "장비 획득" text, appended to the STAGE CLEAR banner
        self.zones: list[dict] = []
        self.shop_index = 0
        self.shop_msg = ""
        self.state = "select"
        self.state_t = 0.0
        self.keys: set[str] = set()
        self.player = Player()
        self.enemies: list[Enemy] = []
        self.bullets: list[Bullet] = []
        self.items: list[Item] = []
        self.effects: list[dict] = []
        self.platforms: list[tuple] = []
        self.pits: list[tuple] = []
        self.score = 0
        self.lives = self.lives_max
        self.stage_no = 0
        self.stage: dict = {}
        self.wave_index = 0
        self.pending: list[tuple] = []          # (rank, side, spawn_kind)
        self.warnings: list[dict] = []          # {"kind","x","t","ttl","rank"} pending ground / sky spawns
        self.spawn_t = 0.0
        self.spawn_side = 0
        self.phase = "wave"                     # "wave" | "midboss" | "boss"
        self.mid_done = False                   # this stage's mid boss already spawned+defeated
        self.boss_index = 0
        self.boss_gap = 0.0
        self.wave_gap = 0.0
        self.boss_ref: Enemy | None = None
        self.banner: str | None = None
        self.banner_t = 0.0
        self.banner_ttl: float | None = None
        self.next_id = 1
        self._paused_from = None
        self._refresh_select_banner()

    # ------------------------------------------------------------ public API
    @property
    def char_key(self) -> str:
        return CHAR_KEYS[self.select_index % len(CHAR_KEYS)]

    @property
    def char(self) -> dict:
        return self.chars[self.char_key]

    @property
    def element_key(self) -> str:
        return ELEMENT_KEYS[self.element_index % len(ELEMENT_KEYS)]

    @property
    def difficulty_key(self) -> str:
        return DIFFICULTIES[self.difficulty_index % len(DIFFICULTIES)]

    def _diff_mult(self) -> float:
        return float(DIFF_MULT.get(self.difficulty_key, 1.0))

    def _diff_locked(self, key: str) -> bool:
        rule = DIFF_UNLOCK.get(key)
        if not rule:
            return False
        on, need = rule
        best = max(self.best_clear.values(), default=0) if on == "any" else self.best_clear.get(on, 0)
        return best < need

    def _equip_fx(self) -> dict:
        return self.warehouse.effect()

    def drain_log(self) -> list[dict]:
        """Balance records completed since the last call (one per stage / death). The caller writes them."""
        out, self.balance_log = self.balance_log, []
        return out

    # ------------------------------------------------------------ stats / elements
    @staticmethod
    def _stats(c: dict) -> dict | None:
        s = c.get("stats")
        if isinstance(s, dict) and all(k in s for k in ("agi", "str", "int")):
            return {k: int(s[k]) for k in ("agi", "str", "int")}
        return None

    def _eff_stats(self, c: dict) -> dict | None:
        """Effective stats = config stats + shop upgrades (str/agi/int). None for legacy characters."""
        s = self._stats(c)
        if s is None:
            return None
        fx = self._equip_fx()
        return {k: s[k] + int(self.upgrades.get(k, 0)) + int(fx.get(k, 0)) for k in STAT_KEYS}

    def _equip_bonus(self, key: str) -> float:
        """Legacy level bonus (old 4-slot model) + v1.9 warehouse gear effect for `key`."""
        total = 0.0
        for slot, lv in self.equip.items():
            eq = self.equipment.get(slot)
            if eq and lv > 0 and key in eq:
                total += float(eq[key]) * lv
        return total + float(self._equip_fx().get(key, 0.0))

    def _speed_mult(self, c: dict) -> float:
        s = self._eff_stats(c)
        base = 1.0 + SPEED_PER_AGI * (s["agi"] - STAT_BASE) if s else float(c.get("speed", 1.0))
        return base * (1.0 + self._equip_bonus("speed"))

    def _jump_mult(self, c: dict) -> float:
        s = self._eff_stats(c)
        base = 1.0 + JUMP_PER_AGI * (s["agi"] - STAT_BASE) if s else float(c.get("jump", 1.0))
        return base * (1.0 + self._equip_bonus("jump"))

    def _phys_dmg(self, c: dict) -> int:
        """Physical damage per shot: max(1, str // 3) (legacy characters: config damage)."""
        s = self._eff_stats(c)
        base = max(1, s["str"] // 3) if s else max(1, int(round(float(c.get("damage", 1.0)))))
        return base + int(self._equip_fx().get("damage", 0))

    def _magic_dmg(self, c: dict) -> int:
        """Magic damage: int // 3 + suit levels."""
        s = self._eff_stats(c)
        return max(0, (s["int"] // 3 if s else 0) + int(round(self._equip_bonus("magic"))))

    def _bullet_speed(self, c: dict) -> float:
        """int -> bullet speed (normal / spread / rapid / missile; laser is instant)."""
        s = self._eff_stats(c)
        return BULLET_SPEED * (1.0 + BULLET_PER_INT * (s["int"] - STAT_BASE)) if s else BULLET_SPEED

    def _fire_rate_mult(self, c: dict) -> float:
        return (float(c.get("fire_rate", 1.0)) * (1.0 + 0.2 * self.upgrades.get("rate", 0))
                * (1.0 + self._equip_bonus("rate")))

    def _elem_mult(self, attacker: str | None, target: str | None) -> float:
        if attacker not in self.elements or target not in self.elements:
            return 1.0
        if self.elements[attacker]["beats"] == target:
            return self.element_mult["strong"]
        if self.elements[target]["beats"] == attacker:
            return self.element_mult["weak"]
        return 1.0

    def _strike(self, e: Enemy, dmg: int, mdmg: int = 0, element: str | None = None,
                x: float | None = None, y: float | None = None) -> int:
        """Player attack on an enemy: physical + magic x element multiplier. Emits hit (+elem) effects."""
        if x is None:
            x, y = e.x, e.y - e.h * 0.6
        mult = self._elem_mult(element, e.element) if mdmg > 0 else 1.0
        total = int(dmg) + int(round(mdmg * mult))
        self._effect("hit", x, y)
        if mdmg > 0 and mult != 1.0:
            self._effect("elem", x, y - 10, text=("강!" if mult > 1.0 else "약"))
        self._damage_enemy(e, total)
        return total

    def resize(self, width: int, height: int) -> None:
        width = max(320, int(width))
        height = max(120, int(height))
        if width == self.width and height == self.height:
            return
        rx = width / self.width
        old_ground = self.ground_y
        self.width, self.height = width, height
        self.ground_y = self.height - 10
        dy = self.ground_y - old_ground
        self.platforms = [(x * rx, y + dy, w, h) for (x, y, w, h) in self.platforms]
        self.pits = [(x * rx, w) for (x, w) in self.pits]
        for ent in [self.player] + self.enemies:
            ent.x *= rx
            ent.y += dy
        for b in self.bullets:
            b.x *= rx
            b.y += dy
        for fx in self.effects:
            fx["x"] *= rx
            fx["y"] += dy

    def set_paused(self, paused: bool) -> None:
        if paused and self.state == "play":
            self._set_state("paused")
        elif not paused and self.state == "paused":
            self._set_state("play")

    def key_down(self, key: str) -> None:
        self.keys.add(key)
        st = self.state
        if st == "select":
            if key in ("sel_left", "left"):
                self.select_index = (self.select_index - 1) % len(CHAR_KEYS)
                self._refresh_select_banner()
            elif key in ("sel_right", "right"):
                self.select_index = (self.select_index + 1) % len(CHAR_KEYS)
                self._refresh_select_banner()
            elif key == "up":                 # "jump" also arrives for ↑ — ignored here on purpose
                self.element_index = (self.element_index - 1) % len(ELEMENT_KEYS)
            elif key == "down":
                self.element_index = (self.element_index + 1) % len(ELEMENT_KEYS)
            elif key == "skill":              # C: cycle difficulty (locked ones are skipped)
                for _ in range(len(DIFFICULTIES)):
                    self.difficulty_index = (self.difficulty_index + 1) % len(DIFFICULTIES)
                    if not self._diff_locked(self.difficulty_key):
                        break
                self._refresh_select_banner()
            elif key in ("confirm", "fire") and self.state_t >= CONFIRM_GUARD:
                if self._char_locked(self.char_key):
                    self._refresh_select_banner()          # locked: stay on the select screen
                elif self.continue_stage and self.continue_stage > 1:
                    self.cont_index = 0
                    self._set_state("continue")
                    self._refresh_continue_banner()
                else:
                    self._start_game(1)
        elif st == "continue":
            if key in ("left", "sel_left", "right", "sel_right"):
                self.cont_index = 1 - self.cont_index
                self._refresh_continue_banner()
            elif key in ("confirm", "fire") and self.state_t >= CONFIRM_GUARD:
                if self.cont_index == 0 and self.continue_stage:
                    self._start_game(self.continue_stage, keep_upgrades=True)
                else:
                    self._start_game(1)
        elif st == "play":
            if key == "pause":
                self._set_state("paused")
            elif key in ("jump", "up"):
                self.player.jump_buf = 0.12
            elif key == "skill":
                self._use_skill()
            elif key.startswith("slot") and key[4:].isdigit():
                self._use_slot(int(key[4:]) - 1)
            elif key.startswith("char:") and len(key) == 6:
                self._type_letter(key[5])
        elif st == "shop":
            if key in ("left", "sel_left"):
                self.shop_index = (self.shop_index - 1) % len(SHOP_ORDER)
                self.shop_msg = ""
            elif key in ("right", "sel_right"):
                self.shop_index = (self.shop_index + 1) % len(SHOP_ORDER)
                self.shop_msg = ""
            elif key in ("confirm", "fire") and self.state_t >= CONFIRM_GUARD:
                self._shop_select()
        elif st == "town":
            self._town_key(key)
        elif st == "paused":
            if key == "pause":
                self._set_state("play")
        elif st == "game_over":
            if key in ("confirm", "fire") and self.state_t >= 3.0:
                self._set_state("select")
                self._refresh_select_banner()

    def key_up(self, key: str) -> None:
        self.keys.discard(key)

    def update(self, dt: float) -> None:
        dt = max(0.0, min(float(dt), 0.05))
        self.state_t += dt
        self.banner_t += dt
        if self.banner_ttl is not None and self.banner_t >= self.banner_ttl and self.state == "play":
            self.banner = None
            self.banner_ttl = None
        st = self.state
        if st == "play":
            self._update_play(dt)
        elif st == "stage_clear":
            self.player.set_anim("victory")
            self.player.tick_anim(dt)
            self._update_effects(dt)
            if self.state_t >= CLEAR_TO_SHOP:
                if self.stage_no % TOWN_EVERY == 0:
                    self._open_town()
                else:
                    self._open_shop()
        elif st in ("game_over", "shop", "town"):
            self._update_effects(dt)
        # select / continue / paused: nothing moves

    def snapshot(self) -> dict:
        p = self.player
        visible = self.state in ("play", "paused", "stage_clear", "game_over")
        boss = self.boss_ref if (self.boss_ref is not None and self.boss_ref in self.enemies) else None
        return {
            "state": self.state,
            "ground_y": int(self.ground_y),
            "platforms": [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in self.platforms],
            "pits": [(int(x), int(w)) for (x, w) in self.pits],
            "player": {"x": p.x, "y": p.y, "anim": p.anim, "frame": p.frame, "flip": p.facing < 0,
                       "palette": self.char_key, "scale": 2, "invincible": p.inv_t > 0 and not p.dead,
                       "visible": visible, "element": self.element_key},
            "enemies": [{"id": e.id, "x": e.x, "y": e.y, "anim": e.anim, "frame": e.frame, "flip": e.facing < 0,
                         "palette": e.palette, "scale": e.scale, "label": e.label, "hp": max(0, e.hp),
                         "hp_max": e.hp_max, "boss": e.boss, "element": e.element, "mid": e.mid,
                         "sprint": (e.alive and e.on_ground and e.move_mode == "sprint" and abs(e.vx) > 1),
                         "drop": bool(e.drop and e.alive),
                         "attack": bool(e.alive and e.attack_t > 0), "slow": bool(self.slow_t > 0 and e.alive)}
                        for e in self.enemies],
            "allies": [{"kind": a.kind, "x": a.x, "y": a.y, "anim": a.anim, "frame": a.frame, "flip": a.facing < 0,
                        "palette": a.palette, "t": round(a.t, 2), "ttl": a.ttl} for a in self.allies],
            "words": [{"text": w["text"], "typed": w["typed"], "x": w["x"], "y": w["y"], "kind": w["kind"],
                       "t": round(w["t"], 2), "vy": w["vy"]} for w in self.words],
            "warnings": [{"kind": w["kind"], "x": w["x"], "t": max(0.0, w["t"]), "ttl": w["ttl"]}
                         for w in self.warnings],
            "bullets": [{"x": b.x, "y": b.y, "w": b.w, "h": b.h, "owner": b.owner, "kind": b.kind,
                         "sprite": b.sprite, "anim": b.anim, "frame": b.frame, "flip": b.vx < 0,
                         "gravity": b.gravity, "r": round(b.r, 1)}
                        for b in self.bullets],
            "items": [{"x": it.x, "y": it.y, "kind": it.kind, "t": it.t, "value": it.value} for it in self.items],
            "zones": [{"kind": z["kind"], "x": z["x"], "w": z["w"], "h": ZONE_H, "t": z["t"], "ttl": z["ttl"]}
                      for z in self.zones],
            "effects": [{"kind": f["kind"], "x": f["x"], "y": f["y"], "t": f["t"], "text": f["text"]}
                        for f in self.effects],
            "hud": {"lives": self.lives, "score": self.score, "best": self.best,
                    "stage_no": self.stage_no, "stage_name": self._stage_display(),
                    "difficulty": self.stage.get("difficulty", "normal") if self.stage else "normal",
                    "boss_hp": (max(0, boss.hp) if boss else None),
                    "boss_hp_max": (boss.hp_max if boss else None),
                    "banner": self.banner, "banner_t": self.banner_t,
                    "char_name": self.char["name"], "select_index": self.select_index,
                    "char_names": list(self.char_names),
                    "continue_stage": self.continue_stage,
                    "show_enemy_hp": bool(self.char.get("show_enemy_hp", False)),
                    "shield": p.shield, "shield_max": self._shield_max(),
                    "melee_t": round(p.melee_t, 3),
                    "skill_label": (self.char["storm"].get("label", "서류 스톰") if self.char.get("storm") else None),
                    "skill_cd": (round(max(0.0, p.skill_cd), 2) if self.char.get("storm") else None),
                    "ult": ({"t": round(p.ult_t, 3), "ttl": ULT_T} if p.ult_t > 0 and not p.dead else None),
                    "char_locked": [self._char_locked(k) for k in CHAR_KEYS],
                    "shop": self._shop_view() if self.state == "shop" else None,
                    "weapon": (p.weapon if p.weapon != "normal" else None),
                    "weapon_label": ITEM_LABEL.get(p.weapon),
                    "weapon_left": (p.ammo if p.weapon == "homing"
                                    else (int(math.ceil(p.weapon_t)) if p.weapon != "normal" else None)),
                    "element": self.element_key,
                    "element_name": self.elements[self.element_key]["name"],
                    "element_names": [self.elements[k]["name"] for k in ELEMENT_KEYS],
                    "element_index": self.element_index % len(ELEMENT_KEYS),
                    "element_colors": {k: self.elements[k]["color"] for k in ELEMENT_KEYS},
                    "stats": self._eff_stats(self.char),
                    "char_stats": [self._stats(self.chars[k]) for k in CHAR_KEYS],
                    "equip": dict(self.equip),
                    "equip_labels": {k: str(self.equipment[k].get("label", k)) for k in EQUIP_ORDER},
                    # v1.9
                    "money": int(self.money),
                    "difficulty_label": DIFF_LABEL[self.difficulty_key],
                    "difficulty_index": self.difficulty_index % len(DIFFICULTIES),
                    "difficulty_locked": [self._diff_locked(k) for k in DIFFICULTIES],
                    "inventory": [dict(it) if it else None for it in self.inventory],
                    "inv_flash": self.inv_flash,
                    "melee_style": self._melee_style(),
                    "melee_hit": int(p.combo),
                    "slow_t": round(self.slow_t, 2),
                    "equip_effect": self._equip_fx(),
                    "equipped": {k: (dict(v) if v else None) for k, v in self.warehouse.equipped.items()},
                    "town": self._town_view()},
        }

    def save_data(self) -> dict:
        return {"stage": int(self.save_stage), "best": int(self.best), "char": self.char_key,
                "char_name": self.char["name"], "hotkey": self.config.get("hotkey", "shift+0"),
                "upgrades": dict(self.saved_upgrades), "unlocked": sorted(self.unlocked),
                "element": self.element_key, "equip": dict(self.saved_equip),
                # v1.9 meta progression (kept across game overs)
                "money": int(self.money), "warehouse": self.warehouse.to_save(),
                "difficulty": self.difficulty_key, "best_clear": dict(self.best_clear),
                "inventory": [dict(it) if it else None for it in self.inventory]}

    # ------------------------------------------------------------ debug helpers (selftest)
    def _debug_kill_all(self) -> int:
        n = 0
        for e in list(self.enemies):
            if e.alive:
                self._damage_enemy(e, 10 ** 9)
                n += 1
        return n

    def _debug_kill_player(self) -> None:
        self.player.inv_t = 0.0
        self._kill_player(force=True)

    # ------------------------------------------------------------ state / banners
    def _set_state(self, s: str):
        self.state = s
        self.state_t = 0.0

    def _set_banner(self, text: str | None, ttl: float | None = None):
        self.banner = text
        self.banner_t = 0.0
        self.banner_ttl = ttl

    def _refresh_select_banner(self):
        c = self.char
        if self._char_locked(self.char_key):
            self._set_banner(f"◀ ??? ({self._unlock_stage(self.char_key)}스테이지 클리어 시 해금) ▶")
        else:
            self._set_banner(f"◀ {c['name']} ({c.get('trait', '')}) ▶ · {DIFF_LABEL[self.difficulty_key]}")

    def _char_hidden(self, key: str) -> bool:
        return bool(self.chars[key].get("hidden", False))

    def _unlock_stage(self, key: str) -> int:
        return int(self.chars[key].get("unlock_stage", DEFAULT_UNLOCK_STAGE))

    def _char_locked(self, key: str) -> bool:
        return self._char_hidden(key) and key not in self.unlocked

    def _refresh_continue_banner(self):
        cs = self.continue_stage or 1
        a, b = ("▶ ", "") if self.cont_index == 0 else ("", "▶ ")
        self._set_banner(f"{a}이어하기 ({cs}스테이지)   {b}처음부터")

    def _stage_display(self) -> str:
        if not self.stage:
            return ""
        s = self.stage
        name = f"{s['no']}스테이지: {s['name']}"
        if s.get("infinite"):
            name += f" ({DIFF_LABEL.get(s['difficulty'], s['difficulty'])})"
        return name

    # ------------------------------------------------------------ stage building
    def _build_stage(self, n: int) -> dict:
        nd, ne = len(self.departments), len(self.executives)
        st = {"no": n, "infinite": False, "difficulty": "normal", "cycle": 0, "dept_idx": 0}
        if n <= nd:
            d = self.departments[n - 1]
            st["dept_idx"] = n - 1
            kind = "dept"
        elif n <= nd + ne:
            d = self.executives[n - nd - 1]
            kind = "exec"
        else:
            idx = n - nd - ne - 1
            cycle = idx // nd
            st["dept_idx"] = idx % nd
            st["cycle"] = cycle
            st["infinite"] = True
            d = self.departments[idx % nd]
            kind = "dept"
        # v1.9: the chosen difficulty (select screen) drives the multipliers; infinite cycles keep escalating
        st["difficulty"] = self.difficulty_key
        m = self._diff_mult()
        bonus = st["cycle"]
        mult = {"hp": m + 0.25 * bonus,
                "speed": 1.0 + (m - 1.0) / 2.0 + 0.05 * bonus,
                "count": 1.0 + (m - 1.0) * 0.4 + 0.1 * bonus,
                "proj": m,
                "money": m}
        monsters = [k for k in (d.get("monsters") or []) if k in self.ranks]
        grunts = list(d.get("grunts") or ["manager"])
        elites = list(d.get("elites") or [])
        if monsters and n >= int(self.stages.get("monsters_from_stage", 5)):
            for k in monsters:                       # v1.9: sheet monsters join the department roster
                (elites if self._rank(k).get("kind") == "elite" else grunts).append(k)
        st.update({
            "kind": kind, "name": d.get("name", "?"), "mult": mult,
            "waves": int(d.get("waves", 0 if kind == "exec" else 3)),
            "grunts": grunts,
            "elites": elites,
            "lab": bool(d.get("lab", False)),
            "platforms": int(d.get("platforms", 1)),
            "pits": int(d.get("pits", 0)),
        })
        if kind == "exec":
            bosses = list(d.get("bosses") or ["director"])
            titles = list(d.get("boss_titles") or [])
        else:
            # department stages: the final boss rotates through "final_bosses" (KOF brawlers) by stage number,
            # keeping the department's own boss title; falls back to the department "boss" rank.
            if self.final_bosses:
                bosses = [self.final_bosses[(n - 1) % len(self.final_bosses)]]
            else:
                bosses = [d.get("boss", "teamlead")]
            titles = [d.get("boss_title") or self._rank(bosses[0]).get("title", "보스")]
        while len(titles) < len(bosses):
            titles.append(self._rank(bosses[len(titles)]).get("title", "보스"))
        st["bosses"] = bosses
        st["boss_titles"] = titles
        return st

    def _rank(self, key: str) -> dict:
        r = self.ranks.get(key)
        if r is None:
            r = {"title": key, "kind": "grunt", "hp": 1, "speed": 60, "fire_rate": 0.2, "score": 100, "scale": 2}
        return r

    def _wave_count(self, wave_i: int) -> int:
        wc = self.wave_cfg
        s = self.stage
        raw = (wc["base_count"] + wc["per_wave"] * wave_i + wc["per_stage"] * s["dept_idx"]
               + wc["per_cycle"] * s["cycle"]) * s["mult"]["count"]
        return max(1, min(int(wc["max_count"]), int(round(raw))))

    def _gen_layout(self):
        rng = self.rng
        W, G = self.width, self.ground_y
        self.platforms = []
        for _ in range(self.stage.get("platforms", 0)):
            for _try in range(25):
                w = rng.randint(120, 220)
                if W - 60 - w <= 60:
                    break
                x = rng.randint(60, W - 60 - w)
                y = G - rng.randint(90, 160)
                if all((x + w + 40 < px) or (px + pw + 40 < x) or abs(y - py) > 50
                       for (px, py, pw, ph) in self.platforms):
                    self.platforms.append((float(x), float(y), float(w), 10.0))
                    break
        self.pits = []
        start = W * 0.15
        for _ in range(self.stage.get("pits", 0)):
            for _try in range(25):
                w = rng.randint(90, 140)
                if W - 200 - w <= 200:
                    break
                x = rng.randint(200, W - 200 - w)
                if x > start + 80 or x + w < start - 80:
                    self.pits.append((float(x), float(w)))
                    break

    def _over_pit(self, x: float) -> bool:
        for (px, pw) in self.pits:
            if px < x < px + pw:
                return True
        return False

    # ------------------------------------------------------------ game flow
    def _start_game(self, stage_no: int, keep_upgrades: bool = False):
        self.lives = self.lives_max
        self.score = 0
        self.upgrades = {k: 0 for k in self.shop_items}
        self.equip = {k: 0 for k in EQUIP_ORDER}
        if keep_upgrades:                       # "continue": upgrades / equipment earned before reaching that stage
            for k, v in self.saved_upgrades.items():
                if k in self.upgrades:
                    mx = self.shop_items[k][3]
                    self.upgrades[k] = max(0, int(v)) if mx <= 0 else max(0, min(int(v), mx))
            for k, v in self.saved_equip.items():
                if k in self.equip:
                    self.equip[k] = max(0, int(v))
        self._start_stage(stage_no)

    def _start_stage(self, n: int):
        self.stage_no = n
        self.stage = self._build_stage(n)
        self.save_stage = n
        self.continue_stage = n if n > 1 else None
        self._gen_layout()
        self.enemies.clear()
        self.bullets.clear()
        self.items.clear()
        self.effects.clear()
        self.zones.clear()
        self.warnings.clear()
        self.saved_upgrades = dict(self.upgrades)
        self.saved_equip = dict(self.equip)
        self._equip_msg = None
        self.boss_ref = None
        self.wave_index = 0
        self.boss_index = 0
        self.mid_done = False
        self.wave_gap = 0.0
        self.boss_gap = 0.0
        self.words.clear()
        self.allies.clear()
        self.words_left = WORDS_PER_STAGE
        self.word_next = self.rng.uniform(4.0, 9.0)
        self.slow_t = 0.0
        self.town = None
        self._reset_player(invincible=1.5)     # enemies close in x2 as fast since v1.8
        self._bal_start()
        if self.stage["waves"] > 0:
            self.phase = "wave"
            self._begin_wave()
        else:
            self.phase = "boss"
            self.boss_gap = BOSS_GAP
        self._set_banner(self._stage_display(), 1.5)
        self._set_state("play")

    def _reset_player(self, invincible: float = 2.0):
        p = self.player
        p.x = self.width * 0.15
        p.y = float(self.ground_y)
        p.vx = p.vy = 0.0
        p.on_ground = True
        p.facing = 1
        p.crouch = False
        p.dead = False
        p.death_t = 0.0
        p.inv_t = invincible
        p.shield = self._shield_max()      # refilled every stage start and respawn
        p.skill_cd = 0.0
        p.ult_t = 0.0
        p.melee_t = 0.0
        p.fire_cd = 0.0
        p.shoot_t = 0.0
        p.jump_buf = 0.0
        p.drop_t = 0.0
        p.hold_frame = None
        p.set_anim("idle")

    def _begin_wave(self):
        s = self.stage
        count = self._wave_count(self.wave_index)
        wc = self.wave_cfg
        elites = s["elites"]
        n_elite = 0
        if elites:
            ratio = min(wc["elite_ratio_max"], wc["elite_ratio_base"] + wc["elite_ratio_per_wave"] * self.wave_index)
            n_elite = int(count * ratio)
            if self.wave_index >= 1 and n_elite == 0:
                n_elite = 1
        self.pending = []
        for i in range(count):
            if i < count - n_elite:
                rank = self.rng.choice(s["grunts"])
            else:
                rank = self.rng.choice(elites)
            self.pending.append((rank, self.spawn_side, self._pick_spawn_kind(i)))
            self.spawn_side ^= 1
        self.spawn_t = 0.0
        self.wave_gap = WAVE_GAP

    def _pick_spawn_kind(self, slot: int) -> str:
        """First slot of a wave always walks in from a side; later slots may burst from the ground / drop
        from the sky with a chance that grows per stage (stage 1: 15 %, 5: 35 %, 9+: 55 %)."""
        if slot == 0:
            return "side"
        p = min(SPECIAL_SPAWN_MAX, SPECIAL_SPAWN_BASE + SPECIAL_SPAWN_PER_STAGE * max(0, self.stage_no - 1))
        if self.rng.random() >= p:
            return "side"
        return self.rng.choice(("ground", "sky"))

    def _special_spawn_x(self) -> float | None:
        """A floor x for a ground burst / sky drop: inside the band, off pits, away from the player and
        from other pending warnings. None when no spot qualifies (caller falls back to a side spawn)."""
        for _ in range(14):
            x = self.rng.uniform(self.width * 0.22, self.width * 0.92)
            if abs(x - self.player.x) < SPAWN_KEEP_OUT:
                continue
            if any(px - 40 < x < px + pw + 40 for (px, pw) in self.pits):
                continue
            if any(abs(w["x"] - x) < 60 for w in self.warnings):
                continue
            return x
        return None

    def _spawn_boss(self):
        s = self.stage
        if self.boss_index >= len(s["bosses"]):
            return
        rank = s["bosses"][self.boss_index]
        title = s["boss_titles"][self.boss_index]
        e = self._make_enemy(rank, self.width + 60.0, boss=True, title=title)
        e.intro = True
        e.facing = -1
        self.enemies.append(e)
        self.boss_ref = e

    def _mid_boss_eligible(self) -> list:
        return [m for m in self.mid_bosses if self.stage_no >= int(m.get("from_stage", 1))]

    def _mid_boss_due(self) -> bool:
        """After finishing wave waves//2 (stages with >= 2 waves), once per stage, if any mid boss qualifies."""
        waves = int(self.stage.get("waves", 0))
        return (waves >= 2 and not self.mid_done and self.wave_index == waves // 2
                and bool(self._mid_boss_eligible()))

    def _spawn_mid_boss(self):
        elig = self._mid_boss_eligible()
        if not elig:
            self.mid_done = True
            self.phase = "wave"
            self._begin_wave()
            return
        m = elig[self.stage_no % len(elig)]
        title = str(m.get("title") or self._rank(m["rank"]).get("title", "중간 보스"))
        e = self._make_enemy(m["rank"], self.width + 60.0, boss=True, title=title)
        e.mid = True
        e.intro = True
        e.facing = -1
        self.enemies.append(e)
        self.boss_ref = e
        self._set_banner(f"중간 보스 · {title}", MID_BANNER_T)

    def _enemy_speed_mult(self) -> float:
        """x2 base, +10 % compound per stage, growth capped (stage 1: 2.0, 5: 2.93, 8: 3.9, 13+: 6.0)."""
        grow = (1.0 + ENEMY_SPEED_PER_STAGE) ** max(0, self.stage_no - 1)
        return ENEMY_SPEED_BASE * min(ENEMY_SPEED_STAGE_CAP, grow)

    def _make_enemy(self, rank_key: str, x: float, boss: bool = False, title: str | None = None) -> Enemy:
        r = self._rank(rank_key)
        mult = self.stage["mult"] if self.stage else DEFAULT_DIFFICULTY["normal"]
        e = Enemy()
        e.id = self.next_id
        self.next_id += 1
        e.rank = rank_key
        e.palette = str(r.get("sprite") or rank_key)
        e.element = r["element"] if r.get("element") in ELEMENT_KEYS else self.rng.choice(ELEMENT_KEYS)
        e.boss = boss
        e.x = float(x)
        e.y = float(self.ground_y)
        if boss:
            e.kind = "boss"
            e.pattern = r.get("pattern", "mid")
            e.scale = int(r.get("boss_scale", 4))
            base_hp = r.get("boss_hp", max(15, int(r.get("hp", 1)) * 10))
            grow = 1.0 + float(self.progression["boss_hp_per_stage"]) * max(0, self.stage_no - 1)
            e.hp_max = max(1, int(round(base_hp * mult["hp"] * grow)))
            e.speed = float(r.get("boss_speed", r.get("speed", 100))) * mult["speed"] * self._enemy_speed_mult()
            e.fire_rate = float(r.get("fire_rate", 0.8))
            e.stop_dist = self.rng.uniform(140, 220)
            e.dash_cd = self.rng.uniform(2.5, 4.0)
            e.spread_cd = self.rng.uniform(1.5, 2.5)
            e.summon_cd = 4.0          # first summon sooner; 8 s between summons afterwards
            e.stamp_cd = 2.5
            if e.pattern == "brawler":
                e.jump_cd = self.rng.uniform(3.0, 5.0)
                e.ranged_cd = self.rng.uniform(1.0, 2.0)
        else:
            e.kind = r.get("kind", "grunt")
            if e.kind not in ("grunt", "elite"):
                e.kind = "elite"
            e.scale = int(r.get("scale", 2))
            # 스테이지가 오를수록 잡병도 한 방에 죽지 않는다 (stage 1: x1.0, 3: x1.7, 6: x2.75 ...)
            grow = 1.0 + float(self.progression["hp_per_stage"]) * max(0, self.stage_no - 1)
            e.hp_max = max(1, int(round(int(r.get("hp", 1)) * mult["hp"] * grow)))
            e.speed = float(r.get("speed", 60)) * mult["speed"] * self._enemy_speed_mult()
            e.move_t = self.rng.uniform(*MOVE_T["walk"])
            e.fire_rate = float(r.get("fire_rate", 0.2)) * (1.0 + 0.5 * (mult["speed"] - 1.0))
            e.stop_dist = self.rng.uniform(150, 300) if e.kind == "grunt" else self.rng.uniform(120, 220)
            e.fire_cd = self.rng.uniform(0.6, 1.5)
            e.jump_cd = self.rng.uniform(1.5, 3.5)
        e.hp = e.hp_max
        if r.get("hit_w") and r.get("hit_h"):          # explicit logic hitbox (custom sprite sheets)
            e.w = float(r["hit_w"]) * (e.scale if r.get("hit_scaled") else 1)
            e.h = float(r["hit_h"]) * (e.scale if r.get("hit_scaled") else 1)
        else:
            e.w = ENEMY_W * e.scale / 2
            e.h = ENEMY_H * e.scale / 2
        # v1.9: melee reach / preference, sprite projectiles, spawn time (balance log)
        e.reach = e.w * 0.6 + ENEMY_REACH_PAD
        e.melee = bool(r.get("melee", False))
        if e.melee and not boss:
            e.stop_dist = e.reach * 0.9
        e.proj = r["proj"] if isinstance(r.get("proj"), dict) else None
        e.attack_cd = self.rng.uniform(0.3, 1.0)
        e.born = self.play_t
        self._bal_enemy(e, killed=False)
        e.label = title or r.get("title", rank_key)
        e.facing = 1 if e.x < self.width / 2 else -1
        if self.anim_lens:
            e.hold_frame = max(0, int(self.anim_lens.get("death", 8)) - 1)
        return e

    # ------------------------------------------------------------ play update
    def _update_play(self, dt: float):
        self.play_t += dt
        self.slow_t = max(0.0, self.slow_t - dt)
        if self.inv_flash is not None:
            self.inv_flash_t -= dt
            if self.inv_flash_t <= 0:
                self.inv_flash = None
        edt = dt * SLOW_FACTOR if self.slow_t > 0 else dt          # enemies / enemy bullets under 야근 커피
        self._update_player(dt)
        self._update_spawning(edt)
        for e in self.enemies:
            self._update_enemy(e, edt)
        self._update_allies(dt)
        self._update_words(dt)
        self._update_bullets(dt, edt)
        self._update_zones(dt)
        self._update_items(dt)
        self._collide()
        self._cleanup()
        self._update_effects(dt)
        self._check_progress(dt)
        if self.score > self.best:
            self.best = self.score

    def _player_box(self):
        p = self.player
        h = PLAYER_H // 2 if p.crouch else PLAYER_H
        return (p.x - PLAYER_W / 2, p.y - h, p.x + PLAYER_W / 2, p.y)

    def _update_player(self, dt: float):
        p = self.player
        keys = self.keys
        if p.dead:
            p.death_t += dt
            p.tick_anim(dt)
            if p.death_t >= 1.0:
                self._after_death()
            return
        p.inv_t = max(0.0, p.inv_t - dt)
        p.drop_t = max(0.0, p.drop_t - dt)
        p.jump_buf = max(0.0, p.jump_buf - dt)
        p.shoot_t = max(0.0, p.shoot_t - dt)
        p.skill_cd = max(0.0, p.skill_cd - dt)
        p.ult_t = max(0.0, p.ult_t - dt)
        p.melee_t = max(0.0, p.melee_t - dt)
        p.combo_t = max(0.0, p.combo_t - dt)
        if p.combo_t <= 0:
            p.combo = 0
        c = self.char
        move = (1 if "right" in keys else 0) - (1 if "left" in keys else 0)
        p.crouch = ("down" in keys) and p.on_ground
        if move:
            p.facing = move
        p.vx = 0.0 if p.crouch else move * WALK_SPEED * self._speed_mult(c)
        if p.jump_buf > 0 and p.on_ground:
            p.jump_buf = 0.0
            if p.crouch and p.on_platform:
                p.drop_t = 0.3          # drop through platform
                p.on_ground = False
                p.crouch = False
            else:
                p.vy = -JUMP_VEL * self._jump_mult(c)
                p.on_ground = False
                p.crouch = False
        p.vy += GRAVITY * dt
        prev_y = p.y
        p.x += p.vx * dt
        p.y += p.vy * dt
        p.x = max(PLAYER_W / 2, min(self.width - PLAYER_W / 2, p.x))
        landed = False
        p.on_platform = False
        if p.vy >= 0:
            if p.drop_t <= 0:
                for (px, py, pw, ph) in self.platforms:
                    if prev_y <= py + 0.01 and p.y >= py and px <= p.x <= px + pw:
                        p.y = py
                        landed = True
                        p.on_platform = True
                        break
            if not landed and p.y >= self.ground_y and not self._over_pit(p.x):
                p.y = float(self.ground_y)
                landed = True
        if landed:
            p.vy = 0.0
            p.on_ground = True
        else:
            p.on_ground = False
            if p.crouch:
                p.crouch = False
        if p.y > self.height + 80:
            self._kill_player(force=True)   # fell into a pit
            return
        # weapon timer
        if p.weapon in WEAPON_TIME:
            p.weapon_t -= dt
            if p.weapon_t <= 0:
                p.weapon, p.weapon_t = "normal", 0.0
        # firing
        p.fire_cd -= dt
        melee = c.get("melee") or None
        if "fire" in keys and p.fire_cd <= 0:
            targets = self._melee_targets(p, melee) if melee else []
            if targets or (melee and melee.get("only")):
                self._player_melee(p, melee, targets)       # enemy in reach (or melee-only character)
            elif len(self.bullets) < MAX_BULLETS:
                self._player_fire(p, c)
        elif "fire" not in keys and p.fire_cd < 0:
            p.fire_cd = 0.0
        # anim
        if not p.on_ground:
            p.set_anim("jump" if p.vy < 0 else "fall")
        elif p.crouch:
            p.set_anim("crouch_shoot" if p.shoot_t > 0 else "crouch")
        elif abs(p.vx) > 1:
            p.set_anim("shoot_run" if p.shoot_t > 0 else "run")
        else:
            p.set_anim("shoot" if p.shoot_t > 0 else "idle")
        p.tick_anim(dt)

    def _player_fire(self, p: Player, c: dict):
        """Spawn bullets for the current weapon. Gun height is relative to the hitbox (PLAYER_H)."""
        gun_y = p.y - (PLAYER_H * 0.35 if p.crouch else PLAYER_H * 0.62)
        gx = p.x + p.facing * (PLAYER_W / 2 + 6)
        dmg = self._phys_dmg(c)
        mdmg = self._magic_dmg(c)
        el = self.element_key
        pierce = bool(c.get("pierce", False))
        rate = FIRE_RATE * self._fire_rate_mult(c)
        spd = self._bullet_speed(c)
        w = p.weapon
        if w == "laser":
            edge = self.width + 40 if p.facing > 0 else -40
            cx = (gx + edge) / 2
            self.bullets.append(Bullet(cx, gun_y, abs(edge - gx), 3, 0.0, 0.0, "player",
                                       dmg=max(1, (dmg + 1) // 2), pierce=True, kind="laser", ttl=0.08,
                                       mdmg=mdmg, element=el))
            rate *= 0.5
        elif w == "homing":
            mspd = MISSILE_SPEED * spd / BULLET_SPEED
            self.bullets.append(Bullet(gx, gun_y, 10, 5, p.facing * mspd, 0.0, "player",
                                       dmg=dmg + 2, pierce=False, kind="missile", ttl=None, mdmg=mdmg, element=el))
            p.ammo -= 1
            rate *= 0.7
            if p.ammo <= 0:
                p.weapon, p.ammo = "normal", 0
        elif w == "spread":
            for ang in (-SPREAD_ANGLE, 0.0, SPREAD_ANGLE):
                if len(self.bullets) >= MAX_BULLETS:
                    break
                self.bullets.append(Bullet(gx, gun_y, 8, 4, p.facing * spd * math.cos(ang),
                                           spd * math.sin(ang), "player", dmg=dmg, pierce=pierce,
                                           mdmg=mdmg, element=el))
        else:
            self.bullets.append(Bullet(gx, gun_y, 8, 4, p.facing * spd, 0.0, "player",
                                       dmg=dmg, pierce=pierce, mdmg=mdmg, element=el))
            if w == "rapid":
                rate *= 2.0
        p.fire_cd = 1.0 / max(0.5, rate)
        p.shoot_t = 0.25
        self._bal_add("shots", 1)

    # ------------------------------------------------------------ melee / skill
    def _melee_style(self) -> str:
        m = self.char.get("melee") or {}
        return str(m.get("style", "hip"))

    def _melee_targets(self, p: Player, melee: dict) -> list:
        reach = float(melee.get("range", 45))
        both = bool(melee.get("both_sides", False))
        head = p.y - PLAYER_H - 6
        hits = []
        for e in self.enemies:
            if not e.alive:
                continue
            dx = e.x - p.x
            if abs(dx) > reach + e.w / 2:
                continue
            if not both and dx * p.facing < -e.w / 2:
                continue                        # behind the player
            if e.y - e.h > p.y + 4 or e.y < head:
                continue                        # not at the player's height
            hits.append(e)
        return hits

    def _player_melee(self, p: Player, melee: dict, targets: list):
        """v1.9 per-character melee. knife: 3-hit combo, 3rd hit knocks back hard. hammer: slow, wide knockback
        + ground shockwave bullet. whip: long reach, every target in reach, magic damage. hip: legacy."""
        style = str(melee.get("style", "hip"))
        hits = max(1, int(melee.get("hits", 1)))
        dmg = max(1, int(melee.get("damage", 4))) + self.upgrades.get("str", 0) // 3   # bought 힘 also helps melee
        dmg += int(self._equip_fx().get("damage", 0))
        mdmg = self._magic_dmg(self.char) if style in ("whip", "hip") or melee.get("magic") else 0
        if style == "whip":
            mdmg = max(mdmg, self._magic_dmg(self.char))
        knock = float(melee.get("knockback", 260)) * 0.12
        p.combo = (p.combo % hits) + 1
        p.combo_t = 0.9
        final = p.combo == hits
        if style == "knife":
            knock = knock * 2.2 if final else 0.0          # the first two cuts hold the target in place
        if not melee.get("pierce", style == "whip") and len(targets) > 1:
            targets = sorted(targets, key=lambda e: abs(e.x - p.x))[:2]
        for e in targets:
            d = 1 if e.x >= p.x else -1
            e.x += d * knock * (MELEE_KNOCK_BOSS if e.boss else 1.0)
            self._strike(e, dmg, mdmg, self.element_key)
            self._bal_add("melee_dmg", dmg + mdmg)
        if targets:
            self._effect("text", p.x + p.facing * 20, p.y - PLAYER_H - 8, text=str(melee.get("text", "퍽!")))
        self._effect("slash", p.x + p.facing * float(melee.get("range", 45)) * 0.5, p.y - PLAYER_H * 0.55, text=style)
        if style == "hammer" and melee.get("wave", True) and final:
            self.bullets.append(Bullet(p.x + p.facing * 18, self.ground_y - 6, 26, 12, p.facing * 380.0, 0.0,
                                       "player", dmg=max(1, dmg // 2), pierce=True, kind="wave", ttl=0.7,
                                       mdmg=0, element=self.element_key))
        cd = float(melee.get("cooldown", MELEE_CD))
        if style == "knife":
            cd = float(melee.get("hit_gap", 0.15)) if not final else cd
        p.fire_cd = cd
        p.shoot_t = 0.2
        p.melee_t = 0.25 if style != "hammer" else 0.4

    def _use_skill(self):
        """C: ultimate. config "storm" per character: kind "storm" (paper storm in front, dongil) or
        "quake" (hammer shockwave centred on the player, hyunki). Both are damage zones; the portrait burst
        (hud.ult) plays on top for ULT_T seconds."""
        p = self.player
        storm = self.char.get("storm")
        if not storm or p.dead or p.skill_cd > 0 or len(self.zones) >= MAX_ZONES:
            return
        kind = str(storm.get("kind", "storm"))
        if kind not in ZONE_KINDS:
            kind = "storm"
        w = float(storm.get("width", 160))
        dur = float(storm.get("duration", 3.0))
        centered = bool(storm.get("centered", kind == "quake"))
        zx = p.x if centered else p.x + p.facing * (w / 2 + 10)
        self.zones.append({"kind": kind, "x": zx, "w": w, "t": dur, "ttl": dur,
                           "tick": 0.0, "every": float(storm.get("tick", 0.4)),
                           "dmg": max(1, int(storm.get("damage", 1))) + self.upgrades.get("str", 0) // 3,
                           "mdmg": self._magic_dmg(self.char), "element": self.element_key,
                           "knock": float(storm.get("knockback", 0.0))})
        p.skill_cd = float(storm.get("cooldown", 8.0))
        p.shoot_t = 0.3
        p.ult_t = ULT_T
        self._effect("text", p.x, p.y - PLAYER_H - 12, text=str(storm.get("label", "서류 스톰")))

    def _update_zones(self, dt: float):
        """Paper storm: removes enemy bullets inside and hits every enemy inside each tick."""
        if not self.zones:
            return
        alive = []
        for z in self.zones:
            z["t"] -= dt
            if z["t"] <= 0:
                continue
            box = (z["x"] - z["w"] / 2, self.ground_y - ZONE_H, z["x"] + z["w"] / 2, self.ground_y + 4)
            for b in self.bullets:
                if b.owner == "enemy" and not b.dead and _overlap(b.box(), box):
                    b.dead = True
            z["tick"] -= dt
            if z["tick"] <= 0:
                z["tick"] = z["every"]
                knock = float(z.get("knock", 0.0))
                for e in self.enemies:
                    if e.alive and _overlap(e.box(), box):
                        self._strike(e, z["dmg"], z.get("mdmg", 0), z.get("element"))
                        if knock > 0:
                            e.x += (1 if e.x >= z["x"] else -1) * knock * (MELEE_KNOCK_BOSS if e.boss else 1.0)
            alive.append(z)
        self.zones = alive

    # ------------------------------------------------------------ shop
    def _open_shop(self):
        self.shop_index = 0
        self.shop_msg = ""
        self._set_banner(None)
        self._set_state("shop")

    def _shop_cost(self, key: str) -> int:
        _label, base, growth, _mx = self.shop_items[key]
        return int(round(base * growth ** self.upgrades.get(key, 0), -1))

    def _shop_select(self, key: str | None = None):
        key = key or SHOP_ORDER[self.shop_index % len(SHOP_ORDER)]
        if key == "next":
            self._start_stage(self.stage_no + 1)
            return
        label, _base, _growth, mx = self.shop_items[key]
        if mx > 0 and self.upgrades[key] >= mx:          # max 0 = unlimited
            self.shop_msg = f"{label}: 최대 단계"
            return
        cost = self._shop_cost(key)
        if self.score < cost:
            self.shop_msg = f"점수 부족 ({cost - self.score:,}점 모자람)"
            return
        self.score -= cost                      # spent score never comes back: upgrades cost the high score
        self.upgrades[key] += 1
        if key == "life":
            self.lives = min(9, self.lives + 1)
        self.shop_msg = f"{label} 구매 (Lv{self.upgrades[key]})"

    def _shop_view(self) -> dict:
        rows = []
        for key in SHOP_ORDER:
            if key == "next":
                rows.append({"key": key, "label": "다음 스테이지 ▶", "cost": 0, "level": 0, "max": 0, "afford": True})
                continue
            label, _base, _growth, mx = self.shop_items[key]
            lv = self.upgrades.get(key, 0)
            cost = self._shop_cost(key)
            rows.append({"key": key, "label": label, "cost": cost, "level": lv, "max": max(0, mx),
                         "afford": (mx <= 0 or lv < mx) and self.score >= cost})
        return {"index": self.shop_index % len(SHOP_ORDER), "items": rows, "msg": self.shop_msg,
                "stats": self._eff_stats(self.char)}

    # ------------------------------------------------------------ town (v1.9: every 5th stage)
    def _open_town(self):
        if self.shop_stock_stage != self.stage_no and hasattr(economy, "make_shop_stock"):
            self.shop_stock = list(economy.make_shop_stock(self.rng, self.stage_no, 10))
            self.shop_stock_stage = self.stage_no
        self.shop_index = 0
        self.shop_msg = ""
        self.town = {"tab": 0, "index": {k: 0 for k in TOWN_TABS}, "msg": "", "store_mode": "list",
                     "game": 0, "stake_i": 0, "bet_i": 0, "streak": 0, "reels": None, "target": 0}
        self._set_banner(None)
        self._set_state("town")

    def _town_tab(self) -> str:
        return TOWN_TABS[self.town["tab"] % len(TOWN_TABS)]

    def _town_list(self, tab: str) -> list:
        """Selectable entries of a tab; the last is always ("next", None)."""
        if tab == "stat":
            rows = [("stat", k) for k in SHOP_ORDER if k != "next"]
        elif tab == "shop":
            rows = [("eq", i) for i in range(len(self.shop_stock))] + [("box", None)]
        elif tab == "store":
            if self.town["store_mode"] == "equipped":
                rows = [("slot", sl) for sl in economy.SLOTS]
            else:
                rows = [("item", i) for i in range(len(self.warehouse.items))]
        else:
            rows = [("game", i) for i in range(len(GAMBLE_GAMES))]
        rows.append(("next", None))
        return rows

    def _town_key(self, key: str):
        t = self.town
        if t is None:
            return
        tab = self._town_tab()
        rows = self._town_list(tab)
        idx = t["index"][tab] % len(rows)
        if key == "tab" or (key in ("up", "down") and tab in ("stat", "shop")):
            t["tab"] = (t["tab"] + (-1 if key == "up" else 1)) % len(TOWN_TABS)
            t["msg"] = ""
        elif key in ("up", "down") and tab == "store":
            t["store_mode"] = "equipped" if t["store_mode"] == "list" else "list"
            t["index"]["store"] = 0
        elif key in ("up", "down") and tab == "gamble":
            t["index"]["gamble"] = (idx + (-1 if key == "up" else 1)) % len(rows)
        elif key in ("left", "sel_left"):
            t["index"][tab] = (idx - 1) % len(rows)
            t["msg"] = ""
        elif key in ("right", "sel_right"):
            t["index"][tab] = (idx + 1) % len(rows)
            t["msg"] = ""
        elif key == "skill":
            self._town_alt(tab, rows[idx])
        elif key in ("confirm", "fire") and self.state_t >= CONFIRM_GUARD:
            self._town_confirm(tab, rows[idx])
        if tab == "store" and t["index"]["store"] >= len(self._town_list("store")):
            t["index"]["store"] = max(0, len(self._town_list("store")) - 1)

    def _town_confirm(self, tab: str, row: tuple):
        t = self.town
        kind, arg = row
        if kind == "next":
            self.town = None
            self._start_stage(self.stage_no + 1)
            return
        if kind == "stat":
            self._shop_select(arg)
            t["msg"] = self.shop_msg
        elif kind == "eq":
            eq = self.shop_stock[arg]
            price = int(economy.buy_price(eq, self.stage_no))
            if self.money < price:
                t["msg"] = f"돈 부족 (₩{price - self.money:,} 모자람)"
            elif not self.warehouse.add(eq):
                t["msg"] = "창고가 가득 찼습니다"
            else:
                self.money -= price
                self.shop_stock.pop(arg)
                t["msg"] = f"구매: {eq['name']} (₩{price:,})"
                self._bal_add("spent", price)
        elif kind == "box":
            price = int(economy.BOX_PRICE(self.stage_no))
            if self.money < price:
                t["msg"] = f"돈 부족 (₩{price - self.money:,} 모자람)"
                return
            self.money -= price
            self._bal_add("spent", price)
            res = economy.open_box(self.rng, self.stage_no)
            self._effect("boxopen", self.width / 2, self.ground_y - 60)
            if res["kind"] == "equip" and res.get("equip"):
                eq = res["equip"]
                ok = self.warehouse.add(eq)
                t["msg"] = f"랜덤박스: [{economy.RARITY_LABEL[eq['rarity']]}] {eq['name']}" + ("" if ok else " (창고 가득, 자동 판매)")
                if not ok:
                    self.money += int(economy.sell_price(eq, self.stage_no))
            elif res["kind"] == "item" and res.get("item"):
                ok = self._pickup(res["item"])
                t["msg"] = f"랜덤박스: {ITEM_LABEL.get(res['item'], res['item'])}" + ("" if ok else " (인벤 가득)")
            elif res["kind"] == "money":
                self.money += int(res.get("money", 0))
                t["msg"] = f"랜덤박스: ₩{int(res.get('money', 0)):,}!"
            else:
                t["msg"] = f"랜덤박스: {res.get('text', '꽝')}"
        elif kind == "item":
            eq = self.warehouse.equip(arg)
            t["msg"] = f"장착: {eq['name']}" if eq else "장착 실패"
            self.player.shield = min(self.player.shield, self._shield_max())
        elif kind == "slot":
            if self.warehouse.equipped.get(arg) is None:
                t["msg"] = "빈 슬롯"
            elif self.warehouse.unequip(arg):
                t["msg"] = f"{economy.SLOT_LABEL[arg]} 해제"
            else:
                t["msg"] = "창고가 가득 찼습니다"
        elif kind == "game":
            self._town_gamble(arg)

    def _town_alt(self, tab: str, row: tuple):
        """C key: sell (warehouse list) / change target, stake or bet (gambling)."""
        t = self.town
        kind, arg = row
        if tab == "store" and kind == "item":
            eq = self.warehouse.remove(arg)
            gain = int(economy.sell_price(eq, self.stage_no))
            self.money += gain
            t["msg"] = f"판매: {eq['name']} +₩{gain:,}"
        elif tab == "gamble" and kind == "game":
            if arg == 0:
                t["target"] = (t["target"] + 1) % len(economy.SLOTS)
            elif arg == 1:
                t["stake_i"] = (t["stake_i"] + 1) % len(DOUBLE_STAKES)
            else:
                t["bet_i"] = (t["bet_i"] + 1) % len(SLOT_BETS)
            t["msg"] = ""

    def _gamble_target_slot(self) -> str | None:
        slots = [sl for sl in economy.SLOTS if self.warehouse.equipped.get(sl) is not None]
        if not slots:
            return None
        return slots[self.town["target"] % len(slots)]

    def _town_gamble(self, game: int):
        t = self.town
        if game == 0:
            sl = self._gamble_target_slot()
            if sl is None:
                t["msg"] = "장착한 장비가 없습니다"
                return
            eq, self.money, text = economy.gamble_upgrade(self.rng, self.warehouse.equipped[sl], self.money)
            self.warehouse.equipped[sl] = eq
            t["msg"] = f"{eq['name']}: {text}"
        elif game == 1:
            stake = max(100, int(self.money * DOUBLE_STAKES[t["stake_i"]]))
            if self.money < stake:
                t["msg"] = "돈이 부족합니다"
                return
            self.money -= stake
            ok, payout = economy.gamble_double(self.rng, stake, t["streak"])
            if ok:
                self.money += payout
                t["streak"] += 1
                t["msg"] = f"성공! ₩{stake:,} → ₩{payout:,} (연승 {t['streak']})"
            else:
                t["streak"] = 0
                t["msg"] = f"실패… ₩{stake:,} 잃음"
        else:
            bet = SLOT_BETS[t["bet_i"]]
            if self.money < bet:
                t["msg"] = "돈이 부족합니다"
                return
            self.money -= bet
            res = economy.gamble_slots(self.rng, bet, self.stage_no)
            self.money += int(res.get("payout", 0))
            t["reels"] = list(res.get("reels") or [])
            prize = res.get("prize")
            if prize and prize.get("kind") == "equip" and prize.get("equip"):
                if not self.warehouse.add(prize["equip"]):
                    self.money += int(economy.sell_price(prize["equip"], self.stage_no))
            elif prize and prize.get("kind") == "item" and prize.get("item"):
                self._pickup(prize["item"])
            t["msg"] = str(res.get("text", ""))
        self._bal_add("gambles", 1)

    def _town_view(self) -> dict | None:
        t = self.town
        if t is None or self.state != "town":
            return None
        tab = self._town_tab()
        rows = self._town_list(tab)
        stock = list(self.shop_stock) + [{"kind": "box", "price": int(economy.BOX_PRICE(self.stage_no))
                                         if hasattr(economy, "BOX_PRICE") else 0}]
        afford = []
        for it in stock:
            price = it["price"] if it.get("kind") == "box" else int(economy.buy_price(it, self.stage_no))
            afford.append(self.money >= price)
        prices = [it["price"] if it.get("kind") == "box" else int(economy.buy_price(it, self.stage_no)) for it in stock]
        tgt = self._gamble_target_slot()
        return {"tab": tab, "tabs": [TOWN_TAB_LABEL[k] for k in TOWN_TABS], "tab_index": t["tab"] % len(TOWN_TABS),
                "index": t["index"][tab] % len(rows), "count": len(rows), "msg": t["msg"], "stage": self.stage_no,
                "hint": TOWN_HINT[tab], "money": self.money,
                "stat": {"items": self._shop_view()["items"]},
                "shop": {"stock": stock, "afford": afford, "prices": prices},
                "store": {"items": [dict(e) for e in self.warehouse.items],
                          "equipped": {k: (dict(v) if v else None) for k, v in self.warehouse.equipped.items()},
                          "mode": t["store_mode"], "cap": self.warehouse.CAP,
                          "sell": [int(economy.sell_price(e, self.stage_no)) for e in self.warehouse.items],
                          "upgrade_cost": {k: (int(economy.upgrade_cost(v)) if v else 0)
                                           for k, v in self.warehouse.equipped.items()}},
                "gamble": {"games": list(GAMBLE_GAMES), "game": t["index"]["gamble"] % len(rows),
                           "stake": max(100, int(self.money * DOUBLE_STAKES[t["stake_i"]])),
                           "stake_pct": int(DOUBLE_STAKES[t["stake_i"]] * 100), "streak": t["streak"],
                           "reels": t["reels"], "bet": SLOT_BETS[t["bet_i"]],
                           "target": (list(economy.SLOTS).index(tgt) if tgt else None),
                           "target_eq": (dict(self.warehouse.equipped[tgt]) if tgt else None),
                           "target_cost": (int(economy.upgrade_cost(self.warehouse.equipped[tgt]) * 1.5) if tgt else 0)}}

    def _drop_item(self, e: Enemy):
        """Kill drops: a coin every time (v1.9 money), plus the usual item roll; bosses drop equipment."""
        x = min(self.width - 20, max(20, e.x))
        mkind = "boss" if (e.boss and not e.mid) else "mid" if e.boss else e.kind
        money = economy.money_drop(self.rng, mkind, self.stage_no, self.stage["mult"].get("money", 1.0),
                                   float(self._equip_fx().get("money", 0.0)))
        if money > 0:
            self.items.append(Item(x + self.rng.uniform(-14, 14), e.y - 10, "coin", value=money))
        if e.boss:
            if not e.mid:
                self._boss_gear_drop()
            if len(self.items) < MAX_ITEMS:
                kind = "life" if self.lives < self.lives_max + 2 else self.rng.choice(("laser", "homing", "spread", "bomb"))
                self.items.append(Item(x, e.y - 10, kind))
            return
        if len(self.items) >= MAX_ITEMS:
            return
        chance = float(self.progression["drop_elite" if e.kind == "elite" else "drop_grunt"])
        if self.rng.random() >= chance:
            return
        kinds = list(ITEM_DROP_WEIGHT)
        kind = self.rng.choices(kinds, [ITEM_DROP_WEIGHT[k] for k in kinds])[0]
        self.items.append(Item(x, e.y - 10, kind))

    def _boss_gear_drop(self):
        """Department final boss: one piece of equipment straight into the warehouse (sold if it is full)."""
        if not hasattr(economy, "make_equipment"):
            return
        rarity = economy.roll_rarity(self.rng, economy.BOSS_RARITY)
        slot = self.rng.choice(economy.SLOTS)
        eq = economy.make_equipment(self.rng, slot, rarity, level=min(3, self.stage_no // 6), stage=self.stage_no)
        self._gear_to_warehouse(eq, "보스 전리품")

    def _gear_to_warehouse(self, eq: dict, why: str):
        p = self.player
        name = str(eq.get("name", "장비"))
        rl = economy.RARITY_LABEL.get(eq.get("rarity"), "") if hasattr(economy, "RARITY_LABEL") else ""
        if self.warehouse.add(eq):
            msg = f"{why} · [{rl}] {name} → 창고"
        else:
            gain = int(economy.sell_price(eq, self.stage_no)) if hasattr(economy, "sell_price") else 0
            self.money += gain
            msg = f"{why} · 창고 가득 → {name} 자동 판매 ₩{gain:,}"
        self._equip_msg = msg
        self._set_banner(msg, EQUIP_BANNER_T)
        self._effect("text", p.x, p.y - PLAYER_H - 24, text=name)
        self._bal_add("gear", 1)

    def _pickup(self, kind: str, value: int = 0) -> bool:
        """Floor item touched. Coins are money at once; everything else goes to an inventory slot (stacks)."""
        p = self.player
        if kind == "coin":
            self.money += int(value)
            self._bal_add("money", int(value))
            self._effect("coin", p.x, p.y - PLAYER_H - 6, text=f"+₩{int(value):,}")
            return True
        for i, slot in enumerate(self.inventory):
            if slot and slot["kind"] == kind and slot["count"] < INV_STACK:
                slot["count"] += 1
                self._flash_slot(i)
                return True
        for i, slot in enumerate(self.inventory):
            if slot is None:
                self.inventory[i] = {"kind": kind, "count": 1}
                self._flash_slot(i)
                self._effect("text", p.x, p.y - PLAYER_H - 12, text=f"{ITEM_LABEL.get(kind, kind)} [{i + 1}]")
                return True
        return False                            # full: the item stays on the floor

    def _flash_slot(self, i: int):
        self.inv_flash = i
        self.inv_flash_t = INV_FLASH_T

    def _use_slot(self, i: int):
        if not (0 <= i < INV_SLOTS) or self.player.dead:
            return
        slot = self.inventory[i]
        if slot is None:
            return
        self._use_item(slot["kind"])
        slot["count"] -= 1
        if slot["count"] <= 0:
            self.inventory[i] = None
        self._flash_slot(i)
        self._bal_add("items_used", 1)

    def _give_item(self, kind: str):
        """Legacy direct-apply (kept for tests / box prizes)."""
        self._use_item(kind)

    def _use_item(self, kind: str):
        p = self.player
        if kind == "life":
            self.lives = min(self.lives_max + 2, self.lives + 1)
        elif kind == "homing":
            p.weapon, p.ammo, p.weapon_t = "homing", HOMING_AMMO, 0.0
        elif kind in WEAPON_TIME:
            p.weapon, p.weapon_t, p.ammo = kind, WEAPON_TIME.get(kind, 10.0), 0
        elif kind == "bomb":
            self._bomb()
        elif kind == "coffee":
            self.slow_t = COFFEE_T
        elif kind == "decoy":
            self.allies = [a for a in self.allies if a.kind != "decoy"]
            a = Ally("decoy", p.x, p.y, DECOY_T, palette=self.char_key)
            a.facing = p.facing
            self.allies.append(a)
        elif kind == "drone":
            self.allies = [a for a in self.allies if a.kind != "drone"]
            self.allies.append(Ally("drone", p.x, p.y - PLAYER_H - 24, DRONE_T))
        elif kind == "dog":
            self.allies = [a for a in self.allies if a.kind != "dog"]
            a = Ally("dog", p.x - p.facing * 24, self.ground_y, DOG_T)
            a.facing = p.facing
            self.allies.append(a)
        self._effect("text", p.x, p.y - PLAYER_H - 12, text=ITEM_LABEL.get(kind, kind))

    def _bomb(self):
        """결재 폭탄: every grunt / elite on screen dies, bosses lose BOMB_BOSS_FRAC of max hp, enemy shots vanish."""
        p = self.player
        for e in list(self.enemies):
            if not e.alive:
                continue
            if e.boss:
                self._strike(e, max(1, int(e.hp_max * BOMB_BOSS_FRAC)), 0, None)
            else:
                self._strike(e, e.hp + 999, 0, None)
        for b in self.bullets:
            if b.owner == "enemy":
                b.dead = True
        for k in range(3):
            x = self.width * (0.25 + 0.25 * k)
            self.bullets.append(Bullet(x, self.ground_y - 40, 0, 0, 0.0, 0.0, "player", dmg=0, kind="blast",
                                       ttl=BLAST_T, r=120.0))
        self._effect("text", p.x, p.y - PLAYER_H - 30, text="결재 완료!")

    # ------------------------------------------------------------ allies (v1.9 companions)
    def _update_allies(self, dt: float):
        if not self.allies:
            return
        p = self.player
        keep = []
        for a in self.allies:
            a.t -= dt
            a.fire_cd -= dt
            if a.t <= 0 or (a.kind == "decoy" and a.hp <= 0):
                self._effect("spark", a.x, a.y - 10)
                continue
            if a.kind == "decoy":
                if a.fire_cd <= 0 and not p.dead:
                    tgt = self._nearest_enemy(a.x)
                    if tgt is not None:
                        a.facing = 1 if tgt.x >= a.x else -1
                        gy = a.y - PLAYER_H * 0.62
                        self.bullets.append(Bullet(a.x + a.facing * 10, gy, 8, 4, a.facing * BULLET_SPEED, 0.0,
                                                   "player", dmg=self._phys_dmg(self.char), mdmg=0))
                        a.fire_cd = DECOY_FIRE
                        a.set_anim("shoot")
                        a.anim_t = 0.0
                elif a.shoot_anim_done():
                    a.set_anim("idle")
            elif a.kind == "drone":
                a.x += (p.x - a.x) * min(1.0, 6.0 * dt)
                a.y = p.y - PLAYER_H - 24 + 4 * math.sin(self.play_t * 5.0)
                a.facing = p.facing
                if a.fire_cd <= 0 and not p.dead and self._nearest_enemy(a.x) is not None:
                    self.bullets.append(Bullet(a.x, a.y, 8, 4, a.facing * MISSILE_SPEED * 0.8, 0.0, "player",
                                               dmg=1, kind="missile", ttl=4.0))
                    a.fire_cd = DRONE_FIRE
            elif a.kind == "dog":
                tgt = self._nearest_enemy(a.x)
                if tgt is not None:
                    d = tgt.x - a.x
                    a.facing = 1 if d > 0 else -1
                    if abs(d) > tgt.w / 2 + 8:
                        a.vx = a.facing * DOG_SPEED
                        a.x += a.vx * dt
                    else:
                        a.vx = 0.0
                        if a.fire_cd <= 0:
                            tgt.x += a.facing * DOG_KNOCK * 0.12 * (MELEE_KNOCK_BOSS if tgt.boss else 1.0)
                            self._strike(tgt, DOG_DMG, 0, None)
                            self._effect("text", a.x, a.y - 22, text="왕!")
                            a.fire_cd = DOG_CD
                else:
                    d = (p.x - p.facing * 30) - a.x
                    a.vx = 0.0 if abs(d) < 6 else math.copysign(DOG_SPEED * 0.7, d)
                    a.x += a.vx * dt
                    a.facing = p.facing
                a.x = max(10.0, min(self.width - 10.0, a.x))
                a.y = float(self.ground_y)
                a.set_anim("run" if abs(a.vx) > 1 else "idle")
            a.tick_anim(dt)
            keep.append(a)
        self.allies = keep

    def _nearest_enemy(self, x: float):
        best, bd = None, 1e18
        for e in self.enemies:
            if e.alive and 0 <= e.x <= self.width:
                d = abs(e.x - x)
                if d < bd:
                    best, bd = e, d
        return best

    # ------------------------------------------------------------ falling words (v1.9 typing bonus)
    def _update_words(self, dt: float):
        if self.state != "play":
            return
        if self.words_left > 0 and self.phase == "wave" and not self.player.dead:
            self.word_next -= dt
            if self.word_next <= 0 and not self.words:
                self._spawn_word()
        keep = []
        for w in self.words:
            w["t"] += dt
            w["y"] += w["vy"] * dt
            if w["y"] >= self.ground_y - 8:
                self._effect("text", w["x"], self.ground_y - 20, text="놓쳤다…")
                continue
            keep.append(w)
        self.words = keep

    def _spawn_word(self):
        kind = self.rng.choices(WORD_KINDS, [WORD_WEIGHTS[k] for k in WORD_KINDS])[0]
        bank = [t for t in WORD_BANK.get(kind, []) if t and set(t) <= WORD_LETTERS]
        if not bank:
            self.words_left = 0
            return
        text = self.rng.choice(bank)
        x = self.rng.uniform(self.width * 0.25, self.width * 0.85)
        self.words.append({"text": text, "typed": 0, "x": x, "y": -20.0, "kind": kind, "t": 0.0, "vy": WORD_VY})
        self.words_left -= 1
        self.word_next = self.rng.uniform(6.0, 12.0)

    def _type_letter(self, ch: str):
        if not self.words or ch not in WORD_LETTERS:
            return
        w = self.words[0]
        if w["text"][w["typed"]] == ch:
            w["typed"] += 1
            self._bal_add("typed", 1)
            if w["typed"] >= len(w["text"]):
                self.words.pop(0)
                self._word_done(w)
        else:
            w["typed"] = 0                       # a wrong letter restarts the word
            w["y"] += 6

    def _word_done(self, w: dict):
        p = self.player
        kind = w["kind"]
        self._effect("word", w["x"], w["y"], text=w["text"])
        if kind == "wipe":
            for e in self.enemies:
                if e.alive:
                    if e.boss:
                        self._strike(e, max(1, int(e.hp_max * 0.2)), 0, None)
                    else:
                        self._strike(e, e.hp + 999, 0, None)
            for b in self.bullets:
                if b.owner == "enemy":
                    b.dead = True
            self._set_banner("전원 퇴근!", 1.2)
        elif kind == "gear" and hasattr(economy, "make_equipment"):
            table = getattr(economy, "WORD_RARITY", {"normal": 0.4, "rare": 0.4, "unique": 0.2})
            rarity = economy.roll_rarity(self.rng, table)
            eq = economy.make_equipment(self.rng, self.rng.choice(economy.SLOTS), rarity,
                                        level=min(5, self.stage_no // 5), stage=self.stage_no)
            self._gear_to_warehouse(eq, "타자 보너스")
        elif kind == "money":
            gain = economy.money_drop(self.rng, "word", self.stage_no, self.stage["mult"].get("money", 1.0),
                                      float(self._equip_fx().get("money", 0.0)))
            self.money += gain
            self._bal_add("money", gain)
            self._effect("coin", p.x, p.y - PLAYER_H - 6, text=f"+₩{gain:,}")
        elif kind == "life":
            self.lives = min(self.lives_max + 2, self.lives + 1)
            self._effect("text", p.x, p.y - PLAYER_H - 12, text="1UP")
        self._bal_add("words", 1)

    def _update_items(self, dt: float):
        if not self.items:
            return
        p = self.player
        pbox = self._player_box()
        alive = []
        for it in self.items:
            it.t -= dt
            it.age += dt
            if it.kind == "coin" and it.age >= COIN_HOME_DELAY and not p.dead:
                dx, dy = p.x - it.x, (p.y - PLAYER_H / 2) - it.y     # coins fly to the player
                d = math.hypot(dx, dy) or 1.0
                step = COIN_HOME_SPEED * dt
                if d <= step:
                    it.x, it.y = p.x, p.y
                else:
                    it.x += dx / d * step
                    it.y += dy / d * step
                it.on_ground = True
            elif not it.on_ground:
                it.vy += GRAVITY * dt
                it.y += it.vy * dt
                if it.y >= self.ground_y:
                    it.y = float(self.ground_y)
                    it.on_ground = True
                    if self._over_pit(it.x) and it.kind != "coin":
                        it.t = 0.0      # fell into a pit
            if it.t <= 0:
                continue
            if not p.dead and _overlap(it.box(), pbox):
                if self._pickup(it.kind, it.value):
                    continue
            alive.append(it)
        self.items = alive

    def _update_spawning(self, dt: float):
        self._update_warnings(dt)
        if not self.pending:
            return
        self.spawn_t -= dt
        if self.spawn_t > 0 or len(self.enemies) + len(self.warnings) >= MAX_ENEMIES:
            return
        rank, side, kind = self.pending.pop(0)
        self.spawn_t = float(self.wave_cfg["spawn_stagger"])
        if kind in WARN_T:
            x = self._special_spawn_x()
            if x is not None:
                self.warnings.append({"kind": kind, "x": x, "t": WARN_T[kind], "ttl": WARN_T[kind], "rank": rank})
                return
        x = -30.0 if side == 0 else self.width + 30.0
        e = self._make_enemy(rank, x)
        self.enemies.append(e)

    def _update_warnings(self, dt: float):
        """Ground / sky spawn warnings count down; when one expires the enemy appears at its x."""
        if not self.warnings:
            return
        keep = []
        for w in self.warnings:
            w["t"] -= dt
            if w["t"] > 0:
                keep.append(w)
                continue
            if len(self.enemies) >= MAX_ENEMIES:
                continue
            e = self._make_enemy(w["rank"], w["x"])
            e.spawn_kind = w["kind"]
            e.on_ground = False
            e.hop_vx = 0.0
            e.facing = 1 if self.player.x >= e.x else -1
            if w["kind"] == "ground":
                # start below the floor and pop out: the band bottom clips the part still underground
                e.y = float(self.ground_y) + e.h + 4.0
                e.vy = -math.sqrt(2.0 * GRAVITY * (e.h + 4.0 + POP_EXTRA))
                self._effect("dust", e.x, self.ground_y)
            else:
                e.y = SKY_Y
                e.vy = 0.0
                e.drop = True
            self.enemies.append(e)
        self.warnings = keep

    def _approach(self, e: Enemy, dt: float) -> None:
        """Grunt / elite approach with variety: walk, sprint bursts and short pauses (pauses only inside the
        band). A fresh landing after a drop / burst keeps the enemy still for LAND_STUN."""
        if e.land_t > 0:                        # (counted down in _update_enemy)
            e.vx = 0.0
            e.anim_rate = 1.0
            return
        e.move_t -= dt
        if e.move_t <= 0:
            total = sum(w for _, w in MOVE_WEIGHTS)
            roll = self.rng.random() * total
            mode = "walk"
            for m, w in MOVE_WEIGHTS:
                roll -= w
                if roll <= 0:
                    mode = m
                    break
            if mode == "pause" and (e.move_mode == "pause" or not self._in_band(e)):
                mode = "walk"                       # no double pauses, no idling off screen
            e.move_mode = mode
            e.move_t = self.rng.uniform(*MOVE_T[mode])
        if e.move_mode == "pause":
            e.vx = 0.0
            e.anim_rate = 1.0
            return
        sprint = e.move_mode == "sprint"
        e.anim_rate = SPRINT_MULT if sprint else 1.0
        e.vx = e.facing * e.speed * (SPRINT_MULT if sprint else 1.0)
        self._maybe_hop(e)

    def _maybe_hop(self, e: Enemy):
        """Enemies hop over pits when the edge is within 30 px ahead."""
        if not e.on_ground or e.vx == 0:
            return
        front = e.x + (e.w / 2) * (1 if e.vx > 0 else -1)
        for (px, pw) in self.pits:
            if e.vx > 0:
                gap = px - front
            else:
                gap = (px + pw) - front
                gap = -gap
            if 0 <= gap <= 30:
                jv = JUMP_VEL * 0.9
                air = 2 * jv / GRAVITY
                need = (pw + e.w + 30) / air
                e.hop_vx = max(abs(e.vx), need) * (1 if e.vx > 0 else -1)
                e.vy = -jv
                e.on_ground = False
                return

    def _update_enemy(self, e: Enemy, dt: float):
        p = self.player
        if not e.alive:
            e.death_t += dt
            e.vx = 0.0
            e.set_anim("death")
            e.tick_anim(dt)
            return
        tx, ty = self._aim_target(e)
        dx = tx - e.x
        dist = abs(dx)
        e.shoot_t = max(0.0, e.shoot_t - dt)
        e.land_t = max(0.0, e.land_t - dt)
        brawler = e.pattern == "brawler"
        if not brawler:
            e.attack_cd -= dt
            if e.attack_t > 0:                       # v1.9: grunt / elite / palette-boss melee swing
                self._enemy_melee_tick(e, dt)
                e.tick_anim(dt)
                return
        if e.on_ground:
            if not p.dead and e.dash_t <= 0 and not e.intro and e.attack_t <= 0 and e.hurt_t <= 0:
                e.facing = 1 if dx > 0 else -1
            if brawler:
                self._brawler_ai(e, dt, dx, dist)
            elif e.kind == "boss":
                self._boss_ai(e, dt, dx, dist)
            elif e.kind == "elite":
                self._elite_ai(e, dt, dx, dist)
            else:
                self._grunt_ai(e, dt, dx, dist)
            if not brawler and not p.dead and e.attack_cd <= 0 and e.land_t <= 0 and dist <= e.reach + PLAYER_W / 2 \
                    and abs(ty - e.y) < e.h and not e.intro and e.dash_t <= 0:
                e.attack_t = ENEMY_ATTACK_T
                e.hit_done = False
                e.vx = 0.0
                e.set_anim("attack" if self._rank(e.rank).get("sheet") else "shoot")
                e.shoot_t = ENEMY_ATTACK_T
        else:
            if brawler:
                self._brawler_ai(e, dt, dx, dist)
            elif e.hop_vx:
                e.vx = e.hop_vx
        # physics
        e.vy += GRAVITY * dt
        e.x += e.vx * dt
        e.y += e.vy * dt
        if e.y >= self.ground_y and e.vy >= 0:       # (a ground burst rises through the floor: vy < 0)
            e.y = float(self.ground_y)
            if not e.on_ground:
                e.on_ground = True
                e.hop_vx = 0.0
                e.vx = 0.0
                if e.drop or e.spawn_kind == "ground" or e.vy > 420:
                    self._effect("dust", e.x, e.y)
                if (e.drop or e.spawn_kind == "ground") and e.kind != "boss":
                    e.land_t = LAND_STUN
                    e.move_mode = "walk"
                    e.move_t = self.rng.uniform(*MOVE_T["walk"])
                e.drop = False
                e.spawn_kind = "side"
            e.vy = 0.0
        else:
            e.on_ground = False
        lo, hi = (-40.0, self.width + 40.0)
        if e.boss and not e.intro:
            lo, hi = (e.w / 2, self.width - e.w / 2)
        e.x = max(lo, min(hi, e.x))
        # anim
        if brawler:                     # brawler sheets only have: idle run attack attack2 hurt death jump
            if not e.on_ground:
                e.set_anim("jump")
            elif e.hurt_t > 0:
                e.set_anim("hurt")
            elif e.attack_t > 0:
                if e.anim not in ("attack", "attack2"):
                    e.set_anim("attack")
            elif abs(e.vx) > 1:
                e.set_anim("run")
            else:
                e.set_anim("idle")
        elif not e.on_ground:
            e.set_anim("jump")
        elif e.shoot_t > 0:
            e.set_anim("shoot")
        elif abs(e.vx) > 1:
            e.set_anim("run")
        else:
            e.set_anim("idle")
        e.tick_anim(dt)

    def _in_band(self, e: Enemy) -> bool:
        return 0 < e.x < self.width

    def _aim_target(self, e: Enemy) -> tuple[float, float]:
        """Where this enemy aims: the decoy (분신) for half of the enemies while one stands, else the player."""
        decoy = next((a for a in self.allies if a.kind == "decoy"), None)
        if decoy is not None and e.id % 2 == 0:
            return decoy.x, decoy.y
        return self.player.x, self.player.y

    def _enemy_melee_tick(self, e: Enemy, dt: float):
        """Melee swing in progress: stand still, deal contact damage once inside the hit window."""
        e.attack_t -= dt
        if e.on_ground:
            e.vx = 0.0
        elapsed = ENEMY_ATTACK_T - e.attack_t
        if not e.hit_done and ENEMY_HIT_WINDOW[0] <= elapsed <= ENEMY_HIT_WINDOW[1]:
            x0, x1 = sorted((e.x - e.w * 0.2 * e.facing, e.x + e.facing * (e.reach + 6)))
            box = (x0, e.y - e.h, x1, e.y + 2)
            p = self.player
            if not p.dead and p.inv_t <= 0 and _overlap(box, self._player_box()):
                self._hit_player()
                e.hit_done = True
            for a in self.allies:
                if a.kind == "decoy" and _overlap(box, a.box()):
                    a.hp -= 1
                    e.hit_done = True
        if e.attack_t <= 0:
            e.attack_t = 0.0
            e.attack_cd = self.rng.uniform(*ENEMY_MELEE_CD)
        # physics still applies (gravity while standing on the floor)
        e.vy += GRAVITY * dt
        e.y += e.vy * dt
        if e.y >= self.ground_y and e.vy >= 0:
            e.y = float(self.ground_y)
            e.vy = 0.0
            e.on_ground = True

    def _enemy_shoot_any(self, e: Enemy):
        """Rank with "proj": sprite projectile (optionally parabolic with a fuse); otherwise a plain shot."""
        if len(self.bullets) >= MAX_BULLETS:
            return
        m = self.stage["mult"].get("proj", 1.0) if self.stage else 1.0
        if e.proj:
            p = self.player
            gx, gy = e.x + e.facing * (e.w / 2), e.y - e.h * 0.6
            spd = ENEMY_BULLET_SPEED * float(e.proj.get("speed", 1.0)) * m
            if e.proj.get("gravity"):
                dx = (p.x - gx)
                t = max(0.5, min(1.4, abs(dx) / max(120.0, spd)))
                vx = dx / t
                vy = (p.y - gy) / t - 0.5 * GRAVITY * t
                fuse = float(e.proj["fuse"]) if e.proj.get("fuse") is not None else None
                self.bullets.append(Bullet(gx, gy, float(e.proj.get("w", 12)), float(e.proj.get("h", 12)), vx, vy,
                                           "enemy", kind="proj", sprite=e.palette, anim=str(e.proj.get("anim", "proj")),
                                           gravity=True, r=float(e.proj.get("blast", 0)), fuse=fuse))
            else:
                ang = math.atan2((p.y - PLAYER_H / 2) - gy, p.x - gx) if e.proj.get("aim") else (0.0 if e.facing > 0 else math.pi)
                self.bullets.append(Bullet(gx, gy, float(e.proj.get("w", 12)), float(e.proj.get("h", 8)),
                                           math.cos(ang) * spd, math.sin(ang) * spd, "enemy", kind="proj",
                                           sprite=e.palette, anim=str(e.proj.get("anim", "proj"))))
            e.shoot_t = 0.35
            return
        gun_y = e.y - e.h * 0.6
        self.bullets.append(Bullet(e.x + e.facing * (e.w / 2 + 4), gun_y, 8, 4,
                                   e.facing * ENEMY_BULLET_SPEED * m, 0.0, "enemy"))
        e.shoot_t = 0.3

    def _grunt_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        p = self.player
        e.fire_cd -= dt
        if dist > e.stop_dist or not self._in_band(e):
            self._approach(e, dt)
        else:
            e.vx = 0.0
            e.anim_rate = 1.0
        if e.fire_cd <= 0 and self._in_band(e) and not p.dead and e.fire_rate > 0:
            prob = e.fire_rate * (1.0 if e.vx == 0 else 0.3)
            if self.rng.random() < prob * dt:
                self._enemy_shoot_any(e)
                e.fire_cd = 0.6
        if e.melee and e.lunge_t <= 0 and e.on_ground and 90 < dist < 240 and self._in_band(e) \
                and self.rng.random() < 0.6 * dt:           # v1.9: melee grunts lunge at the player
            e.lunge_t = 0.35
            e.move_mode = "sprint"
            e.move_t = 0.35
        e.lunge_t = max(0.0, e.lunge_t - dt)

    def _elite_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        p = self.player
        e.fire_cd -= dt
        e.jump_cd -= dt
        if dist > e.stop_dist or not self._in_band(e):
            self._approach(e, dt)
        else:
            e.vx = 0.0
            e.anim_rate = 1.0
        if e.burst_left > 0:
            e.burst_t -= dt
            if e.burst_t <= 0:
                self._enemy_shoot_any(e)
                e.burst_left -= 1
                e.burst_t = 0.12
        elif e.fire_cd <= 0 and self._in_band(e) and not p.dead and e.fire_rate > 0:
            if self.rng.random() < e.fire_rate * dt:
                e.burst_left = 3
                e.burst_t = 0.0
                e.fire_cd = self.rng.uniform(1.2, 2.2)
        if e.jump_cd <= 0 and e.on_ground and e.land_t <= 0 and dist < 420 and self._in_band(e) \
                and self.rng.random() < float(self._rank(e.rank).get("jump_odds", 1.0)):
            e.vy = -JUMP_VEL * float(self._rank(e.rank).get("jump_mult", 0.8))
            e.on_ground = False
            e.hop_vx = e.vx
            e.jump_cd = self.rng.uniform(2.0, 4.0)

    def _boss_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        p = self.player
        if e.intro:
            e.vx = -e.speed
            if e.x <= self.width - 140:
                e.intro = False
                e.vx = 0.0
            return
        e.dash_cd -= dt
        e.spread_cd -= dt
        e.summon_cd -= dt
        e.stamp_cd -= dt
        if e.dash_t > 0:
            e.dash_t -= dt
            e.vx = e.dash_dir * DASH_SPEED
            if e.dash_t <= 0:
                e.vx = 0.0
                e.dash_cd = self.rng.uniform(3.0, 5.0)
            return
        if dist > e.stop_dist:
            e.vx = e.facing * e.speed
            self._maybe_hop(e)
        else:
            e.vx = 0.0
        if p.dead:
            return
        if e.dash_cd <= 0 and dist < self.width * 0.7:
            e.dash_t = 0.5
            e.dash_dir = e.facing
            e.dash_cd = 99.0
            return
        if e.spread_cd <= 0 and len(self.bullets) + 3 <= MAX_BULLETS:
            self._boss_spread(e)
            e.spread_cd = self.rng.uniform(2.0, 3.5) / max(0.5, e.fire_rate)
        if e.pattern in ("final", "chairman") and e.summon_cd <= 0:
            e.summon_cd = 8.0
            grunts = self.stage.get("grunts") or ["manager"]
            for side in (0, 1):
                if len(self.enemies) < MAX_ENEMIES:
                    self.pending.append((self.rng.choice(grunts), side, "side"))
        if e.pattern == "chairman" and e.stamp_cd <= 0 and len(self.bullets) < MAX_BULLETS:
            e.stamp_cd = 2.5
            self.bullets.append(Bullet(p.x, -20.0, 20, 20, 0.0, STAMP_SPEED, "enemy", stamp=True))
            e.shoot_t = 0.3

    def _brawler_reach(self, e: Enemy) -> float:
        return e.w * 0.6 + 30.0

    def _brawler_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        """KOF final bosses (mai/choi/chang): walk in, chase, melee in reach, aimed shot at range, occasional jump."""
        p = self.player
        if e.intro:
            e.vx = -e.speed
            if e.x <= self.width - 140:
                e.intro = False
                e.vx = 0.0
            return
        e.attack_cd -= dt
        e.ranged_cd -= dt
        e.jump_cd -= dt
        e.hurt_cd -= dt
        if e.hurt_t > 0:                            # staggered: no movement, no attacks
            e.hurt_t -= dt
            if e.on_ground:
                e.vx = 0.0
            e.dash_t = 0.0
            return
        if e.dash_t > 0:                            # v1.9: brawler dash (the 5-in-6 alternative to jumping)
            e.dash_t -= dt
            e.vx = e.dash_dir * DASH_SPEED * 0.8
            if e.dash_t <= 0:
                e.vx = 0.0
                if dist <= self._brawler_reach(e) + 20 and e.attack_cd <= 0:
                    e.attack_t = BRAWLER_ATTACK_T
                    e.hit_done = False
                    e.set_anim("attack")
            return
        if e.attack_t > 0:
            e.attack_t -= dt
            if e.on_ground:
                e.vx = 0.0
            elapsed = BRAWLER_ATTACK_T - e.attack_t
            if not e.hit_done and elapsed >= BRAWLER_HIT_WINDOW[0]:
                if e.anim == "attack2":
                    self._brawler_shot(e)
                    e.hit_done = True
                elif elapsed <= BRAWLER_HIT_WINDOW[1] and not p.dead and p.inv_t <= 0:
                    reach = self._brawler_reach(e)
                    x0, x1 = sorted((e.x - e.w * 0.3 * e.facing, e.x + e.facing * (reach + 8)))
                    if _overlap((x0, e.y - e.h * 0.9, x1, e.y + 2), self._player_box()):
                        self._hit_player()
                        e.hit_done = True
            if e.attack_t <= 0:
                e.attack_t = 0.0
                e.attack_cd = self.rng.uniform(1.0, 1.6)
            return
        if not e.on_ground:
            if e.hop_vx:
                e.vx = e.hop_vx
            return
        if p.dead:
            e.vx = 0.0
            return
        reach = self._brawler_reach(e)
        if dist <= reach:
            e.vx = 0.0
            if e.attack_cd <= 0:
                e.attack_t = BRAWLER_ATTACK_T
                e.hit_done = False
                e.set_anim("attack")
            return
        if e.ranged_cd <= 0 and self._in_band(e) and dist < self.width * 0.8 and len(self.bullets) < MAX_BULLETS:
            e.vx = 0.0
            e.attack_t = BRAWLER_ATTACK_T
            e.hit_done = False
            e.set_anim("attack2")
            e.ranged_cd = self.rng.uniform(2.0, 3.5) / max(0.5, e.fire_rate)
            return
        if e.jump_cd <= 0 and dist > BRAWLER_JUMP_DIST and self._in_band(e):
            e.jump_cd = self.rng.uniform(3.0, 5.0)
            if self.rng.random() < BOSS_JUMP_ODDS:          # jump 1 : dash 5
                e.vy = -JUMP_VEL * 0.9
                e.on_ground = False
                e.hop_vx = e.facing * max(e.speed, 160.0)
                e.vx = e.hop_vx
            else:
                e.dash_t = BRAWLER_DASH_T
                e.dash_dir = e.facing
            return
        e.vx = e.facing * e.speed
        self._maybe_hop(e)

    def _brawler_shot(self, e: Enemy):
        """attack2: one aimed projectile. Ranks with "proj" fire a sprite bullet (kind "proj", palette anim
        "proj", size / speed factor from the rank); otherwise a plain shot at 1.2x enemy bullet speed."""
        if len(self.bullets) >= MAX_BULLETS:
            return
        p = self.player
        gx, gy = e.x + e.facing * (e.w / 2), e.y - e.h * 0.6
        ang = math.atan2((p.y - PLAYER_H / 2) - gy, p.x - gx)
        proj = self._rank(e.rank).get("proj")
        pm = self.stage["mult"].get("proj", 1.0) if self.stage else 1.0
        if isinstance(proj, dict):
            spd = ENEMY_BULLET_SPEED * float(proj.get("speed", 1.2)) * pm
            self.bullets.append(Bullet(gx, gy, float(proj.get("w", 8)), float(proj.get("h", 4)),
                                       math.cos(ang) * spd, math.sin(ang) * spd, "enemy", kind="proj",
                                       sprite=e.palette, anim="proj"))
            return
        spd = ENEMY_BULLET_SPEED * 1.2 * pm
        self.bullets.append(Bullet(gx, gy, 8, 4, math.cos(ang) * spd, math.sin(ang) * spd, "enemy"))

    def _enemy_shoot(self, e: Enemy):
        if len(self.bullets) >= MAX_BULLETS:
            return
        gun_y = e.y - e.h * 0.6
        self.bullets.append(Bullet(e.x + e.facing * (e.w / 2 + 4), gun_y, 8, 4,
                                   e.facing * ENEMY_BULLET_SPEED, 0.0, "enemy"))
        e.shoot_t = 0.3

    def _boss_spread(self, e: Enemy):
        p = self.player
        gx, gy = e.x + e.facing * (e.w / 2), e.y - e.h * 0.6
        tx, ty = p.x, p.y - PLAYER_H / 2
        ang = math.atan2(ty - gy, tx - gx)
        spd = ENEMY_BULLET_SPEED * 1.1 * (self.stage["mult"].get("proj", 1.0) if self.stage else 1.0)
        for off in (-0.26, 0.0, 0.26):
            a = ang + off
            self.bullets.append(Bullet(gx, gy, 8, 4, math.cos(a) * spd, math.sin(a) * spd, "enemy"))
        e.shoot_t = 0.3

    def _update_bullets(self, dt: float, edt: float | None = None):
        W, H = self.width, self.height
        edt = dt if edt is None else edt
        spawn = []
        for b in self.bullets:
            bdt = edt if b.owner == "enemy" else dt
            b.px, b.py = b.x, b.y
            if b.kind == "missile":
                self._steer_missile(b, bdt)
            if b.kind == "blast":                       # expanding explosion, then gone
                b.ttl = (b.ttl if b.ttl is not None else BLAST_T) - bdt
                b.r = b.r_max * max(0.0, min(1.0, 1.0 - b.ttl / BLAST_T))
                b.w = b.h = b.r * 2
                if b.ttl <= 0:
                    b.dead = True
                continue
            if b.gravity:
                if b.fuse is not None and b.vx == 0 and b.vy == 0:      # armed on the ground
                    b.fuse -= bdt
                    if b.fuse <= 0:
                        b.dead = True
                        spawn.append(Bullet(b.x, b.y, 0, 0, 0.0, 0.0, b.owner, dmg=b.dmg, kind="blast",
                                            ttl=BLAST_T, r=b.r_max or 40.0))
                        self._effect("spark", b.x, b.y)
                    continue
                b.vy += GRAVITY * bdt
            b.x += b.vx * bdt
            b.y += b.vy * bdt
            if b.gravity and b.y >= self.ground_y - b.h / 2 and b.vy > 0:
                if b.fuse is not None:                   # bomb: sit on the floor until the fuse runs out
                    b.y = self.ground_y - b.h / 2
                    b.vx = b.vy = 0.0
                    continue
                b.dead = True                            # boulder: shatters on the floor
                self._effect("spark", b.x, self.ground_y)
                if b.r_max > 0:
                    spawn.append(Bullet(b.x, self.ground_y, 0, 0, 0.0, 0.0, b.owner, dmg=b.dmg, kind="blast",
                                        ttl=BLAST_T, r=b.r_max))
                continue
            if b.anim:
                b.anim_t += bdt
                step = 1.0 / PROJ_ANIM_FPS
                while b.anim_t >= step:
                    b.anim_t -= step
                    b.frame += 1
            if b.ttl is not None:
                b.ttl -= dt
                if b.ttl <= 0:
                    b.dead = True
            if b.x < -50 or b.x > W + 50 or b.y < -80 or b.y > H + 50:
                b.dead = True
            elif b.kind == "wave":
                b.y = self.ground_y - 6
            elif (b.stamp or b.kind == "missile") and b.y >= self.ground_y:
                b.dead = True
                self._effect("spark", b.x, self.ground_y)
        if spawn:
            self.bullets.extend(spawn)

    def _steer_missile(self, b: Bullet, dt: float):
        best, bd = None, 1e18
        for e in self.enemies:
            if not e.alive:
                continue
            d = (e.x - b.x) ** 2 + (e.y - e.h / 2 - b.y) ** 2
            if d < bd:
                best, bd = e, d
        if best is None:
            return
        want = math.atan2((best.y - best.h / 2) - b.y, best.x - b.x)
        cur = math.atan2(b.vy, b.vx)
        diff = (want - cur + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) > 2.5:
            # target is behind: always loop upward, never down into the floor
            diff = -math.copysign(abs(diff), b.vx if abs(b.vx) > 1 else 1.0)
        step = MISSILE_TURN * dt
        cur += max(-step, min(step, diff))
        spd = math.hypot(b.vx, b.vy) or MISSILE_SPEED        # keeps the int-scaled launch speed
        b.vx, b.vy = math.cos(cur) * spd, math.sin(cur) * spd

    def _collide(self):
        p = self.player
        pbox = self._player_box()
        for b in self.bullets:
            if b.dead:
                continue
            bb = b.box()
            if b.owner == "player":
                if b.kind == "blast":
                    if b.dmg <= 0:
                        continue
                    for e in self.enemies:
                        if e.alive and e.id not in b.hit and self._circle_hits(b, e.box()):
                            b.hit.add(e.id)
                            self._strike(e, b.dmg, b.mdmg, b.element)
                    continue
                sb = b.swept_box() if b.kind != "laser" else bb
                for e in self.enemies:
                    if not e.alive or e.id in b.hit:
                        continue
                    if _overlap(sb, e.box()):
                        b.hit.add(e.id)
                        self._strike(e, b.dmg, b.mdmg, b.element, b.x, b.y)
                        if not b.pierce:
                            b.dead = True
                            break
            else:
                if b.kind == "blast":
                    if not p.dead and p.inv_t <= 0 and self._circle_hits(b, pbox):
                        self._hit_player()
                    continue
                if b.fuse is not None:                   # a fused bomb only hurts when it blasts
                    continue
                if not p.dead and p.inv_t <= 0 and _overlap(bb, pbox):
                    b.dead = True
                    self._effect("spark", b.x, b.y)
                    self._hit_player()
                    continue
                for a in self.allies:
                    if a.kind == "decoy" and _overlap(bb, a.box()):
                        b.dead = True
                        a.hp -= 1
                        self._effect("spark", b.x, b.y)
                        break
        # boss dash contact; a sky drop landing on / a ground burst rising into the player also hits
        if not p.dead and p.inv_t <= 0:
            for e in self.enemies:
                if not e.alive:
                    continue
                dash = e.boss and e.dash_t > 0
                body = (not e.on_ground) and ((e.drop and e.vy > 0) or (e.spawn_kind == "ground" and e.vy < 0))
                if (dash or body) and _overlap(e.box(), pbox):
                    self._hit_player()
                    break

    @staticmethod
    def _circle_hits(b: Bullet, box) -> bool:
        cx = max(box[0], min(b.x, box[2]))
        cy = max(box[1], min(b.y, box[3]))
        return (cx - b.x) ** 2 + (cy - b.y) ** 2 <= b.r * b.r

    def _damage_enemy(self, e: Enemy, dmg: int):
        if not e.alive:
            return
        e.hp -= int(dmg)
        if e.hp <= 0:
            e.hp = 0
            self._kill_enemy(e)
        elif e.pattern == "brawler" and not e.intro and e.hurt_cd <= 0:
            e.hurt_t = BRAWLER_HURT_T           # brief stagger, rate-limited so it cannot be stun-locked
            e.hurt_cd = BRAWLER_HURT_CD
            e.attack_t = 0.0
            e.attack_cd = max(e.attack_cd, 0.4)
            if e.on_ground:
                e.vx = 0.0
                e.set_anim("hurt")

    def _kill_enemy(self, e: Enemy):
        e.death_t = 0.0
        e.vx = 0.0
        e.set_anim("death")
        self._bal_enemy(e, killed=True)
        r = self._rank(e.rank)
        if e.boss:
            pts = int(r.get("boss_score", 2000))
        elif e.kind == "elite":
            pts = int(r.get("score", 300))
        else:
            pts = int(r.get("score", 100))
        self.score += pts
        self._effect("text", e.x, e.y - e.h - 8, text=f"+{pts}")
        self._drop_item(e)
        if e.boss:
            self.pending.clear()
            for o in self.enemies:
                if o is not e and o.alive:
                    o.death_t = 0.0
                    o.set_anim("death")
            if not e.mid and self.stage.get("kind") == "dept":
                self._grant_equip()

    def _grant_equip(self) -> str:
        """A department stage's final boss fell: +1 level on the lowest-level slot (ties: EQUIP_ORDER)."""
        slot = min(EQUIP_ORDER, key=lambda k: (self.equip.get(k, 0), EQUIP_ORDER.index(k)))
        self.equip[slot] = self.equip.get(slot, 0) + 1
        label = str(self.equipment[slot].get("label", slot))
        msg = f"장비 획득 · {label} Lv{self.equip[slot]}"
        self._equip_msg = msg
        self._set_banner(msg, EQUIP_BANNER_T)
        p = self.player
        self._effect("text", p.x, p.y - PLAYER_H - 24, text=f"{label} Lv{self.equip[slot]}")
        if p.shield < self._shield_max() and slot == "hat":
            p.shield += 1                       # a new helmet level comes charged
        return slot

    def _shield_max(self) -> int:
        return max(0, int(self.char.get("shield", 0) or 0) + self.upgrades.get("shield", 0)
                   + int(round(self._equip_bonus("shield"))))

    def _hit_player(self):
        """Enemy bullet / boss contact. A shield charge absorbs the hit before a life is lost."""
        p = self.player
        if p.dead or p.inv_t > 0:
            return
        if p.shield > 0:
            p.shield -= 1
            p.inv_t = SHIELD_INV
            self._bal_add("hits_shield", 1)
            self._effect("text", p.x, p.y - PLAYER_H - 12, text=f"실드 {p.shield}")
            return
        self._bal_add("hits_life", 1)
        self._kill_player()

    def _kill_player(self, force: bool = False):
        p = self.player
        if p.dead or (p.inv_t > 0 and not force):
            return
        p.dead = True
        p.death_t = 0.0
        p.vx = p.vy = 0.0
        p.crouch = False
        p.weapon, p.weapon_t, p.ammo = "normal", 0.0, 0
        if self.anim_lens:
            p.hold_frame = max(0, int(self.anim_lens.get("death", 8)) - 1)
        p.set_anim("death")
        self._effect("spark", p.x, p.y - PLAYER_H / 2)

    def _after_death(self):
        self.lives -= 1
        self._bal_add("deaths", 1)
        if self.lives <= 0:
            self.lives = 0
            if self.score > self.best:
                self.best = self.score
            self.bullets.clear()
            self.allies.clear()
            self.words.clear()
            self._bal_flush("game_over")
            self._set_banner("GAME OVER")
            self._set_state("game_over")
            return
        # restart current wave / boss
        self.enemies.clear()
        self.bullets.clear()
        self.items.clear()
        self.effects.clear()
        self.zones.clear()
        self.warnings.clear()
        self.boss_ref = None
        self._reset_player(invincible=2.0)
        if self.phase in ("boss", "midboss"):   # restart at the (mid) boss, not the whole stage
            self.boss_gap = BOSS_GAP
            self.pending.clear()
        else:
            self._begin_wave()

    def _cleanup(self):
        if any(b.dead for b in self.bullets):
            self.bullets = [b for b in self.bullets if not b.dead]
        if any((not e.alive) and e.death_t >= 0.6 for e in self.enemies):
            self.enemies = [e for e in self.enemies if e.alive or e.death_t < 0.6]

    def _check_progress(self, dt: float):
        if self.player.dead:
            return
        if self.phase == "wave":
            if not self.pending and not self.enemies and not self.warnings:
                self.wave_gap -= dt
                if self.wave_gap <= 0:
                    self.wave_index += 1
                    if self.wave_index < self.stage["waves"]:
                        if self._mid_boss_due():
                            self.phase = "midboss"
                            self.boss_gap = BOSS_GAP
                        else:
                            self._begin_wave()
                    else:
                        self.phase = "boss"
                        self.boss_index = 0
                        self.boss_gap = BOSS_GAP
        if self.phase == "midboss":
            b = self.boss_ref
            if b is None:
                if not self.enemies:
                    self.boss_gap -= dt
                    if self.boss_gap <= 0:
                        self._spawn_mid_boss()
            elif b not in self.enemies:
                # mid boss died and its death anim finished -> remaining waves
                self.boss_ref = None
                self.mid_done = True
                self.phase = "wave"
                self._begin_wave()
        if self.phase == "boss":
            b = self.boss_ref
            if b is None:
                if not self.enemies:
                    self.boss_gap -= dt
                    if self.boss_gap <= 0:
                        self._spawn_boss()
            elif b not in self.enemies:
                # boss died and its death anim finished
                self.boss_ref = None
                self.boss_index += 1
                if self.boss_index < len(self.stage["bosses"]):
                    self.boss_gap = BOSS_NEXT_GAP
                else:
                    self._stage_clear()

    def _stage_clear(self):
        self.score += 500 * self.stage_no
        if self.score > self.best:
            self.best = self.score
        self.best_clear[self.difficulty_key] = max(self.best_clear.get(self.difficulty_key, 0), self.stage_no)
        self.allies.clear()
        self.words.clear()
        self._bal_flush("clear")
        self.bullets.clear()
        self.enemies.clear()
        self.pending.clear()
        self.warnings.clear()
        self.player.hold_frame = (max(0, int(self.anim_lens.get("victory", 6)) - 1) if self.anim_lens else None)
        self.player.set_anim("victory")
        banner = "STAGE CLEAR"
        for k in CHAR_KEYS:
            if self._char_locked(k) and self.stage_no >= self._unlock_stage(k):
                self.unlocked.add(k)
                banner = f"STAGE CLEAR · {self.chars[k]['name']} 해금!"
        if self._equip_msg:                     # keep the equipment pickup visible through the clear screen
            banner += f" · {self._equip_msg}"
        self._set_banner(banner)
        self._set_state("stage_clear")

    # ------------------------------------------------------------ balance log (v1.9)
    def _bal_start(self):
        c = self.char
        self._bal = {"stage": self.stage_no, "stage_name": self.stage.get("name", ""), "difficulty": self.difficulty_key,
                     "char": self.char_key, "t0": self.play_t, "lives0": self.lives, "money0": self.money,
                     "score0": self.score,
                     "player": {"phys": self._phys_dmg(c), "magic": self._magic_dmg(c),
                                "fire_rate": round(FIRE_RATE * self._fire_rate_mult(c), 2),
                                "speed": round(self._speed_mult(c), 3), "shield_max": self._shield_max(),
                                "stats": self._eff_stats(c), "equip": self._equip_fx()},
                     "enemy_hp": {}, "ttk": {}, "spawned": 0, "killed": 0, "shots": 0, "hits_shield": 0,
                     "hits_life": 0, "deaths": 0, "money": 0, "spent": 0, "items_used": 0, "words": 0,
                     "typed": 0, "gear": 0, "melee_dmg": 0, "gambles": 0}

    def _bal_add(self, key: str, v: float = 1):
        if self._bal:
            self._bal[key] = self._bal.get(key, 0) + v

    def _bal_enemy(self, e: Enemy, killed: bool):
        b = self._bal
        if not b:
            return
        k = "boss" if e.boss else e.kind
        if not killed:
            b["spawned"] += 1
            b["enemy_hp"].setdefault(k, []).append(e.hp_max)
            return
        b["killed"] += 1
        b["ttk"].setdefault(k, []).append(round(self.play_t - e.born, 2))

    def _bal_flush(self, reason: str):
        b = self._bal
        if not b:
            return
        rec = {"reason": reason, "stage": b["stage"], "stage_name": b["stage_name"], "difficulty": b["difficulty"],
               "char": b["char"], "duration": round(self.play_t - b["t0"], 1), "player": b["player"],
               "enemy_hp_avg": {k: round(sum(v) / len(v), 1) for k, v in b["enemy_hp"].items() if v},
               "ttk_avg": {k: round(sum(v) / len(v), 2) for k, v in b["ttk"].items() if v},
               "ttk_max": {k: max(v) for k, v in b["ttk"].items() if v},
               "spawned": b["spawned"], "killed": b["killed"], "shots": b["shots"],
               "hits_shield": b["hits_shield"], "hits_life": b["hits_life"], "deaths": b["deaths"],
               "lives_end": self.lives, "money_gained": b["money"], "money_spent": b["spent"],
               "money_end": self.money, "score_gained": self.score - b["score0"], "items_used": b["items_used"],
               "words_done": b["words"], "letters_typed": b["typed"], "gear_drops": b["gear"],
               "melee_dmg": b["melee_dmg"], "gambles": b["gambles"]}
        self.balance_log.append(rec)
        if len(self.balance_log) > BALANCE_LOG_MAX:
            del self.balance_log[0:len(self.balance_log) - BALANCE_LOG_MAX]
        self._bal = {}

    # ------------------------------------------------------------ effects
    def _effect(self, kind: str, x: float, y: float, text: str | None = None):
        ttl = {"hit": 0.15, "spark": 0.25, "text": 0.8, "elem": 0.5, "dust": 0.35}.get(kind, 0.2)
        self.effects.append({"kind": kind, "x": float(x), "y": float(y), "t": ttl, "ttl": ttl, "text": text})
        if len(self.effects) > MAX_EFFECTS:
            del self.effects[0:len(self.effects) - MAX_EFFECTS]

    def _update_effects(self, dt: float):
        alive = []
        for f in self.effects:
            f["t"] -= dt
            if f["kind"] in ("text", "elem"):
                f["y"] -= 40 * dt
            if f["t"] > 0:
                alive.append(f)
        self.effects = alive


# ---------------------------------------------------------------- selftest
SNAP_KEYS = {"state", "ground_y", "platforms", "pits", "player", "enemies", "bullets", "items", "zones", "effects",
             "hud", "warnings", "allies", "words"}
ALLY_KEYS = {"kind", "x", "y", "anim", "frame", "flip", "palette", "t", "ttl"}
WORD_KEYS = {"text", "typed", "x", "y", "kind", "t", "vy"}
WARNING_KEYS = {"kind", "x", "t", "ttl"}
WARNING_KINDS = ("ground", "sky")
ZONE_KEYS = {"kind", "x", "w", "h", "t", "ttl"}
ZONE_KINDS = ("storm", "quake")
PLAYER_KEYS = {"x", "y", "anim", "frame", "flip", "palette", "scale", "invincible", "visible", "element"}
ENEMY_KEYS = {"id", "x", "y", "anim", "frame", "flip", "palette", "scale", "label", "hp", "hp_max", "boss",
              "element", "mid", "sprint", "drop", "attack", "slow"}
BULLET_KEYS = {"x", "y", "w", "h", "owner", "kind", "sprite", "anim", "frame", "flip", "gravity", "r"}
BULLET_KINDS = ("normal", "laser", "missile", "proj", "bomb", "blast", "wave")
ITEM_KEYS = {"x", "y", "kind", "t", "value"}
EFFECT_KEYS = {"kind", "x", "y", "t", "text"}
EFFECT_KINDS = ("hit", "spark", "text", "elem", "dust", "slash", "word", "coin", "boxopen")
HUD_KEYS = {"lives", "score", "best", "stage_no", "stage_name", "difficulty", "boss_hp", "boss_hp_max",
            "banner", "banner_t", "char_name", "select_index", "char_names", "continue_stage", "show_enemy_hp",
            "weapon", "weapon_label", "weapon_left", "shield", "shield_max", "melee_t", "skill_label", "skill_cd", "ult",
            "char_locked", "shop", "element", "element_name", "element_names", "element_index", "stats",
            "char_stats", "element_colors", "equip", "equip_labels",
            "money", "difficulty_label", "difficulty_index", "difficulty_locked", "inventory", "inv_flash",
            "melee_style", "melee_hit", "slow_t", "equip_effect", "equipped", "town"}
BRAWLER_ANIMS = {"idle", "run", "attack", "attack2", "hurt", "death", "jump"}
ALL_KEYS = {"left", "right", "up", "down", "jump", "fire", "pause", "quit", "confirm", "sel_left", "sel_right",
            "skill", "slot1", "slot2", "slot3", "slot4", "slot5", "tab", "char:a", "char:s", "char:d", "char:o"}


def _check_snapshot(s: dict):
    assert set(s.keys()) == SNAP_KEYS, set(s.keys()) ^ SNAP_KEYS
    assert set(s["player"].keys()) == PLAYER_KEYS, set(s["player"].keys()) ^ PLAYER_KEYS
    assert set(s["hud"].keys()) == HUD_KEYS, set(s["hud"].keys()) ^ HUD_KEYS
    for e in s["enemies"]:
        assert set(e.keys()) == ENEMY_KEYS, set(e.keys()) ^ ENEMY_KEYS
        assert e["scale"] in (1, 2, 4, 6)          # v1.9: sheet monsters draw at 1x
        assert e["element"] is None or e["element"] in ELEMENT_KEYS
        if e["mid"]:
            assert e["boss"]
    assert s["player"]["element"] in ELEMENT_KEYS
    h = s["hud"]
    assert h["element"] == ELEMENT_KEYS[h["element_index"]] and len(h["element_names"]) == len(ELEMENT_KEYS)
    assert set(h["element_colors"]) == set(ELEMENT_KEYS) and len(h["char_stats"]) == len(CHAR_KEYS)
    assert set(h["equip"]) == set(EQUIP_ORDER) == set(h["equip_labels"])
    assert all(isinstance(v, int) and v >= 0 for v in h["equip"].values())
    if h["shop"] is not None:
        assert set(h["shop"]) == {"index", "items", "msg", "stats"}
        for row in h["shop"]["items"]:
            assert row["max"] >= 0 and (row["max"] == 0 or row["level"] <= row["max"])
    for b in s["bullets"]:
        assert set(b.keys()) == BULLET_KEYS and b["owner"] in ("player", "enemy")
        assert b["kind"] in BULLET_KINDS
        assert (b["sprite"] is None) == (b["anim"] is None) and isinstance(b["frame"], int)
        assert isinstance(b["flip"], bool)
        if b["kind"] == "proj":
            assert b["sprite"] and b["anim"] in ("proj", "proj2")
    for it in s["items"]:
        assert set(it.keys()) == ITEM_KEYS and it["kind"] in ITEM_KINDS
    assert len(s["items"]) <= MAX_ITEMS
    for z in s["zones"]:
        assert set(z.keys()) == ZONE_KEYS and z["kind"] in ZONE_KINDS
    assert len(s["hud"]["char_locked"]) == len(CHAR_KEYS)
    assert (s["hud"]["shop"] is not None) == (s["state"] == "shop")
    assert (s["hud"]["town"] is not None) == (s["state"] == "town")
    for a in s["allies"]:
        assert set(a.keys()) == ALLY_KEYS and a["kind"] in ("decoy", "drone", "dog")
    for w in s["words"]:
        assert set(w.keys()) == WORD_KEYS and w["kind"] in WORD_KINDS and 0 <= w["typed"] <= len(w["text"])
    assert len(s["hud"]["inventory"]) == INV_SLOTS
    for it in s["hud"]["inventory"]:
        assert it is None or (it["kind"] in ITEM_KINDS and 1 <= it["count"] <= INV_STACK)
    for f in s["effects"]:
        assert set(f.keys()) == EFFECT_KEYS and f["kind"] in EFFECT_KINDS
    for w in s["warnings"]:
        assert set(w.keys()) == WARNING_KEYS and w["kind"] in WARNING_KINDS
        assert 0 <= w["t"] <= w["ttl"] and w["x"] > 0
    assert s["hud"]["difficulty"] in DIFFICULTIES
    assert s["state"] in World.STATES
    assert s["player"]["scale"] == 2
    assert len(s["enemies"]) <= MAX_ENEMIES and len(s["bullets"]) <= MAX_BULLETS and len(s["effects"]) <= MAX_EFFECTS


def _run(w: "World", secs: float, dt: float = 1 / 30) -> None:
    for _ in range(int(round(secs / dt))):
        w.update(dt)


def selftest() -> int:
    import time
    t0 = time.perf_counter()
    base = os.path.dirname(os.path.abspath(__file__))
    stages = load_json(os.path.join(base, "stages.json"))
    config = load_json(os.path.join(base, "config.json"))
    assert stages and config, "stages.json / config.json must load"
    assert len(stages["departments"]) == 10 and len(stages["executive_stages"]) == 4
    for k in ("intern", "staff", "assistant", "manager", "deputy", "general", "teamlead", "director", "md", "evp",
              "ceo", "chairman", "lab1", "lab2", "lab3", "lab4", "lab5"):
        assert k in stages["ranks"], k
    DT = 1 / 30

    # (1) select -> play
    w = World(stages, config, {}, 1600, 360, seed=1)
    assert w.state == "select"
    w.key_down("sel_right"); w.key_up("sel_right")
    assert w.snapshot()["hud"]["select_index"] == 1
    _run(w, 0.3)
    w.key_down("confirm"); w.key_up("confirm")
    assert w.state == "play" and w.stage_no == 1, (w.state, w.stage_no)
    assert w.snapshot()["hud"]["stage_name"] == "1스테이지: 총무팀"
    sel = CHAR_KEYS[w.snapshot()["hud"]["select_index"]]
    assert w.snapshot()["hud"]["show_enemy_hp"] is bool(w.chars[sel].get("show_enemy_hp", False))
    print("PASS 1: select -> play via confirm")

    # stage table sanity: build stages 1..45 without error
    for n in range(1, 46):
        st = w._build_stage(n)
        assert st["bosses"] and st["difficulty"] in DIFFICULTIES
    assert w._build_stage(11)["name"] == "실장단" and len(w._build_stage(11)["bosses"]) == 3
    assert w._build_stage(14)["bosses"] == ["chairman"]
    assert w._build_stage(15)["difficulty"] == "normal" and w._build_stage(25)["infinite"] is True
    assert w._build_stage(25)["mult"]["hp"] > w._build_stage(15)["mult"]["hp"] and w._build_stage(10)["lab"] is True

    # (2) clear all waves + boss -> stage 2, player reset
    start_x = w.player.x
    w.player.x = 900.0          # move away from start to prove the reset
    saw_boss = False
    ticks = 0
    while w.stage_no == 1 and ticks < 6000:
        w.update(DT)
        ticks += 1
        snap = w.snapshot()
        if snap["hud"]["boss_hp"] is not None:
            saw_boss = True
        if w.state == "play" and w.enemies:
            w._debug_kill_all()
        if w.state == "stage_clear":
            assert snap["hud"]["banner"].startswith("STAGE CLEAR"), snap["hud"]["banner"]
        if w.state == "shop":                   # leave the shop without buying
            w.shop_index = len(SHOP_ORDER) - 1
            w.state_t = 1.0
            w.key_down("confirm"); w.key_up("confirm")
    assert saw_boss, "boss never appeared"
    assert w.state == "play" and w.stage_no == 2, (w.state, w.stage_no, ticks)
    assert abs(w.player.x - start_x) < 1 and not w.enemies and not w.bullets
    assert w.score >= 500 + 2000, w.score
    print(f"PASS 2: waves+boss cleared -> stage {w.stage_no}, player reset ({ticks} ticks, score {w.score})")

    # (4) save round-trip (do before deaths so stage 2 is what we continue at)
    sd = w.save_data()
    sd2 = json.loads(json.dumps(sd))
    assert sd2["stage"] == 2 and sd2["char"] == "hyunki" and "best" in sd2
    w2 = World(stages, config, sd2, 1600, 360, seed=5)
    assert w2.snapshot()["hud"]["select_index"] == 1 and w2.snapshot()["hud"]["continue_stage"] == 2
    _run(w2, 0.3)
    w2.key_down("confirm"); w2.key_up("confirm")
    assert w2.state == "continue", w2.state
    assert "이어하기 (2스테이지)" in w2.snapshot()["hud"]["banner"]
    w2.key_down("right"); w2.key_up("right")
    assert w2.snapshot()["hud"]["banner"].endswith("▶ 처음부터")
    w2.key_down("left"); w2.key_up("left")
    _run(w2, 0.3)
    w2.key_down("fire"); w2.key_up("fire")
    assert w2.state == "play" and w2.stage_no == 2, (w2.state, w2.stage_no)
    w3 = World(stages, config, sd2, 1600, 360, seed=5)
    _run(w3, 0.3); w3.key_down("confirm"); w3.key_down("right"); _run(w3, 0.3); w3.key_down("confirm")
    assert w3.state == "play" and w3.stage_no == 1
    print("PASS 4: save_data round-trip -> continue offered (stage 2) / new game")

    # (3) deaths -> lives, game over
    lives0 = w.lives
    assert lives0 == 3
    for i in range(3):
        w._debug_kill_player()
        assert w.player.dead
        for _ in range(int(1.2 / DT)):
            w.update(DT)
        if i < 2:
            assert w.lives == lives0 - i - 1 and w.state == "play" and not w.player.dead, (w.lives, w.state)
            assert w.player.inv_t > 0
    assert w.state == "game_over" and w.lives == 0, (w.state, w.lives)
    assert w.snapshot()["hud"]["banner"] == "GAME OVER"
    assert w.snapshot()["hud"]["best"] >= w.score
    w.key_down("confirm"); w.key_up("confirm")
    assert w.state == "game_over"                       # too early
    for _ in range(int(3.1 / DT)):
        w.update(DT)
    w.key_down("fire"); w.key_up("fire")
    assert w.state == "select", w.state
    assert w.save_data()["stage"] == 2
    print("PASS 3: 3 deaths -> lives 3->0 -> game_over -> select")

    # pause
    _run(w, 0.3); w.key_down("confirm"); w.key_up("confirm")
    assert w.state in ("play", "continue")
    if w.state == "continue":
        _run(w, 0.3); w.key_down("confirm"); w.key_up("confirm")
    assert w.state == "play"
    w.key_down("pause"); w.key_up("pause"); assert w.state == "paused"
    w.set_paused(False); assert w.state == "play"
    w.set_paused(True); assert w.state == "paused"
    w.key_down("pause"); w.key_up("pause"); assert w.state == "play"

    # (5) fuzz: random keys, snapshot key sets exact; also across stages/exec stages
    rng = random.Random(7)
    worlds = [World(stages, config, {}, 1280, 300, seed=11), World(stages, config, {"stage": 11}, 1920, 400, seed=12),
              World(stages, config, {"stage": 14}, 800, 240, seed=13), World(stages, config, {"stage": 27}, 1600, 360, seed=14)]
    for wi, fw in enumerate(worlds):
        _run(fw, 0.3); fw.key_down("confirm"); fw.key_up("confirm")
        if fw.state == "continue":
            _run(fw, 0.3); fw.key_down("confirm"); fw.key_up("confirm")
        assert fw.state == "play"
        fw.keys.add("fire")
        for t in range(200 if wi else 400):
            k = rng.choice(sorted(ALL_KEYS))
            if rng.random() < 0.5:
                fw.key_down(k)
            else:
                fw.key_up(k)
            if fw.state == "paused":
                fw.set_paused(False)
            fw.update(rng.choice((DT, 0.02, 0.1)))
            if t % 37 == 0:
                fw.resize(fw.width + rng.randint(-100, 100), fw.height + rng.randint(-20, 20))
            if t % 50 == 25 and fw.state == "play":
                fw._debug_kill_all()
            s = fw.snapshot()
            _check_snapshot(s)
            json.dumps(s)   # serialisable
    # long soak on a boss stage with bosses actually fighting
    fw = World(stages, config, {"stage": 12}, 1600, 360, seed=3)
    _run(fw, 0.3); fw.key_down("confirm"); _run(fw, 0.3); fw.key_down("confirm")
    assert fw.state == "play" and fw.stage_no == 12
    fw.keys.add("fire")
    saw_boss = saw_enemy_bullet = False
    for t in range(900):
        fw.update(DT)
        if t % 60 == 0:
            fw.keys.symmetric_difference_update({"left", "right", "down"})
        s = fw.snapshot()
        _check_snapshot(s)
        saw_boss = saw_boss or s["hud"]["boss_hp"] is not None
        saw_enemy_bullet = saw_enemy_bullet or any(b["owner"] == "enemy" for b in s["bullets"])
    assert saw_boss and saw_enemy_bullet, (saw_boss, saw_enemy_bullet)
    print("PASS 5: 1400+ random-key ticks, no exceptions, snapshot keys exact")

    # 6) hit detection (bullet must actually reach a grunt), HP progression, items and weapons
    def _arena(seed, stage=1):
        aw = World(stages, config, {}, 1920, 340, seed=seed)
        aw._start_game(stage)
        aw.pending.clear()                      # v1.8: faster enemies would reach the player within 1.3 s
        _run(aw, 1.3)
        aw.enemies.clear()
        aw.pending.clear()
        aw.bullets.clear()
        aw.player.x = 600.0
        return aw

    hp_seen = []
    for stage in (1, 3, 6):
        aw = _arena(11, stage)
        en = aw._make_enemy("intern", aw.player.x + 300)
        en.fire_rate = 0.0                      # the target must not shoot back (hp-by-stage check only)
        aw.enemies.append(en)
        hp_seen.append(en.hp_max)
        aw.key_down("fire")
        for _ in range(150):
            aw.update(1 / 30)
            if not en.alive:
                break
        assert not en.alive, f"stage {stage}: bullets never hit the grunt"
    assert hp_seen[0] < hp_seen[1] < hp_seen[2], hp_seen
    aw = _arena(12)
    aw.items.append(Item(aw.player.x, aw.player.y - 5, "laser"))
    _run(aw, 0.1)
    assert aw.inventory[0] == {"kind": "laser", "count": 1}, aw.inventory      # v1.9: stored, not applied
    aw._use_slot(0)
    assert aw.inventory[0] is None
    assert aw.player.weapon == "laser" and aw.snapshot()["hud"]["weapon"] == "laser"
    row = [aw._make_enemy("staff", aw.player.x + d) for d in (200, 400, 600)]
    aw.enemies.extend(row)
    aw.key_down("fire")
    _run(aw, 0.7)
    assert all(not e.alive for e in row), "laser must pierce the whole row"
    aw = _arena(13)
    aw.items.append(Item(aw.player.x, aw.player.y - 5, "homing"))
    _run(aw, 0.1)
    aw._use_slot(0)
    behind = aw._make_enemy("staff", aw.player.x - 300)
    behind.speed = 0.0
    aw.enemies.append(behind)
    aw.key_down("fire")
    for _ in range(90):
        aw.update(1 / 30)
        if not behind.alive:
            break
    assert not behind.alive, "missile must home onto an enemy behind the player"
    aw = _arena(14)
    lives0 = aw.lives
    aw.items.append(Item(aw.player.x, aw.player.y - 5, "life"))
    _run(aw, 0.1)
    aw._use_slot(0)
    assert aw.lives == lives0 + 1
    aw._kill_player(force=True)
    assert aw.player.weapon == "normal"
    print(f"PASS 6: hits land, grunt hp by stage {hp_seen}, laser/homing/1UP items work")

    # 7) shield: hyunki absorbs 3 enemy bullets, the 4th costs a life; refilled on respawn
    sw = World(stages, config, {"char": "hyunki"}, 1920, 340, seed=21)
    assert sw.char_key == "hyunki" and sw._shield_max() == 3
    sw._start_game(1)
    sw.enemies.clear(); sw.pending.clear(); sw.bullets.clear()
    lives0 = sw.lives
    assert sw.player.shield == 3 and sw.snapshot()["hud"]["shield"] == 3

    def _shoot_player(world):
        p = world.player
        p.inv_t = 0.0
        world.bullets.append(Bullet(p.x, p.y - PLAYER_H / 2, 6, 6, 0.0, 0.0, "enemy"))
        world.update(1 / 30)

    for left in (2, 1, 0):
        _shoot_player(sw)
        assert sw.player.shield == left and not sw.player.dead and sw.lives == lives0, (sw.player.shield, sw.lives)
    _shoot_player(sw)
    assert sw.player.dead
    _run(sw, 1.2)
    assert sw.lives == lives0 - 1 and sw.player.shield == 3, (sw.lives, sw.player.shield)
    jw = World(stages, config, {"char": "jaehwi"}, 1920, 340, seed=22)
    jw._start_game(1)
    jw.enemies.clear(); jw.pending.clear(); jw.bullets.clear()
    assert jw.player.shield == 0 and jw.snapshot()["hud"]["shield_max"] == 0
    _shoot_player(jw)
    assert jw.player.dead, "characters without a shield die on the first hit"
    print("PASS 7: hyunki shield absorbs 3 hits, 4th costs a life, refilled on respawn")

    def _dummy(world, rank, x, hp=20):
        e = world._make_enemy(rank, x)
        e.hp = e.hp_max = hp
        e.speed = 0.0
        e.fire_rate = 0.0
        e.fire_cd = e.jump_cd = 99.0
        world.enemies.append(e)
        return e

    def _quiet(char, seed):
        qw = World(stages, config, {"char": char, "unlocked": ["masked"]}, 1920, 340, seed=seed)
        assert qw.char_key == char
        qw._start_game(1)
        _run(qw, 1.3)
        qw.enemies.clear(); qw.pending.clear(); qw.bullets.clear()
        qw.player.x, qw.player.facing = 600.0, 1
        return qw

    # 8) melee: hyunki strikes an adjacent enemy instead of shooting; masked hits behind and never shoots
    mw = _quiet("hyunki", 31)
    near = _dummy(mw, "teamlead", mw.player.x + 30)
    near.element = None                          # neutral target: melee = config damage + magic (int//3)
    mw.key_down("fire"); mw.update(DT); mw.key_up("fire")
    melee_dmg = int(config["characters"]["hyunki"]["melee"]["damage"])      # v1.9: hammer = physical only
    assert near.hp == 20 - melee_dmg, near.hp
    assert not any(b.owner == "player" and b.kind != "wave" for b in mw.bullets), "melee must replace the shot"
    assert near.x > mw.player.x + 30, "melee must shove the enemy"
    mw.enemies.clear()
    _run(mw, 0.5)
    mw.key_down("fire"); mw.update(DT); mw.key_up("fire")
    assert any(b.owner == "player" for b in mw.bullets), "no enemy in reach -> normal shot"
    kw = _quiet("masked", 32)
    behind = _dummy(kw, "teamlead", kw.player.x - 40)
    kw.key_down("fire"); kw.update(DT)
    assert behind.hp < 20 and not kw.bullets, (behind.hp, len(kw.bullets))
    kw.enemies.clear()
    _run(kw, 0.6)
    assert not any(b.owner == "player" for b in kw.bullets), "melee-only character never shoots"
    print("PASS 8: melee strikes in reach (hyunki front, masked both sides), shots otherwise")

    # 9) paper storm: dongil zone damages enemies inside, clears enemy bullets, has a cooldown
    dw = _quiet("dongil", 33)
    target = _dummy(dw, "teamlead", 700.0)
    dw.key_down("skill"); dw.key_up("skill")
    assert len(dw.zones) == 1 and dw.player.skill_cd > 0
    dw.key_down("skill"); dw.key_up("skill")
    assert len(dw.zones) == 1, "skill is on cooldown"
    dw.bullets.append(Bullet(700.0, dw.ground_y - 30, 8, 4, -ENEMY_BULLET_SPEED, 0.0, "enemy"))
    _run(dw, 1.0)
    assert target.hp <= 20 - 2, target.hp
    assert not any(b.owner == "enemy" for b in dw.bullets), "storm must eat enemy bullets"
    _check_snapshot(dw.snapshot())
    _run(dw, 2.5)
    assert not dw.zones
    jw2 = _quiet("jaehwi", 34)
    jw2.key_down("skill"); jw2.key_up("skill")
    assert not jw2.zones and jw2.snapshot()["hud"]["skill_label"] is None
    assert dw.snapshot()["hud"]["ult"] is None
    dw.key_down("skill"); dw.key_up("skill")               # cooldown still running -> no burst
    assert dw.snapshot()["hud"]["ult"] is None
    dw.player.skill_cd = 0.0
    dw.key_down("skill"); dw.key_up("skill")
    ult = dw.snapshot()["hud"]["ult"]
    assert ult and 0 < ult["t"] <= ult["ttl"] == ULT_T, ult
    _run(dw, ULT_T + 0.1)
    assert dw.snapshot()["hud"]["ult"] is None, "portrait burst ends after ULT_T"
    # v2.0 hyunki: quake zone centred on the player hits both sides and shoves
    hw2 = _quiet("hyunki", 35)
    left = _dummy(hw2, "teamlead", hw2.player.x - 90)
    right = _dummy(hw2, "teamlead", hw2.player.x + 90)
    lx, rx = left.x, right.x
    hw2.key_down("skill"); hw2.key_up("skill")
    assert len(hw2.zones) == 1 and hw2.zones[0]["kind"] == "quake" and hw2.player.ult_t > 0
    _check_snapshot(hw2.snapshot())
    _run(hw2, 0.5)
    assert left.hp < 20 and right.hp < 20 and left.x < lx and right.x > rx, (left.hp, right.hp)
    print("PASS 9: paper storm hits enemies inside, clears enemy bullets, cooldown holds; ult burst + quake")

    # 10) shop after stage clear: buy with score, next stage, upgrades survive 'continue'
    hw = World(stages, config, {"char": "jaehwi"}, 1920, 340, seed=35)
    hw._start_game(1)
    hw._stage_clear()
    _run(hw, 2.1)
    assert hw.state == "shop", hw.state
    assert SHOP_ORDER[0] == "str" and "damage" not in hw.shop_items
    cost = hw._shop_cost("str")
    assert cost == 1500, cost
    hw.score = cost
    hw.state_t = 1.0
    hw.key_down("confirm"); hw.key_up("confirm")
    assert hw.upgrades["str"] == 1 and hw.score == 0, (hw.upgrades, hw.score)
    assert hw.snapshot()["hud"]["stats"]["str"] == 5 and hw.snapshot()["hud"]["shop"]["stats"]["str"] == 5
    hw.key_down("confirm"); hw.key_up("confirm")
    assert hw.upgrades["str"] == 1 and "부족" in hw.snapshot()["hud"]["shop"]["msg"]
    _check_snapshot(hw.snapshot())
    hw.key_down("left"); hw.key_up("left")      # wraps to "next"
    hw.key_down("confirm"); hw.key_up("confirm")
    assert hw.state == "play" and hw.stage_no == 2, (hw.state, hw.stage_no)
    sd = json.loads(json.dumps(hw.save_data()))
    assert sd["upgrades"]["str"] == 1 and sd["stage"] == 2
    cw = World(stages, config, sd, 1920, 340, seed=36)
    _run(cw, 0.3); cw.key_down("confirm"); cw.key_up("confirm")
    assert cw.state == "continue"
    _run(cw, 0.3); cw.key_down("confirm"); cw.key_up("confirm")
    assert cw.state == "play" and cw.upgrades["str"] == 1 and cw._eff_stats(cw.char)["str"] == 5
    cw.upgrades["str"] = 2                        # jaehwi str 4 -> 6 -> phys 2
    cw.bullets.clear()
    cw.key_down("fire"); cw.update(DT)
    assert any(b.owner == "player" and b.dmg == 2 for b in cw.bullets), "str upgrade applies to shots"
    print(f"PASS 10: shop buys with score (str cost {cost}), next stage, upgrades kept on continue")

    # 11) hidden character: locked until the unlock stage is cleared, then selectable
    uw = World(stages, config, {}, 1920, 340, seed=37)
    idx = CHAR_KEYS.index("masked")
    assert uw._char_locked("masked") and uw.snapshot()["hud"]["char_locked"][idx]
    while uw.select_index != idx:
        uw.key_down("right"); uw.key_up("right")
    assert "???" in uw.snapshot()["hud"]["banner"]
    _run(uw, 0.3)
    uw.key_down("confirm"); uw.key_up("confirm")
    assert uw.state == "select", "locked character must not start"
    uw.select_index = 0
    unlock_at = uw._unlock_stage("masked")
    uw._start_game(unlock_at)
    uw._stage_clear()
    assert not uw._char_locked("masked") and "해금" in uw.snapshot()["hud"]["banner"]
    assert "masked" in uw.save_data()["unlocked"]
    print(f"PASS 11: hidden character locked until stage {unlock_at} clear, then unlocked and saved")

    # 12) elements: multiplier table, magic damage added to shots, "elem" effect on strong/weak hits
    ew = _quiet("jaehwi", 41)                    # jaehwi stats 8/4/4 -> phys 1, magic 1
    assert ew._elem_mult("cheongryong", "hyeonmu") == 1.5 and ew._elem_mult("hyeonmu", "cheongryong") == 0.5
    assert ew._elem_mult("cheongryong", "jujak") == 1.0 and ew._elem_mult("cheongryong", None) == 1.0
    assert ew._elem_mult(None, "jujak") == 1.0 and ew._elem_mult("baekho", "cheongryong") == 1.5
    for a, b in (("cheongryong", "hyeonmu"), ("hyeonmu", "jujak"), ("jujak", "baekho"), ("baekho", "cheongryong")):
        assert ew._elem_mult(a, b) == 1.5 and ew._elem_mult(b, a) == 0.5, (a, b)
    ew.element_index = ELEMENT_KEYS.index("cheongryong")
    phys, magic = ew._phys_dmg(ew.char), ew._magic_dmg(ew.char)
    assert phys == 1 and magic == 1, (phys, magic)
    seen = {}
    for tgt, want, fx in (("hyeonmu", phys + 2, "강!"), ("baekho", phys + 0, "약"), ("jujak", phys + 1, None)):
        ew.enemies.clear(); ew.bullets.clear(); ew.effects.clear()
        d = _dummy(ew, "teamlead", ew.player.x + 150)
        d.element = tgt
        ew.player.fire_cd = 0.0
        ew.key_down("fire"); ew.update(DT); ew.key_up("fire")
        assert sum(1 for b in ew.bullets if b.owner == "player") == 1
        b = next(b for b in ew.bullets if b.owner == "player")
        assert b.mdmg == magic and b.element == "cheongryong" and b.dmg == phys
        texts = set()
        for _ in range(30):
            ew.update(DT)
            texts |= {f["text"] for f in ew.effects if f["kind"] == "elem"}
            if d.hp < 20:
                break
        assert d.hp == 20 - want, (tgt, d.hp, want)
        assert (fx in texts) if fx else (not texts), (tgt, texts)
        seen[tgt] = 20 - d.hp
    _check_snapshot(ew.snapshot())
    print(f"PASS 12: element multiplier strong/weak/neutral -> damage {seen}, elem effects shown")

    # 13) mid boss: spawns after waves//2 on stage 2, mid=True + boss_hp shown, waves resume, stage still clears
    assert stages.get("mid_bosses") and "boss_mai" in stages["ranks"] and "boss_choi" in stages["ranks"]
    mid_ranks = {m["rank"] for m in stages["mid_bosses"]}
    assert mid_ranks == {"teamlead", "general", "deputy", "dino_gold"}, mid_ranks     # v1.9: + 황금 공룡
    bw = World(stages, config, {}, 1600, 360, seed=51)
    bw._start_game(2)
    waves = bw.stage["waves"]
    assert waves >= 2
    saw_mid = saw_mid_hp = saw_main = False
    mid_wave = None
    ticks = 0
    while bw.stage_no == 2 and ticks < 8000:
        bw.update(DT)
        ticks += 1
        snap = bw.snapshot()
        _check_snapshot(snap)
        mids = [e for e in bw.enemies if e.mid and e.alive]
        if bw.phase == "midboss" and mids:
            m = mids[0]
            assert m.boss and m.pattern == "mid" and m.rank in mid_ranks and m.element in ELEMENT_KEYS
            assert m.scale == 4 and m.palette == m.rank, (m.scale, m.palette)
            assert snap["hud"]["boss_hp"] is not None and snap["hud"]["boss_hp"] == m.hp
            assert any(e["mid"] for e in snap["enemies"])
            if not saw_mid:
                assert bw.banner and bw.banner.startswith("중간 보스 · "), bw.banner
                assert not saw_main and bw.wave_index == waves // 2, (bw.wave_index, waves)
                mid_wave = bw.wave_index
            saw_mid = True
            saw_mid_hp = True
        if bw.phase == "boss" and bw.boss_ref is not None and bw.boss_ref.alive:
            assert saw_mid and bw.mid_done and bw.wave_index == waves
            saw_main = True
        if bw.state == "play" and bw.enemies and ticks % 45 == 0:
            bw._debug_kill_all()
        if bw.state == "shop":
            bw.shop_index = len(SHOP_ORDER) - 1
            bw.state_t = 1.0
            bw.key_down("confirm"); bw.key_up("confirm")
    assert saw_mid and saw_mid_hp and saw_main and bw.stage_no == 3 and bw.state == "play", \
        (saw_mid, saw_main, bw.stage_no, bw.state, ticks)
    # stage 1 has no eligible mid boss (from_stage 2+): no midboss phase there
    ow = World(stages, config, {}, 1600, 360, seed=52)
    ow._start_game(1)
    assert not ow._mid_boss_eligible()
    # death during the mid boss restarts at the mid boss, not the whole stage
    dw2 = World(stages, config, {}, 1600, 360, seed=53)
    dw2._start_game(3)
    for _ in range(8000):
        dw2.update(DT)
        if dw2.phase == "midboss" and any(e.mid and e.alive for e in dw2.enemies):
            break
        if dw2.enemies and not dw2.player.dead:
            dw2._debug_kill_all()
    assert dw2.phase == "midboss", dw2.phase
    wave_before = dw2.wave_index
    dw2._debug_kill_player()
    _run(dw2, 1.2)
    assert dw2.state == "play" and dw2.phase == "midboss" and dw2.wave_index == wave_before and not dw2.mid_done
    _run(dw2, 1.5)
    assert any(e.mid and e.alive for e in dw2.enemies), "mid boss must respawn after death"
    # brawler AI (stage final boss) actually fights: melee contact or attack2 shot within a few seconds
    fw2 = World(stages, config, {"char": "jaehwi"}, 1600, 360, seed=54)
    fw2._start_game(2)
    fw2.enemies.clear(); fw2.pending.clear()
    fw2.phase = "boss"; fw2.boss_gap = 0.0
    fw2._spawn_boss()
    mb = fw2.boss_ref
    assert mb is not None and not mb.mid and mb.pattern == "brawler" and mb.palette in ("mai", "choi", "chang")
    assert mb.w == stages["ranks"][mb.rank]["hit_w"] and mb.h == stages["ranks"][mb.rank]["hit_h"]
    anims = set()
    saw_shot = False
    fw2.player.shield = 99                    # survive contact hits, count them via shield loss
    for _ in range(int(12 / DT)):
        fw2.update(DT)
        if not mb.alive:
            break
        anims.add(mb.anim)
        assert mb.anim in BRAWLER_ANIMS, mb.anim
        saw_shot = saw_shot or any(b.owner == "enemy" for b in fw2.bullets)
        fw2.player.inv_t = 0.0
    assert "attack" in anims or "attack2" in anims, anims
    assert saw_shot or fw2.player.shield < 99, (saw_shot, fw2.player.shield)
    mb.hurt_cd = 0.0
    fw2.player.x = mb.x + 120; fw2.player.facing = -1
    fw2.bullets.clear()
    fw2.player.fire_cd = 0.0
    fw2.key_down("fire"); fw2.update(DT); fw2.key_up("fire")
    hp0 = mb.hp
    for _ in range(20):
        fw2.update(DT)
        if mb.hp < hp0:
            break
    assert mb.hp < hp0 and mb.hurt_t > 0 and mb.anim == "hurt", (mb.hp, hp0, mb.hurt_t, mb.anim)
    print(f"PASS 13: mid boss after wave {mid_wave}/{waves} on stage 2, waves resume, stage clears ({ticks} ticks)")

    # 14) select screen up/down cycles the element, save round-trip restores it, stats drive speed
    vw = World(stages, config, {}, 1600, 360, seed=61)
    assert vw.snapshot()["hud"]["element_index"] == 0 and vw.element_key == ELEMENT_KEYS[0]
    vw.key_down("down"); vw.key_up("down")
    assert vw.element_key == ELEMENT_KEYS[1]
    vw.key_down("jump"); vw.key_up("jump")           # ↑ also sends "jump": must not cycle
    assert vw.element_key == ELEMENT_KEYS[1]
    vw.key_down("up"); vw.key_up("up")
    assert vw.element_key == ELEMENT_KEYS[0]
    vw.key_down("up"); vw.key_up("up")
    assert vw.element_key == ELEMENT_KEYS[-1]
    for _ in range(3):
        vw.key_down("down"); vw.key_up("down")
    assert vw.element_key == "jujak", vw.element_key
    h = vw.snapshot()["hud"]
    assert h["element"] == "jujak" and h["element_name"] == "주작" and h["element_index"] == 2
    assert h["element_names"] == ["청룡", "백호", "주작", "현무"] and h["element_colors"]["jujak"] == "#ef4444"
    assert h["stats"] == {"agi": 8, "str": 4, "int": 4} and h["char_stats"][1] == {"agi": 4, "str": 8, "int": 3}
    sd = json.loads(json.dumps(vw.save_data()))
    assert sd["element"] == "jujak"
    vw2 = World(stages, config, sd, 1600, 360, seed=62)
    assert vw2.element_key == "jujak" and vw2.snapshot()["player"]["element"] == "jujak"
    _run(vw2, 0.3); vw2.key_down("confirm"); vw2.key_up("confirm")
    assert vw2.state == "play" and vw2.snapshot()["player"]["element"] == "jujak"
    # stats-derived speed/jump
    jw3, hw3 = _quiet("jaehwi", 63), _quiet("hyunki", 64)
    assert abs(jw3._speed_mult(jw3.char) - 1.18) < 1e-9 and abs(hw3._speed_mult(hw3.char) - 0.94) < 1e-9
    assert abs(jw3._jump_mult(jw3.char) - 1.12) < 1e-9 and abs(hw3._jump_mult(hw3.char) - 0.96) < 1e-9
    assert jw3._phys_dmg(jw3.char) == 1 and hw3._phys_dmg(hw3.char) == 2 and hw3._magic_dmg(hw3.char) == 1
    dist = {}
    for name, ww in (("jaehwi", jw3), ("hyunki", hw3)):
        x0 = ww.player.x
        ww.keys.add("right")
        _run(ww, 0.5)
        dist[name] = ww.player.x - x0
    assert dist["jaehwi"] > dist["hyunki"] > 0, dist
    legacy = World(stages, {"characters": {"jaehwi": {"name": "L", "speed": 1.3, "jump": 1.2, "damage": 2.0}}},
                   {}, 1600, 360, seed=65)
    assert legacy._speed_mult(legacy.char) == 1.3 and legacy._jump_mult(legacy.char) == 1.2
    assert legacy._phys_dmg(legacy.char) == 2 and legacy._magic_dmg(legacy.char) == 0
    assert legacy.snapshot()["hud"]["stats"] is None
    _check_snapshot(legacy.snapshot())
    print(f"PASS 14: element select via up/down, save round-trip, stats-derived speed {dist}")

    # 15) stage final bosses rotate through final_bosses (dept title kept); mid bosses are palette bosses
    fb = stages["final_bosses"]
    assert fb == ["boss_mai", "boss_choi", "boss_chang"], fb
    for k in fb:
        r = stages["ranks"][k]
        assert r["pattern"] == "brawler" and r["boss_scale"] == 2 and set(r["proj"]) == {"speed", "w", "h"}, k
    assert stages["ranks"]["boss_mai"]["boss_hp"] == 150 and stages["ranks"]["boss_choi"]["boss_hp"] == 170
    assert stages["ranks"]["boss_chang"]["boss_hp"] == 190 and stages["ranks"]["boss_chang"]["title"] == "본부장 대행"
    assert stages["ranks"]["intern"]["hp"] == 3 and stages["ranks"]["teamlead"]["boss_hp"] == 60
    sw2 = World(stages, config, {}, 1600, 360, seed=71)
    for n, want in ((1, "boss_mai"), (2, "boss_choi"), (3, "boss_chang"), (4, "boss_mai"), (10, "boss_mai"),
                    (15, "boss_chang"), (16, "boss_mai")):
        st = sw2._build_stage(n)
        assert st["kind"] == "dept" and st["bosses"] == [want], (n, st["bosses"])
        assert st["boss_titles"] == [stages["departments"][st["dept_idx"]]["boss_title"]], (n, st["boss_titles"])
    assert sw2._build_stage(1)["boss_titles"] == ["총무팀장"]
    assert sw2._build_stage(11)["bosses"] == ["director"] * 3 and sw2._build_stage(12)["bosses"] == ["md", "evp"]
    assert sw2._build_stage(13)["bosses"] == ["ceo"] and sw2._build_stage(14)["bosses"] == ["chairman"]
    sw2._start_game(1)
    sw2.enemies.clear(); sw2.pending.clear()
    sw2.phase = "boss"; sw2._spawn_boss()
    fbe = sw2.boss_ref
    assert fbe.rank == "boss_mai" and fbe.label == "총무팀장" and fbe.palette == "mai" and not fbe.mid
    assert fbe.hp_max == 150, fbe.hp_max
    for n, want, title in ((2, "teamlead", "팀장 대행"), (3, "general", "감사 부장"), (4, "general", "감사 부장"),
                           (5, "deputy", "기획 차장")):
        mw2 = World(stages, config, {}, 1600, 360, seed=72)
        mw2._start_game(n)
        mw2.enemies.clear(); mw2.pending.clear()
        mw2.phase = "midboss"; mw2._spawn_mid_boss()
        m = mw2.boss_ref
        assert m is not None and m.mid and m.boss and m.rank == want and m.label == title, (n, m.rank, m.label)
        assert m.pattern == "mid" and m.scale == 4 and mw2.snapshot()["hud"]["boss_hp"] == m.hp
        assert any(e["mid"] for e in mw2.snapshot()["enemies"])
    print("PASS 15: final bosses mai/choi/chang rotate by stage (dept title kept); palette mid bosses")

    # 16) equipment: granted by a department stage's final boss, slot order, save round-trip, effects
    qw = World(stages, config, {"char": "hyunki"}, 1600, 360, seed=81)
    qw._start_game(1)
    qw.enemies.clear(); qw.pending.clear(); qw.effects.clear()
    assert qw.equip == {"hat": 0, "gloves": 0, "suit": 0, "shoes": 0}
    assert qw.snapshot()["hud"]["equip_labels"] == {"hat": "안전모", "gloves": "작업 장갑", "suit": "사신 정장",
                                                     "shoes": "운동화"}
    # a mid boss must not grant
    mid = qw._make_enemy("teamlead", 900.0, boss=True, title="x"); mid.mid = True
    qw.enemies.append(mid); qw._damage_enemy(mid, 10 ** 9)
    assert sum(qw.equip.values()) == 0
    qw.enemies.clear(); qw.boss_ref = None
    order = []
    for i in range(5):
        qw.phase = "boss"; qw.boss_index = 0
        qw._spawn_boss()
        b = qw.boss_ref
        qw.effects.clear()
        qw._damage_enemy(b, 10 ** 9)
        assert not b.alive
        order.append(qw._equip_msg)
        assert qw.banner == qw._equip_msg and qw.banner_ttl == EQUIP_BANNER_T, (qw.banner, qw.banner_ttl)
        assert any(f["kind"] == "text" and "Lv" in (f["text"] or "") for f in qw.effects)
        qw.enemies.clear(); qw.boss_ref = None
    assert qw.equip == {"hat": 2, "gloves": 1, "suit": 1, "shoes": 1}, qw.equip
    assert order == ["장비 획득 · 안전모 Lv1", "장비 획득 · 작업 장갑 Lv1", "장비 획득 · 사신 정장 Lv1",
                     "장비 획득 · 운동화 Lv1", "장비 획득 · 안전모 Lv2"], order
    assert qw.snapshot()["hud"]["equip"] == qw.equip
    # executive stage bosses never grant
    xw = World(stages, config, {}, 1600, 360, seed=82)
    xw._start_game(11)
    xw.enemies.clear(); xw.pending.clear()
    xw.phase = "boss"; xw._spawn_boss(); xw._damage_enemy(xw.boss_ref, 10 ** 9)
    assert sum(xw.equip.values()) == 0
    # effects: hat -> shield max, gloves -> fire rate, shoes -> speed / jump, suit -> magic
    assert qw._shield_max() == 3 + 2, qw._shield_max()
    assert qw.snapshot()["hud"]["shield_max"] == 5
    assert abs(qw._speed_mult(qw.char) - 0.94 * 1.12) < 1e-9 and abs(qw._jump_mult(qw.char) - 0.96 * 1.08) < 1e-9
    assert qw._magic_dmg(qw.char) == 1 + 1, qw._magic_dmg(qw.char)
    assert abs(qw._fire_rate_mult(qw.char) - 1.2) < 1e-9
    base_w = World(stages, config, {"char": "hyunki"}, 1600, 360, seed=83)
    base_w._start_game(1)
    assert abs(base_w._fire_rate_mult(base_w.char) - 1.0) < 1e-9 and base_w._shield_max() == 3
    for ww in (qw, base_w):
        ww.enemies.clear(); ww.pending.clear(); ww.bullets.clear()
        ww._reset_player(); ww.player.x = 600.0
        ww.key_down("fire"); ww.update(DT); ww.key_up("fire")
    assert qw.player.fire_cd < base_w.player.fire_cd, (qw.player.fire_cd, base_w.player.fire_cd)
    assert qw.player.shield == 5 and base_w.player.shield == 3
    # save round-trip: kept on continue, reset on new game
    qw._start_stage(2)
    sd = json.loads(json.dumps(qw.save_data()))
    assert sd["equip"] == {"hat": 2, "gloves": 1, "suit": 1, "shoes": 1} and sd["stage"] == 2
    rw = World(stages, config, sd, 1600, 360, seed=84)
    assert rw.snapshot()["hud"]["equip"] == {"hat": 0, "gloves": 0, "suit": 0, "shoes": 0}
    _run(rw, 0.3); rw.key_down("confirm"); rw.key_up("confirm")
    assert rw.state == "continue"
    _run(rw, 0.3); rw.key_down("confirm"); rw.key_up("confirm")
    assert rw.state == "play" and rw.stage_no == 2 and rw.equip == sd["equip"] and rw._shield_max() == 5
    _check_snapshot(rw.snapshot())
    nw = World(stages, config, sd, 1600, 360, seed=85)
    _run(nw, 0.3); nw.key_down("confirm"); nw.key_up("confirm")
    nw.key_down("right"); nw.key_up("right")
    _run(nw, 0.3); nw.key_down("confirm"); nw.key_up("confirm")
    assert nw.state == "play" and nw.stage_no == 1 and sum(nw.equip.values()) == 0
    # the clear banner carries the pickup
    qw2 = World(stages, config, {}, 1600, 360, seed=86)
    qw2._start_game(1)
    qw2.enemies.clear(); qw2.pending.clear()
    qw2.phase = "boss"; qw2._spawn_boss(); qw2._damage_enemy(qw2.boss_ref, 10 ** 9)
    _run(qw2, 1.0)
    assert qw2.state == "stage_clear" and qw2.snapshot()["hud"]["banner"] == "STAGE CLEAR · 장비 획득 · 안전모 Lv1"
    print(f"PASS 16: equipment granted by stage bosses in slot order {list(qw.equip.items())}, saved, effects apply")

    # 17) stat shop: str -> phys dmg, int -> bullet speed + magic, agi -> speed; max 0 unlimited; item tweaks
    tw = _quiet("jaehwi", 91)                    # jaehwi 8/4/4
    def _shot(world):
        world.bullets.clear(); world.player.fire_cd = 0.0
        world.key_down("fire"); world.update(DT); world.key_up("fire")
        return [b for b in world.bullets if b.owner == "player"]
    b0 = _shot(tw)[0]
    assert b0.dmg == 1 and b0.mdmg == 1 and abs(b0.vx - BULLET_SPEED * 0.92) < 1e-6, (b0.dmg, b0.mdmg, b0.vx)
    tw.upgrades["str"] = 2
    assert tw._eff_stats(tw.char) == {"agi": 8, "str": 6, "int": 4} and tw.snapshot()["hud"]["stats"]["str"] == 6
    assert _shot(tw)[0].dmg == 2
    tw.upgrades["int"] = 2                       # int 6 -> vx 700 * 1.08, magic 2
    b2 = _shot(tw)[0]
    assert abs(b2.vx - BULLET_SPEED * 1.08) < 1e-6 and b2.mdmg == 2, (b2.vx, b2.mdmg)
    sp0 = tw._speed_mult(tw.char)
    tw.upgrades["agi"] = 2
    assert abs(tw._speed_mult(tw.char) - (sp0 + 0.12)) < 1e-9 and abs(tw._jump_mult(tw.char) - 1.2) < 1e-9
    tw.upgrades["str"] = 50
    tw._open_shop()
    tw.score = 10 ** 9
    view = tw._shop_view()
    row = next(r for r in view["items"] if r["key"] == "str")
    assert row["max"] == 0 and row["level"] == 50 and row["afford"], row
    assert view["stats"] == {"agi": 10, "str": 54, "int": 6}
    assert [r["key"] for r in view["items"]] == list(SHOP_ORDER)
    tw.shop_index = 0; tw.state_t = 1.0
    tw.key_down("confirm"); tw.key_up("confirm")
    assert tw.upgrades["str"] == 51 and "Lv51" in tw.shop_msg, (tw.upgrades["str"], tw.shop_msg)
    rate_row = next(r for r in view["items"] if r["key"] == "rate")
    assert rate_row["max"] == 5
    _check_snapshot(tw.snapshot())
    tw._set_state("play")
    tw.upgrades = {k: 0 for k in tw.shop_items}
    # items: missile ttl None + speed, spread ±0.044 rad, laser dmg halved
    tw._give_item("homing")
    m = _shot(tw)[0]
    assert m.kind == "missile" and m.ttl is None and abs(abs(m.vx) - MISSILE_SPEED * 0.92) < 1e-6, (m.ttl, m.vx)
    assert MISSILE_SPEED == 700.0 and MISSILE_TURN == 14.0        # v1.9: slower missiles that curl back
    tw._give_item("spread")
    sb = _shot(tw)
    assert len(sb) == 3
    angs = sorted(round(math.atan2(b.vy, abs(b.vx)), 3) for b in sb)
    assert angs == [-0.044, 0.0, 0.044], angs                      # v1.9: ±2.5°
    tw._give_item("laser")
    lz = _shot(tw)[0]
    assert lz.kind == "laser" and lz.dmg == max(1, (1 + 1) // 2) == 1
    hw4 = _quiet("hyunki", 92)                   # str 8 -> phys 2 -> laser (2+1)//2 = 1
    hw4._give_item("laser")
    assert _shot(hw4)[0].dmg == 1
    hw4.upgrades["str"] = 4                      # str 12 -> phys 4 -> laser 2
    assert _shot(hw4)[0].dmg == 2
    print("PASS 17: stat shop str/agi/int effects, unlimited levels, missile/spread/laser tweaks")

    # 18) brawler "proj" bullets carry sprite / anim / frame / flip through the snapshot
    pw = _quiet("jaehwi", 93)
    for key, w_h in (("boss_chang", (34, 34)), ("boss_mai", (40, 22)), ("boss_choi", (48, 24))):
        pw.enemies.clear(); pw.bullets.clear()
        be = pw._make_enemy(key, pw.player.x + 400, boss=True)
        be.intro = False; be.facing = -1
        pw.enemies.append(be)
        pw._brawler_shot(be)
        pb = pw.bullets[-1]
        assert pb.kind == "proj" and pb.sprite == be.palette and pb.anim == "proj" and pb.frame == 0
        assert (pb.w, pb.h) == w_h and pb.owner == "enemy" and pb.vx < 0
        spd = ENEMY_BULLET_SPEED * stages["ranks"][key]["proj"]["speed"]
        assert abs(math.hypot(pb.vx, pb.vy) - spd) < 1e-6
        snapb = [b for b in pw.snapshot()["bullets"] if b["kind"] == "proj"][-1]
        assert snapb["sprite"] == be.palette and snapb["anim"] == "proj" and snapb["frame"] == 0 and snapb["flip"]
        _check_snapshot(pw.snapshot())
    pw.player.inv_t = 99.0
    _run(pw, 0.5)
    assert pw.bullets and pw.bullets[-1].frame == 4, pw.bullets[-1].frame     # 8 fps
    assert pw.snapshot()["bullets"][-1]["frame"] == 4
    pw.enemies.clear(); pw.bullets.clear()
    plain = pw._make_enemy("director", pw.player.x + 400, boss=True)
    plain.pattern = "brawler"; plain.intro = False
    pw.enemies.append(plain); pw._brawler_shot(plain)
    assert pw.bullets[-1].kind == "normal" and pw.bullets[-1].sprite is None and pw.bullets[-1].anim is None
    snapn = pw.snapshot()["bullets"][-1]
    assert snapn["sprite"] is None and snapn["anim"] is None and snapn["frame"] == 0 and snapn["flip"] is True
    # a real fight on stage 3 (chang) produces proj bullets
    cw3 = World(stages, config, {"char": "jaehwi"}, 1600, 360, seed=94)
    cw3._start_game(3)
    cw3.enemies.clear(); cw3.pending.clear()
    cw3.phase = "boss"; cw3.boss_gap = 0.0; cw3._spawn_boss()
    assert cw3.boss_ref.rank == "boss_chang"
    cw3.player.shield = 99
    saw_proj = False
    for _ in range(int(12 / DT)):
        cw3.update(DT)
        cw3.player.inv_t = 0.0
        s = cw3.snapshot()
        _check_snapshot(s)
        saw_proj = saw_proj or any(b["kind"] == "proj" and b["sprite"] == "chang" for b in s["bullets"])
        if saw_proj:
            break
    assert saw_proj, "chang never threw its ball"
    print("PASS 18: brawler proj bullets: sprite/anim/frame/flip in snapshot, 8 fps anim")

    # 19) v1.8 tempo + motion variety: x2 speed (+10 %/stage, capped), halved gaps, sprint / pause modes,
    #     ground-burst and sky-drop spawns announced by warnings, landing dust, contact damage
    vw = _quiet("jaehwi", 94)
    base = float(stages["ranks"]["intern"]["speed"])
    for st, want in ((1, 2.0), (2, 2.2), (5, 2.0 * 1.1 ** 4), (13, 6.0), (30, 6.0)):
        vw.stage_no = st
        assert abs(vw._enemy_speed_mult() - want) < 1e-9, (st, vw._enemy_speed_mult())
        en = vw._make_enemy("intern", 900.0)
        assert abs(en.speed - base * want) < 1e-6, (st, en.speed)
    vw.stage_no = 1
    bz = vw._make_enemy("teamlead", 1500.0, boss=True)
    assert abs(bz.speed - stages["ranks"]["teamlead"]["boss_speed"] * 2.0) < 1e-6, bz.speed
    assert DEFAULT_WAVE["spawn_stagger"] == 0.3 and vw.wave_cfg["spawn_stagger"] == 0.3
    assert WAVE_GAP == 0.5 and BOSS_GAP == 0.5 and BOSS_NEXT_GAP == 0.6 and CLEAR_TO_SHOP == 1.0
    # movement modes: over 12 s of approaching from far away, a grunt walks, sprints and pauses
    vw.enemies.clear(); vw.pending.clear(); vw.bullets.clear()
    vw.player.x = 300.0
    far = vw._make_enemy("intern", 1700.0)
    far.stop_dist = 50.0
    far.fire_rate = 0.0
    vw.enemies.append(far)
    seen, sprint_snap = set(), False
    for _ in range(360):
        far.x = max(far.x, 1200.0)                 # keep it far so it stays in approach mode
        vw.update(1 / 30)
        seen.add(far.move_mode)
        if far.move_mode == "sprint":
            assert abs(far.vx) > far.speed * 1.5 and far.anim_rate == SPRINT_MULT
            sprint_snap = sprint_snap or [e for e in vw.snapshot()["enemies"] if e["id"] == far.id][0]["sprint"]
        elif far.move_mode == "pause":
            assert far.vx == 0.0 and far.anim == "idle"
    assert seen == {"walk", "sprint", "pause"}, seen
    assert sprint_snap
    # spawn kinds: slot 0 always a side spawn, later slots mix; special chance grows with stage
    vw.stage_no = 1
    assert all(vw._pick_spawn_kind(0) == "side" for _ in range(50))
    kinds1 = [vw._pick_spawn_kind(3) for _ in range(2000)]
    vw.stage_no = 9
    kinds9 = [vw._pick_spawn_kind(3) for _ in range(2000)]
    r1 = 1 - kinds1.count("side") / 2000
    r9 = 1 - kinds9.count("side") / 2000
    assert 0.10 < r1 < 0.20 and 0.50 < r9 < 0.60, (r1, r9)
    assert {"ground", "sky"} <= set(kinds9)
    # ground burst: warning -> enemy rises through the floor -> lands, stunned, dust puffs
    vw.stage_no = 1
    vw.enemies.clear(); vw.pending.clear(); vw.warnings.clear(); vw.effects.clear()
    vw.pending.append(("staff", 0, "ground"))
    vw.spawn_t = 0.0
    vw.update(1 / 30)
    assert len(vw.warnings) == 1 and not vw.enemies
    wsnap = vw.snapshot()["warnings"]
    assert len(wsnap) == 1 and wsnap[0]["kind"] == "ground" and wsnap[0]["ttl"] == WARN_T["ground"]
    assert abs(wsnap[0]["x"] - vw.player.x) >= SPAWN_KEEP_OUT
    assert vw.phase == "wave" and vw.wave_gap == WAVE_GAP
    _run(vw, WARN_T["ground"] - 0.05)
    assert vw.warnings and vw.wave_gap == WAVE_GAP, "a live warning must hold the wave open"
    _run(vw, 0.1)
    assert not vw.warnings and len(vw.enemies) == 1
    ge = vw.enemies[0]
    assert ge.spawn_kind == "ground" and ge.vy < 0 and ge.y > vw.ground_y and not ge.on_ground
    assert any(f["kind"] == "dust" for f in vw.effects)
    top = ge.y
    for _ in range(60):
        vw.update(1 / 30)
        top = min(top, ge.y)
        if ge.on_ground:
            break
    assert ge.on_ground and ge.y == vw.ground_y and top < vw.ground_y - POP_EXTRA * 0.5, top
    assert ge.land_t > 0 and ge.vx == 0.0 and ge.spawn_kind == "side"
    _run(vw, LAND_STUN + 0.1)
    assert ge.land_t <= 0
    # sky drop: warning -> enemy appears above the band, falls, lands with dust; "drop" flag in snapshot
    vw.enemies.clear(); vw.pending.clear(); vw.warnings.clear(); vw.effects.clear()
    vw.pending.append(("staff", 1, "sky"))
    vw.spawn_t = 0.0
    vw.update(1 / 30)
    assert vw.warnings[0]["kind"] == "sky"
    _run(vw, WARN_T["sky"] + 0.05)
    se = vw.enemies[0]
    assert se.drop and se.y < 0 and not se.on_ground
    assert [e for e in vw.snapshot()["enemies"] if e["id"] == se.id][0]["drop"] is True
    for _ in range(60):
        vw.update(1 / 30)
        if se.on_ground:
            break
    assert se.on_ground and not se.drop and se.land_t > 0
    assert any(f["kind"] == "dust" for f in vw.effects)
    _check_snapshot(vw.snapshot())
    # a drop landing on the player costs a hit
    vw.enemies.clear(); vw.warnings.clear(); vw.bullets.clear()
    vw.player.inv_t = 0.0
    lives0 = vw.lives
    de = vw._make_enemy("staff", vw.player.x)
    de.drop = True; de.on_ground = False; de.y = vw.player.y - 60; de.vy = 300.0
    vw.enemies.append(de)
    _run(vw, 0.3)
    assert vw.player.dead or vw.player.shield < vw._shield_max(), "sky drop must hit the player"
    # no special spawn spot when the player blocks the whole band -> side fallback
    vw.enemies.clear(); vw.pending.clear(); vw.warnings.clear()
    vw.player.dead = False
    vw.pits = [(vw.width * 0.22 - 40, vw.width * 0.7)]
    vw.pending.append(("staff", 0, "sky"))
    vw.spawn_t = 0.0
    vw.update(1 / 30)
    assert not vw.warnings and len(vw.enemies) == 1 and vw.enemies[0].x < 0
    vw.pits = []
    print("PASS 19: enemy speed x2 (+10 %/stage, cap 3x), gaps halved, walk/sprint/pause, ground/sky spawns + warnings")

    # 20) v1.9: inventory, per-character melee, enemy melee, allies, bomb / coffee, typing words, money,
    #     difficulty, town (shop / box / warehouse / gambling), gravity bombs, balance log, save round-trip
    def _fresh(char, seed, stage=1, money=0, diff="normal"):
        fw_ = World(stages, config, {"char": char, "money": money, "difficulty": diff}, 1920, 340, seed=seed)
        fw_._start_game(stage)
        fw_.enemies.clear(); fw_.pending.clear(); fw_.warnings.clear(); fw_.bullets.clear(); fw_.words.clear()
        fw_.words_left = 0
        fw_.player.x = 600.0
        fw_.player.inv_t = 0.0
        return fw_
    # inventory: stacking, full slots leave items on the floor, use by slot
    iw = _fresh("jaehwi", 101)
    for k in ("bomb", "bomb", "coffee", "laser", "drone", "dog", "decoy"):
        iw.items.append(Item(iw.player.x, iw.player.y - 5, k))
    _run(iw, 0.2)
    inv = iw.inventory
    assert inv[0] == {"kind": "bomb", "count": 2} and inv[1]["kind"] == "coffee" and inv[4]["kind"] == "dog", inv
    assert len(iw.items) == 1 and iw.items[0].kind == "decoy", "6th kind must stay on the floor when slots are full"
    assert iw.snapshot()["hud"]["inventory"][0]["count"] == 2
    iw.key_down("slot2"); iw.key_up("slot2")
    assert iw.inventory[1] is None and abs(iw.slow_t - COFFEE_T) < 1e-9
    slowed = iw._make_enemy("staff", 1400.0); slowed.fire_rate = 0.0; slowed.stop_dist = 50.0
    iw.enemies.append(slowed)
    x0 = slowed.x
    _run(iw, 0.5)
    moved_slow = x0 - slowed.x
    assert 0 < moved_slow < slowed.speed * 0.5 * 0.7, moved_slow          # 40 % speed under coffee
    assert iw.snapshot()["enemies"][0]["slow"] is True
    iw.slow_t = 0.0
    # bomb: grunts die, boss loses 15 %, enemy bullets vanish
    bz = iw._make_enemy("teamlead", 1500.0, boss=True); bz.intro = False
    iw.enemies.append(bz)
    iw.bullets.append(Bullet(700, iw.ground_y - 20, 8, 4, -300.0, 0.0, "enemy"))
    iw.key_down("slot1"); iw.key_up("slot1")
    assert iw.inventory[0] == {"kind": "bomb", "count": 1}
    assert not slowed.alive and bz.alive and bz.hp == bz.hp_max - max(1, int(bz.hp_max * BOMB_BOSS_FRAC))
    assert all(b.dead for b in iw.bullets if b.owner == "enemy")
    assert any(b.kind == "blast" for b in iw.bullets)
    _check_snapshot(iw.snapshot())
    # allies: drone fires missiles, dog bites, decoy draws fire and dies after 3 hits
    iw.enemies.clear(); iw.bullets.clear()
    tgt = iw._make_enemy("staff", 760.0); tgt.fire_rate = 0.0; tgt.speed = 0.0; tgt.stop_dist = 5.0
    tgt.hp = tgt.hp_max = 60
    iw.enemies.append(tgt)
    iw.key_down("slot3"); iw.key_up("slot3")             # laser -> weapon
    assert iw.player.weapon == "laser"
    iw.key_down("slot4"); iw.key_up("slot4")             # drone
    iw.key_down("slot5"); iw.key_up("slot5")             # dog
    assert {a.kind for a in iw.allies} == {"drone", "dog"}
    _run(iw, 2.0)
    assert any(b.kind == "missile" for b in iw.bullets) or tgt.hp < 60, "drone must shoot"
    assert tgt.hp < 60, "dog / drone must have damaged the target"
    snap_a = iw.snapshot()["allies"]
    assert {a["kind"] for a in snap_a} == {"drone", "dog"} and all(0 < a["t"] <= a["ttl"] for a in snap_a)
    iw.items.append(Item(iw.player.x, iw.player.y - 5, "decoy"))
    _run(iw, 0.1)
    slot_i = next(i for i, it in enumerate(iw.inventory) if it and it["kind"] == "decoy")
    iw._use_slot(slot_i)
    dec = next(a for a in iw.allies if a.kind == "decoy")
    iw.player.x = 300.0                                  # step away so the shots reach the decoy, not the player
    for _ in range(3):
        iw.bullets.append(Bullet(dec.x - 40, dec.y - PLAYER_H / 2, 8, 4, 400.0, 0.0, "enemy"))
        _run(iw, 0.2)
    assert all(a.kind != "decoy" for a in iw.allies), "decoy must die after 3 hits"
    _run(iw, DRONE_T)
    assert not iw.allies, "companions expire"
    # per-character melee (auto-switch inside reach)
    def _melee_probe(char, seed):
        mw_ = _fresh(char, seed)
        foe = mw_._make_enemy("staff", mw_.player.x + 30); foe.fire_rate = 0.0; foe.speed = 0.0
        foe.hp = foe.hp_max = 500
        mw_.enemies.append(foe)
        mw_.player.facing = 1
        return mw_, foe
    kw, kf = _melee_probe("jaehwi", 102)
    kw.keys.add("fire")
    hits = []
    for _ in range(40):
        kw.update(1 / 30)
        if kw.player.combo and (not hits or hits[-1] != kw.player.combo):
            hits.append(kw.player.combo)
    assert hits[:3] == [1, 2, 3], hits
    assert kf.hp < 500 and not any(b.owner == "player" for b in kw.bullets), "knife: melee, no bullets"
    assert kw.snapshot()["hud"]["melee_style"] == "knife"
    hw, hf = _melee_probe("hyunki", 103)
    hw.keys.add("fire"); _run(hw, 0.3)
    assert any(b.kind == "wave" for b in hw.bullets) and hf.x > hw.player.x + 30, "hammer: shockwave + knockback"
    assert hw.snapshot()["hud"]["melee_style"] == "hammer"
    ww, wf = _melee_probe("dongil", 104)
    far2 = ww._make_enemy("staff", ww.player.x + 85); far2.fire_rate = 0.0; far2.speed = 0.0; far2.hp = far2.hp_max = 500
    ww.enemies.append(far2)
    ww.keys.add("fire"); _run(ww, 0.3)
    assert wf.hp < 500 and far2.hp < 500, "whip hits every enemy in reach"
    assert any(f["kind"] == "slash" for f in ww.effects) or ww.player.melee_t >= 0
    # enemy melee: an adjacent grunt swings and takes a shield charge / life
    ew = _fresh("hyunki", 105)
    ew.player.shield = 3
    foe = ew._make_enemy("staff", ew.player.x + 20); foe.fire_rate = 0.0; foe.speed = 0.0
    foe.attack_cd = 0.0
    ew.enemies.append(foe)
    ew.keys.clear()
    _run(ew, 1.0)
    assert ew.player.shield < 3, "enemy melee must land"
    assert foe.attack_cd > 0
    # words: two per stage, correct letters advance, wrong letter resets, completion pays out, miss when landed
    tw9 = _fresh("jaehwi", 106)
    tw9.words_left = WORDS_PER_STAGE; tw9.word_next = 0.0
    tw9.phase = "wave"
    tw9.update(1 / 30)
    assert len(tw9.words) == 1 and tw9.words_left == WORDS_PER_STAGE - 1
    wd = tw9.words[0]
    assert set(wd["text"]) <= WORD_LETTERS and wd["kind"] in WORD_KINDS
    wd["kind"] = "money"
    m0 = tw9.money
    tw9.key_down("char:" + wd["text"][0]); tw9.key_up("char:" + wd["text"][0])
    assert wd["typed"] == 1
    wrong = next(ch_ for ch_ in "abdefghijklmnoqrstvwy" if ch_ != wd["text"][1])
    tw9.key_down("char:" + wrong)
    assert wd["typed"] == 0, "wrong letter resets the word"
    for ch_ in wd["text"]:
        tw9.key_down("char:" + ch_); tw9.key_up("char:" + ch_)
    assert not tw9.words and tw9.money > m0 and any(f["kind"] == "word" for f in tw9.effects)
    tw9.word_next = 0.0
    tw9.update(1 / 30)
    assert len(tw9.words) == 1 and tw9.words_left == 0
    tw9.words[0]["y"] = tw9.ground_y - 9
    tw9.update(1 / 30)
    assert not tw9.words, "a landed word is lost"
    tw9.word_next = 0.0
    _run(tw9, 1.0)
    assert not tw9.words, "only WORDS_PER_STAGE words per stage"
    _check_snapshot(tw9.snapshot())
    # money: kills drop coins that fly to the player
    cw9 = _fresh("jaehwi", 107)
    vic = cw9._make_enemy("staff", cw9.player.x + 200); vic.fire_rate = 0.0; vic.speed = 0.0
    cw9.enemies.append(vic)
    m0 = cw9.money
    cw9._damage_enemy(vic, 10 ** 6)
    assert any(it.kind == "coin" and it.value > 0 for it in cw9.items)
    _run(cw9, 1.5)
    assert cw9.money > m0 and not any(it.kind == "coin" for it in cw9.items), (cw9.money, m0)
    # difficulty: locks and multipliers
    dw = World(stages, config, {"difficulty": "crazy"}, 1920, 340, seed=108)
    assert dw.difficulty_key == "normal", "crazy is locked without clears"
    dw.best_clear = {"normal": 20}
    assert not dw._diff_locked("hell") and dw._diff_locked("crazy")
    dw.best_clear = {"hell": 30}
    assert not dw._diff_locked("crazy")
    dw._set_state("select"); dw.state_t = 1.0
    seen_d = set()
    for _ in range(6):
        dw.key_down("skill"); dw.key_up("skill")
        seen_d.add(dw.difficulty_key)
    assert seen_d == set(DIFFICULTIES), seen_d
    dw.difficulty_index = DIFFICULTIES.index("crazy")
    st_c = dw._build_stage(1)
    assert abs(st_c["mult"]["hp"] - 3.0) < 1e-9 and abs(st_c["mult"]["speed"] - 2.0) < 1e-9 and st_c["mult"]["money"] == 3.0
    assert dw.snapshot()["hud"]["difficulty_label"] == "크레이지" and len(dw.snapshot()["hud"]["difficulty_locked"]) == 6
    # boss jump : dash odds ~ 1 : 5
    bw9 = _fresh("jaehwi", 109)
    jumps = dashes = 0
    for _ in range(600):
        br = bw9._make_enemy("boss_mai", bw9.player.x + 600, boss=True); br.intro = False; br.jump_cd = 0.0
        br.attack_cd = 9.0; br.ranged_cd = 9.0
        bw9.enemies = [br]
        bw9._brawler_ai(br, 1 / 30, bw9.player.x - br.x, 600.0)
        if br.vy < 0:
            jumps += 1
        elif br.dash_t > 0:
            dashes += 1
    assert jumps + dashes == 600 and 0.10 < jumps / 600 < 0.24, (jumps, dashes)
    # gravity bomb projectile: lands, waits for the fuse, blasts
    gw = _fresh("jaehwi", 110)
    gw.ranks["_bomber_test"] = {"title": "폭탄", "kind": "grunt", "hp": 3, "speed": 0, "fire_rate": 0,
                                "proj": {"gravity": True, "fuse": 0.5, "blast": 40, "w": 12, "h": 12, "speed": 1.0}}
    bomber = gw._make_enemy("_bomber_test", gw.player.x + 260); bomber.speed = 0.0
    gw.enemies.append(bomber)
    gw._enemy_shoot_any(bomber)
    pb = gw.bullets[-1]
    assert pb.gravity and pb.kind == "proj" and pb.fuse == 0.5
    for _ in range(90):
        gw.update(1 / 30)
        if any(b.kind == "blast" for b in gw.bullets):
            break
    assert any(b.kind == "blast" and b.owner == "enemy" for b in gw.bullets), "bomb must blast after landing"
    _check_snapshot(gw.snapshot())
    # town after stage 5: buy gear, open a box, equip / unequip / sell, gamble, next stage; save round-trip
    tw5 = _fresh("jaehwi", 111, stage=5, money=200000)
    tw5._stage_clear()
    assert tw5.state == "stage_clear" and tw5.best_clear["normal"] == 5
    log = tw5.drain_log()
    assert len(log) == 1 and log[0]["reason"] == "clear" and log[0]["stage"] == 5 and "player" in log[0], log
    assert set(log[0]) >= {"duration", "enemy_hp_avg", "ttk_avg", "hits_shield", "hits_life", "money_gained"}
    _run(tw5, CLEAR_TO_SHOP + 0.1)
    assert tw5.state == "town" and len(tw5.shop_stock) == 10
    snap_t = tw5.snapshot()
    _check_snapshot(snap_t)
    town = snap_t["hud"]["town"]
    assert town["tab"] == "stat" and len(town["tabs"]) == 4 and len(town["shop"]["stock"]) == 11
    tw5.key_down("tab"); tw5.key_up("tab")
    assert tw5._town_tab() == "shop"
    tw5.state_t = 1.0
    m0 = tw5.money
    tw5.key_down("confirm"); tw5.key_up("confirm")             # buy stock[0]
    assert tw5.money < m0 and len(tw5.shop_stock) == 9 and len(tw5.warehouse.items) == 1, tw5.town["msg"]
    for _ in range(9):
        tw5.key_down("right"); tw5.key_up("right")
    assert tw5._town_list("shop")[tw5.town["index"]["shop"]][0] == "box"
    m1 = tw5.money
    tw5.key_down("confirm"); tw5.key_up("confirm")             # random box
    assert tw5.money != m1 or tw5.town["msg"].startswith("랜덤박스"), tw5.town["msg"]
    tw5.key_down("tab"); tw5.key_up("tab")                     # store
    assert tw5._town_tab() == "store" and tw5.town["store_mode"] == "list"
    n_items = len(tw5.warehouse.items)
    tw5.key_down("confirm"); tw5.key_up("confirm")             # equip item 0
    eq_slot = next(k for k, v in tw5.warehouse.equipped.items() if v)
    assert len(tw5.warehouse.items) == n_items - 1 and tw5.snapshot()["hud"]["equipped"][eq_slot]
    fx = tw5._equip_fx()
    assert isinstance(fx, dict) and "shield" in fx
    tw5.key_down("down"); tw5.key_up("down")                   # equipped row
    assert tw5.town["store_mode"] == "equipped"
    while tw5._town_list("store")[tw5.town["index"]["store"]][1] != eq_slot:
        tw5.key_down("right"); tw5.key_up("right")
    tw5.key_down("confirm"); tw5.key_up("confirm")             # unequip
    assert tw5.warehouse.equipped[eq_slot] is None and len(tw5.warehouse.items) == n_items
    tw5.key_down("up"); tw5.key_up("up")                       # back to list
    m2 = tw5.money
    tw5.key_down("skill"); tw5.key_up("skill")                 # sell item 0
    assert tw5.money > m2 and len(tw5.warehouse.items) == n_items - 1
    tw5.key_down("tab"); tw5.key_up("tab")                     # gamble
    assert tw5._town_tab() == "gamble"
    tw5.warehouse.items.append(economy.make_equipment(tw5.rng, "hat", "normal", 0, 5))
    tw5.warehouse.equip(len(tw5.warehouse.items) - 1)
    tw5.town["index"]["gamble"] = 0
    tw5.key_down("confirm"); tw5.key_up("confirm")             # upgrade gamble
    assert tw5.town["gambles" if False else "msg"], "gamble message"
    tw5.key_down("right"); tw5.key_up("right")
    m3 = tw5.money
    tw5.key_down("confirm"); tw5.key_up("confirm")             # double-up
    assert tw5.money != m3
    tw5.key_down("right"); tw5.key_up("right")
    tw5.key_down("confirm"); tw5.key_up("confirm")             # slots
    assert tw5.town["reels"] is not None and len(tw5.town["reels"]) == 3
    _check_snapshot(tw5.snapshot())
    sd = tw5.save_data()
    assert sd["money"] == tw5.money and sd["difficulty"] == "normal" and sd["best_clear"] == {"normal": 5}
    assert sd["warehouse"]["equipped"]["hat"] is not None and len(sd["inventory"]) == INV_SLOTS
    rw = World(stages, config, sd, 1920, 340, seed=1)
    assert rw.money == tw5.money and rw.warehouse.to_save() == sd["warehouse"] and rw.best_clear == {"normal": 5}
    tw5.key_down("right"); tw5.key_up("right")                 # -> "next"
    assert tw5._town_list("gamble")[tw5.town["index"]["gamble"]][0] == "next"
    tw5.key_down("confirm"); tw5.key_up("confirm")
    assert tw5.state == "play" and tw5.stage_no == 6 and tw5.town is None
    # game over keeps money / warehouse (meta progression)
    go = _fresh("jaehwi", 112, money=777)
    go.lives = 1
    go._kill_player(force=True)
    _run(go, 1.2)
    assert go.state == "game_over" and go.money == 777 and go.save_data()["money"] == 777
    assert go.drain_log() and go.drain_log() == []
    print("PASS 20: inventory, melee styles, enemy melee, allies, bomb/coffee, typing words, money, difficulty,"
          " boss odds, gravity bombs, town, save, balance log")

    dtms = (time.perf_counter() - t0) * 1000
    print(f"SELFTEST OK ({dtms:.0f} ms)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print("game.py: pure logic module. Run with --selftest.")
