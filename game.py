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
DEFAULT_UNLOCK_STAGE = 5
DEFAULT_SHOP = {                # key: [label, base cost, cost growth per level, max level]
    "damage": ["공격력 +1", 3000, 1.7, 5],
    "rate": ["연사 +20%", 2500, 1.6, 5],
    "shield": ["실드 +1", 4000, 1.8, 3],
    "life": ["목숨 +1", 5000, 2.0, 3],
}
SHOP_ORDER = ("damage", "rate", "shield", "life", "next")
MAX_ENEMIES, MAX_BULLETS, MAX_EFFECTS = 14, 40, 30
DASH_SPEED = 520.0
STAMP_SPEED = 450.0
MISSILE_SPEED = 430.0
MISSILE_TURN = 7.0              # rad/s
ITEM_TTL = 9.0                  # s an item stays on the floor
ITEM_KINDS = ("laser", "homing", "spread", "rapid", "life")
ITEM_LABEL = {"laser": "레이저", "homing": "유도탄", "spread": "3연발", "rapid": "속사", "life": "1UP"}
WEAPON_TIME = {"laser": 10.0, "spread": 12.0, "rapid": 12.0}
HOMING_AMMO = 25
MAX_ITEMS = 6
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
MID_BANNER_T = 1.5
BRAWLER_ATTACK_T = 0.5          # s an attack / attack2 animation lasts
BRAWLER_HIT_WINDOW = (0.15, 0.35)   # contact damage window inside the melee attack
BRAWLER_HURT_T = 0.25
BRAWLER_HURT_CD = 1.5           # min s between hurt staggers (no stun-lock)
BRAWLER_JUMP_DIST = 260.0       # jump toward the player only when farther than this

ANIM_FPS = {"idle": 6, "run": 12, "jump": 1, "fall": 1, "shoot": 10, "shoot_run": 12,
            "crouch": 6, "crouch_shoot": 10, "death": 8, "victory": 6,
            "attack": 10, "attack2": 10, "hurt": 8}
DIFF_ORDER = ["easy", "normal", "hard"]
DIFF_LABEL = {"easy": "쉬움", "normal": "보통", "hard": "하드"}

DEFAULT_DIFFICULTY = {"easy": {"hp": 0.8, "speed": 0.9, "count": 0.8},
                      "normal": {"hp": 1.0, "speed": 1.0, "count": 1.0},
                      "hard": {"hp": 1.6, "speed": 1.25, "count": 1.4}}
DEFAULT_WAVE = {"base_count": 3, "per_wave": 1, "per_stage": 0.35, "per_cycle": 1, "max_count": 10,
                "elite_ratio_base": 0.2, "elite_ratio_per_wave": 0.1, "elite_ratio_max": 0.5,
                "spawn_stagger": 0.6}
DEFAULT_CHAR = {"name": "?", "trait": "", "damage": 1.0, "speed": 1.0, "fire_rate": 1.0,
                "jump": 1.0, "pierce": False}

CONFIRM_GUARD = 0.25      # s after a state change during which confirm/fire is ignored (Space = confirm+fire)


# ---------------------------------------------------------------- helpers
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
    __slots__ = ("x", "y", "vx", "vy", "on_ground", "facing", "anim", "frame", "anim_t", "hold_frame")

    def __init__(self):
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
        self.anim_t += dt
        step = 1.0 / fps
        while self.anim_t >= step:
            self.anim_t -= step
            if self.hold_frame is not None and self.anim in ("death", "victory") and self.frame >= self.hold_frame:
                self.anim_t = 0.0
                break
            self.frame += 1


class Player(_Ent):
    __slots__ = ("crouch", "fire_cd", "shoot_t", "inv_t", "dead", "death_t", "drop_t", "jump_buf", "on_platform",
                 "weapon", "weapon_t", "ammo", "shield", "skill_cd", "melee_t")

    def __init__(self):
        super().__init__()
        self.shield = 0
        self.skill_cd = 0.0
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
                 "element", "mid", "attack_t", "attack_cd", "ranged_cd", "hurt_t", "hurt_cd", "hit_done")

    def __init__(self):
        super().__init__()
        self.element = None         # ELEMENT_KEYS entry or None
        self.mid = False            # mid boss (brawler) flag
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
                 "kind", "ttl", "px", "py", "mdmg", "element")

    def __init__(self, x, y, w, h, vx, vy, owner, dmg=1, pierce=False, stamp=False, kind="normal", ttl=None,
                 mdmg=0, element=None):
        self.x, self.y, self.w, self.h = x, y, w, h
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
        self.kind = kind                 # "normal" | "laser" | "missile"
        self.ttl = ttl                   # seconds; None = until off-screen

    def swept_box(self):
        """Box covering the bullet's travel since the last tick (prevents tunnelling through thin targets)."""
        x0, x1 = (self.px, self.x) if self.px <= self.x else (self.x, self.px)
        y0, y1 = (self.py, self.y) if self.py <= self.y else (self.y, self.py)
        return (x0 - self.w / 2, y0 - self.h / 2, x1 + self.w / 2, y1 + self.h / 2)

    def box(self):
        return (self.x - self.w / 2, self.y - self.h / 2, self.x + self.w / 2, self.y + self.h / 2)


class Item:
    __slots__ = ("x", "y", "vy", "kind", "t", "on_ground")
    SIZE = 14

    def __init__(self, x, y, kind):
        self.x, self.y = float(x), float(y)
        self.vy = -260.0
        self.kind = kind
        self.t = ITEM_TTL
        self.on_ground = False

    def box(self):
        s = Item.SIZE
        return (self.x - s / 2, self.y - s, self.x + s / 2, self.y)


# ---------------------------------------------------------------- world
class World:
    """See INTERFACES.md section C."""

    STATES = ("select", "play", "stage_clear", "shop", "game_over", "paused", "continue")

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
        self.saved_upgrades = dict(save.get("upgrades") or {})
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
        self.pending: list[tuple] = []          # (rank, side)
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

    # ------------------------------------------------------------ stats / elements
    @staticmethod
    def _stats(c: dict) -> dict | None:
        s = c.get("stats")
        if isinstance(s, dict) and all(k in s for k in ("agi", "str", "int")):
            return {k: int(s[k]) for k in ("agi", "str", "int")}
        return None

    def _speed_mult(self, c: dict) -> float:
        s = self._stats(c)
        return 1.0 + SPEED_PER_AGI * (s["agi"] - STAT_BASE) if s else float(c.get("speed", 1.0))

    def _jump_mult(self, c: dict) -> float:
        s = self._stats(c)
        return 1.0 + JUMP_PER_AGI * (s["agi"] - STAT_BASE) if s else float(c.get("jump", 1.0))

    def _phys_dmg(self, c: dict) -> int:
        """Physical damage per shot, shop upgrade included."""
        s = self._stats(c)
        base = max(1, s["str"] // 3) if s else max(1, int(round(float(c.get("damage", 1.0)))))
        return base + self.upgrades.get("damage", 0)

    def _magic_dmg(self, c: dict) -> int:
        s = self._stats(c)
        return max(0, s["int"] // 3) if s else 0

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
        elif st == "shop":
            if key in ("left", "sel_left"):
                self.shop_index = (self.shop_index - 1) % len(SHOP_ORDER)
                self.shop_msg = ""
            elif key in ("right", "sel_right"):
                self.shop_index = (self.shop_index + 1) % len(SHOP_ORDER)
                self.shop_msg = ""
            elif key in ("confirm", "fire") and self.state_t >= CONFIRM_GUARD:
                self._shop_select()
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
            if self.state_t >= 2.0:
                self._open_shop()
        elif st in ("game_over", "shop"):
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
                         "hp_max": e.hp_max, "boss": e.boss, "element": e.element, "mid": e.mid}
                        for e in self.enemies],
            "bullets": [{"x": b.x, "y": b.y, "w": b.w, "h": b.h, "owner": b.owner, "kind": b.kind}
                        for b in self.bullets],
            "items": [{"x": it.x, "y": it.y, "kind": it.kind, "t": it.t} for it in self.items],
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
                    "stats": self._stats(self.char),
                    "char_stats": [self._stats(self.chars[k]) for k in CHAR_KEYS]},
        }

    def save_data(self) -> dict:
        return {"stage": int(self.save_stage), "best": int(self.best), "char": self.char_key,
                "char_name": self.char["name"], "hotkey": self.config.get("hotkey", "shift+0"),
                "upgrades": dict(self.saved_upgrades), "unlocked": sorted(self.unlocked),
                "element": self.element_key}

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
            self._set_banner(f"◀ {c['name']} ({c.get('trait', '')}) ▶")

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
            st["difficulty"] = DIFF_ORDER[cycle % 3]
            d = self.departments[idx % nd]
            kind = "dept"
        mult = dict(self.difficulty.get(st["difficulty"]) or DEFAULT_DIFFICULTY["normal"])
        bonus = st["cycle"] // 3               # after each full easy/normal/hard rotation, keep escalating
        mult = {"hp": float(mult.get("hp", 1)) + 0.25 * bonus,
                "speed": float(mult.get("speed", 1)) + 0.05 * bonus,
                "count": float(mult.get("count", 1)) + 0.1 * bonus}
        st.update({
            "kind": kind, "name": d.get("name", "?"), "mult": mult,
            "waves": int(d.get("waves", 0 if kind == "exec" else 3)),
            "grunts": list(d.get("grunts") or ["manager"]),
            "elites": list(d.get("elites") or []),
            "lab": bool(d.get("lab", False)),
            "platforms": int(d.get("platforms", 1)),
            "pits": int(d.get("pits", 0)),
        })
        if kind == "exec":
            bosses = list(d.get("bosses") or ["director"])
            titles = list(d.get("boss_titles") or [])
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
        if keep_upgrades:                       # "continue": upgrades bought before reaching that stage
            for k, v in self.saved_upgrades.items():
                if k in self.upgrades:
                    self.upgrades[k] = max(0, min(int(v), self.shop_items[k][3]))
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
        self.saved_upgrades = dict(self.upgrades)
        self.boss_ref = None
        self.wave_index = 0
        self.boss_index = 0
        self.mid_done = False
        self.wave_gap = 0.0
        self.boss_gap = 0.0
        self._reset_player(invincible=1.0)
        if self.stage["waves"] > 0:
            self.phase = "wave"
            self._begin_wave()
        else:
            self.phase = "boss"
            self.boss_gap = 1.0
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
            self.pending.append((rank, self.spawn_side))
            self.spawn_side ^= 1
        self.spawn_t = 0.0
        self.wave_gap = 1.0

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
            e.speed = float(r.get("boss_speed", r.get("speed", 100))) * mult["speed"]
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
            e.speed = float(r.get("speed", 60)) * mult["speed"]
            e.fire_rate = float(r.get("fire_rate", 0.2)) * (1.0 + 0.5 * (mult["speed"] - 1.0))
            e.stop_dist = self.rng.uniform(150, 300) if e.kind == "grunt" else self.rng.uniform(120, 220)
            e.fire_cd = self.rng.uniform(0.6, 1.5)
            e.jump_cd = self.rng.uniform(1.5, 3.5)
        e.hp = e.hp_max
        if r.get("hit_w") and r.get("hit_h"):          # explicit logic hitbox (custom sprite sheets)
            e.w = float(r["hit_w"])
            e.h = float(r["hit_h"])
        else:
            e.w = ENEMY_W * e.scale / 2
            e.h = ENEMY_H * e.scale / 2
        e.label = title or r.get("title", rank_key)
        e.facing = 1 if e.x < self.width / 2 else -1
        if self.anim_lens:
            e.hold_frame = max(0, int(self.anim_lens.get("death", 8)) - 1)
        return e

    # ------------------------------------------------------------ play update
    def _update_play(self, dt: float):
        self._update_player(dt)
        self._update_spawning(dt)
        for e in self.enemies:
            self._update_enemy(e, dt)
        self._update_bullets(dt)
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
        p.melee_t = max(0.0, p.melee_t - dt)
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
        rate = FIRE_RATE * float(c.get("fire_rate", 1.0)) * (1.0 + 0.2 * self.upgrades.get("rate", 0))
        w = p.weapon
        if w == "laser":
            edge = self.width + 40 if p.facing > 0 else -40
            cx = (gx + edge) / 2
            self.bullets.append(Bullet(cx, gun_y, abs(edge - gx), 3, 0.0, 0.0, "player",
                                       dmg=dmg + 1, pierce=True, kind="laser", ttl=0.08, mdmg=mdmg, element=el))
            rate *= 0.5
        elif w == "homing":
            self.bullets.append(Bullet(gx, gun_y, 10, 5, p.facing * MISSILE_SPEED, 0.0, "player",
                                       dmg=dmg + 2, pierce=False, kind="missile", ttl=3.0, mdmg=mdmg, element=el))
            p.ammo -= 1
            rate *= 0.7
            if p.ammo <= 0:
                p.weapon, p.ammo = "normal", 0
        elif w == "spread":
            for ang in (-0.26, 0.0, 0.26):
                if len(self.bullets) >= MAX_BULLETS:
                    break
                self.bullets.append(Bullet(gx, gun_y, 8, 4, p.facing * BULLET_SPEED * math.cos(ang),
                                           BULLET_SPEED * math.sin(ang), "player", dmg=dmg, pierce=pierce,
                                           mdmg=mdmg, element=el))
        else:
            self.bullets.append(Bullet(gx, gun_y, 8, 4, p.facing * BULLET_SPEED, 0.0, "player",
                                       dmg=dmg, pierce=pierce, mdmg=mdmg, element=el))
            if w == "rapid":
                rate *= 2.0
        p.fire_cd = 1.0 / max(0.5, rate)
        p.shoot_t = 0.25

    # ------------------------------------------------------------ melee / skill
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
        dmg = max(1, int(melee.get("damage", 4))) + self.upgrades.get("damage", 0)
        mdmg = self._magic_dmg(self.char)
        knock = float(melee.get("knockback", 260)) * 0.12
        for e in targets:
            d = 1 if e.x >= p.x else -1
            e.x += d * knock * (MELEE_KNOCK_BOSS if e.boss else 1.0)
            self._strike(e, dmg, mdmg, self.element_key)
        if targets:
            self._effect("text", p.x + p.facing * 20, p.y - PLAYER_H - 8, text=str(melee.get("text", "퍽!")))
        p.fire_cd = float(melee.get("cooldown", MELEE_CD))
        p.shoot_t = 0.2
        p.melee_t = 0.25

    def _use_skill(self):
        p = self.player
        storm = self.char.get("storm")
        if not storm or p.dead or p.skill_cd > 0 or len(self.zones) >= MAX_ZONES:
            return
        w = float(storm.get("width", 160))
        dur = float(storm.get("duration", 3.0))
        self.zones.append({"kind": "storm", "x": p.x + p.facing * (w / 2 + 10), "w": w, "t": dur, "ttl": dur,
                           "tick": 0.0, "every": float(storm.get("tick", 0.4)),
                           "dmg": max(1, int(storm.get("damage", 1))) + self.upgrades.get("damage", 0),
                           "mdmg": self._magic_dmg(self.char), "element": self.element_key})
        p.skill_cd = float(storm.get("cooldown", 8.0))
        p.shoot_t = 0.3
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
                for e in self.enemies:
                    if e.alive and _overlap(e.box(), box):
                        self._strike(e, z["dmg"], z.get("mdmg", 0), z.get("element"))
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

    def _shop_select(self):
        key = SHOP_ORDER[self.shop_index % len(SHOP_ORDER)]
        if key == "next":
            self._start_stage(self.stage_no + 1)
            return
        label, _base, _growth, mx = self.shop_items[key]
        if self.upgrades[key] >= mx:
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
            rows.append({"key": key, "label": label, "cost": cost, "level": lv, "max": mx,
                         "afford": lv < mx and self.score >= cost})
        return {"index": self.shop_index % len(SHOP_ORDER), "items": rows, "msg": self.shop_msg}

    def _drop_item(self, e: Enemy):
        if len(self.items) >= MAX_ITEMS:
            return
        if e.boss:
            kind = "life" if self.lives < self.lives_max + 2 else self.rng.choice(("laser", "homing", "spread"))
        else:
            chance = float(self.progression["drop_elite" if e.kind == "elite" else "drop_grunt"])
            if self.rng.random() >= chance:
                return
            # weighted: weapons common, 1UP rare
            kind = self.rng.choices(("laser", "homing", "spread", "rapid", "life"), (4, 4, 4, 4, 1))[0]
        x = min(self.width - 20, max(20, e.x))
        self.items.append(Item(x, e.y - 10, kind))

    def _give_item(self, kind: str):
        p = self.player
        if kind == "life":
            self.lives = min(self.lives_max + 2, self.lives + 1)
        elif kind == "homing":
            p.weapon, p.ammo, p.weapon_t = "homing", HOMING_AMMO, 0.0
        else:
            p.weapon, p.weapon_t, p.ammo = kind, WEAPON_TIME.get(kind, 10.0), 0
        self._effect("text", p.x, p.y - PLAYER_H - 12, text=ITEM_LABEL.get(kind, kind))

    def _update_items(self, dt: float):
        if not self.items:
            return
        p = self.player
        pbox = self._player_box()
        alive = []
        for it in self.items:
            it.t -= dt
            if not it.on_ground:
                it.vy += GRAVITY * dt
                it.y += it.vy * dt
                if it.y >= self.ground_y:
                    it.y = float(self.ground_y)
                    it.on_ground = True
                    if self._over_pit(it.x):
                        it.t = 0.0      # fell into a pit
            if it.t <= 0:
                continue
            if not p.dead and _overlap(it.box(), pbox):
                self._give_item(it.kind)
                continue
            alive.append(it)
        self.items = alive

    def _update_spawning(self, dt: float):
        if not self.pending:
            return
        self.spawn_t -= dt
        if self.spawn_t > 0 or len(self.enemies) >= MAX_ENEMIES:
            return
        rank, side = self.pending.pop(0)
        x = -30.0 if side == 0 else self.width + 30.0
        e = self._make_enemy(rank, x)
        self.enemies.append(e)
        self.spawn_t = float(self.wave_cfg["spawn_stagger"])

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
        dx = p.x - e.x
        dist = abs(dx)
        e.shoot_t = max(0.0, e.shoot_t - dt)
        brawler = e.pattern == "brawler"
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
        else:
            if brawler:
                self._brawler_ai(e, dt, dx, dist)
            elif e.hop_vx:
                e.vx = e.hop_vx
        # physics
        e.vy += GRAVITY * dt
        e.x += e.vx * dt
        e.y += e.vy * dt
        if e.y >= self.ground_y:
            e.y = float(self.ground_y)
            e.vy = 0.0
            if not e.on_ground:
                e.on_ground = True
                e.hop_vx = 0.0
                e.vx = 0.0
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

    def _grunt_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        p = self.player
        e.fire_cd -= dt
        if dist > e.stop_dist or not self._in_band(e):
            e.vx = e.facing * e.speed
            self._maybe_hop(e)
        else:
            e.vx = 0.0
        if e.fire_cd <= 0 and self._in_band(e) and not p.dead:
            prob = e.fire_rate * (1.0 if e.vx == 0 else 0.3)
            if self.rng.random() < prob * dt:
                self._enemy_shoot(e)
                e.fire_cd = 0.6

    def _elite_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        p = self.player
        e.fire_cd -= dt
        e.jump_cd -= dt
        if dist > e.stop_dist or not self._in_band(e):
            e.vx = e.facing * e.speed
            self._maybe_hop(e)
        else:
            e.vx = 0.0
        if e.burst_left > 0:
            e.burst_t -= dt
            if e.burst_t <= 0:
                self._enemy_shoot(e)
                e.burst_left -= 1
                e.burst_t = 0.12
        elif e.fire_cd <= 0 and self._in_band(e) and not p.dead:
            if self.rng.random() < e.fire_rate * dt:
                e.burst_left = 3
                e.burst_t = 0.0
                e.fire_cd = self.rng.uniform(1.2, 2.2)
        if e.jump_cd <= 0 and e.on_ground and dist < 420 and self._in_band(e):
            e.vy = -JUMP_VEL * 0.8
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
                    self.pending.append((self.rng.choice(grunts), side))
        if e.pattern == "chairman" and e.stamp_cd <= 0 and len(self.bullets) < MAX_BULLETS:
            e.stamp_cd = 2.5
            self.bullets.append(Bullet(p.x, -20.0, 20, 20, 0.0, STAMP_SPEED, "enemy", stamp=True))
            e.shoot_t = 0.3

    def _brawler_reach(self, e: Enemy) -> float:
        return e.w * 0.6 + 30.0

    def _brawler_ai(self, e: Enemy, dt: float, dx: float, dist: float):
        """Mid boss (mai/choi): walk in, chase, melee in reach, single aimed shot at range, occasional jump."""
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
            e.vy = -JUMP_VEL * 0.9
            e.on_ground = False
            e.hop_vx = e.facing * max(e.speed, 160.0)
            e.vx = e.hop_vx
            e.jump_cd = self.rng.uniform(3.0, 5.0)
            return
        e.vx = e.facing * e.speed
        self._maybe_hop(e)

    def _brawler_shot(self, e: Enemy):
        """attack2: one aimed projectile at 1.2x enemy bullet speed."""
        if len(self.bullets) >= MAX_BULLETS:
            return
        p = self.player
        gx, gy = e.x + e.facing * (e.w / 2), e.y - e.h * 0.6
        ang = math.atan2((p.y - PLAYER_H / 2) - gy, p.x - gx)
        spd = ENEMY_BULLET_SPEED * 1.2
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
        spd = ENEMY_BULLET_SPEED * 1.1
        for off in (-0.26, 0.0, 0.26):
            a = ang + off
            self.bullets.append(Bullet(gx, gy, 8, 4, math.cos(a) * spd, math.sin(a) * spd, "enemy"))
        e.shoot_t = 0.3

    def _update_bullets(self, dt: float):
        W, H = self.width, self.height
        for b in self.bullets:
            b.px, b.py = b.x, b.y
            if b.kind == "missile":
                self._steer_missile(b, dt)
            b.x += b.vx * dt
            b.y += b.vy * dt
            if b.ttl is not None:
                b.ttl -= dt
                if b.ttl <= 0:
                    b.dead = True
            if b.x < -50 or b.x > W + 50 or b.y < -80 or b.y > H + 50:
                b.dead = True
            elif (b.stamp or b.kind == "missile") and b.y >= self.ground_y:
                b.dead = True
                self._effect("spark", b.x, self.ground_y)

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
        b.vx, b.vy = math.cos(cur) * MISSILE_SPEED, math.sin(cur) * MISSILE_SPEED

    def _collide(self):
        p = self.player
        pbox = self._player_box()
        for b in self.bullets:
            if b.dead:
                continue
            bb = b.box()
            if b.owner == "player":
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
                if not p.dead and p.inv_t <= 0 and _overlap(bb, pbox):
                    b.dead = True
                    self._effect("spark", b.x, b.y)
                    self._hit_player()
        # boss dash contact
        if not p.dead and p.inv_t <= 0:
            for e in self.enemies:
                if e.alive and e.boss and e.dash_t > 0 and _overlap(e.box(), pbox):
                    self._hit_player()
                    break

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

    def _shield_max(self) -> int:
        return max(0, int(self.char.get("shield", 0) or 0) + self.upgrades.get("shield", 0))

    def _hit_player(self):
        """Enemy bullet / boss contact. A shield charge absorbs the hit before a life is lost."""
        p = self.player
        if p.dead or p.inv_t > 0:
            return
        if p.shield > 0:
            p.shield -= 1
            p.inv_t = SHIELD_INV
            self._effect("text", p.x, p.y - PLAYER_H - 12, text=f"실드 {p.shield}")
            return
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
        if self.lives <= 0:
            self.lives = 0
            if self.score > self.best:
                self.best = self.score
            self.bullets.clear()
            self._set_banner("GAME OVER")
            self._set_state("game_over")
            return
        # restart current wave / boss
        self.enemies.clear()
        self.bullets.clear()
        self.items.clear()
        self.effects.clear()
        self.zones.clear()
        self.boss_ref = None
        self._reset_player(invincible=2.0)
        if self.phase in ("boss", "midboss"):   # restart at the (mid) boss, not the whole stage
            self.boss_gap = 1.0
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
            if not self.pending and not self.enemies:
                self.wave_gap -= dt
                if self.wave_gap <= 0:
                    self.wave_index += 1
                    if self.wave_index < self.stage["waves"]:
                        if self._mid_boss_due():
                            self.phase = "midboss"
                            self.boss_gap = 1.0
                        else:
                            self._begin_wave()
                    else:
                        self.phase = "boss"
                        self.boss_index = 0
                        self.boss_gap = 1.0
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
                    self.boss_gap = 1.2
                else:
                    self._stage_clear()

    def _stage_clear(self):
        self.score += 500 * self.stage_no
        if self.score > self.best:
            self.best = self.score
        self.bullets.clear()
        self.enemies.clear()
        self.pending.clear()
        self.player.hold_frame = (max(0, int(self.anim_lens.get("victory", 6)) - 1) if self.anim_lens else None)
        self.player.set_anim("victory")
        banner = "STAGE CLEAR"
        for k in CHAR_KEYS:
            if self._char_locked(k) and self.stage_no >= self._unlock_stage(k):
                self.unlocked.add(k)
                banner = f"STAGE CLEAR · {self.chars[k]['name']} 해금!"
        self._set_banner(banner)
        self._set_state("stage_clear")

    # ------------------------------------------------------------ effects
    def _effect(self, kind: str, x: float, y: float, text: str | None = None):
        ttl = {"hit": 0.15, "spark": 0.25, "text": 0.8, "elem": 0.5}.get(kind, 0.2)
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
             "hud"}
ZONE_KEYS = {"kind", "x", "w", "h", "t", "ttl"}
PLAYER_KEYS = {"x", "y", "anim", "frame", "flip", "palette", "scale", "invincible", "visible", "element"}
ENEMY_KEYS = {"id", "x", "y", "anim", "frame", "flip", "palette", "scale", "label", "hp", "hp_max", "boss",
              "element", "mid"}
BULLET_KEYS = {"x", "y", "w", "h", "owner", "kind"}
ITEM_KEYS = {"x", "y", "kind", "t"}
EFFECT_KEYS = {"kind", "x", "y", "t", "text"}
EFFECT_KINDS = ("hit", "spark", "text", "elem")
HUD_KEYS = {"lives", "score", "best", "stage_no", "stage_name", "difficulty", "boss_hp", "boss_hp_max",
            "banner", "banner_t", "char_name", "select_index", "char_names", "continue_stage", "show_enemy_hp",
            "weapon", "weapon_label", "weapon_left", "shield", "shield_max", "melee_t", "skill_label", "skill_cd",
            "char_locked", "shop", "element", "element_name", "element_names", "element_index", "stats",
            "char_stats", "element_colors"}
BRAWLER_ANIMS = {"idle", "run", "attack", "attack2", "hurt", "death", "jump"}
ALL_KEYS = {"left", "right", "up", "down", "jump", "fire", "pause", "quit", "confirm", "sel_left", "sel_right",
            "skill"}


def _check_snapshot(s: dict):
    assert set(s.keys()) == SNAP_KEYS, set(s.keys()) ^ SNAP_KEYS
    assert set(s["player"].keys()) == PLAYER_KEYS, set(s["player"].keys()) ^ PLAYER_KEYS
    assert set(s["hud"].keys()) == HUD_KEYS, set(s["hud"].keys()) ^ HUD_KEYS
    for e in s["enemies"]:
        assert set(e.keys()) == ENEMY_KEYS, set(e.keys()) ^ ENEMY_KEYS
        assert e["scale"] in (2, 4, 6)
        assert e["element"] is None or e["element"] in ELEMENT_KEYS
        if e["mid"]:
            assert e["boss"] and e["anim"] in BRAWLER_ANIMS, e["anim"]
    assert s["player"]["element"] in ELEMENT_KEYS
    h = s["hud"]
    assert h["element"] == ELEMENT_KEYS[h["element_index"]] and len(h["element_names"]) == len(ELEMENT_KEYS)
    assert set(h["element_colors"]) == set(ELEMENT_KEYS) and len(h["char_stats"]) == len(CHAR_KEYS)
    for b in s["bullets"]:
        assert set(b.keys()) == BULLET_KEYS and b["owner"] in ("player", "enemy")
        assert b["kind"] in ("normal", "laser", "missile")
    for it in s["items"]:
        assert set(it.keys()) == ITEM_KEYS and it["kind"] in ITEM_KINDS
    assert len(s["items"]) <= MAX_ITEMS
    for z in s["zones"]:
        assert set(z.keys()) == ZONE_KEYS and z["kind"] == "storm"
    assert len(s["hud"]["char_locked"]) == len(CHAR_KEYS)
    assert (s["hud"]["shop"] is not None) == (s["state"] == "shop")
    for f in s["effects"]:
        assert set(f.keys()) == EFFECT_KEYS and f["kind"] in EFFECT_KINDS
    assert s["hud"]["difficulty"] in ("easy", "normal", "hard")
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
        assert st["bosses"] and st["difficulty"] in DIFF_ORDER
    assert w._build_stage(11)["name"] == "실장단" and len(w._build_stage(11)["bosses"]) == 3
    assert w._build_stage(14)["bosses"] == ["chairman"]
    assert w._build_stage(15)["difficulty"] == "easy" and w._build_stage(25)["difficulty"] == "normal"
    assert w._build_stage(35)["difficulty"] == "hard" and w._build_stage(10)["lab"] is True

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
            assert snap["hud"]["banner"] == "STAGE CLEAR"
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
    assert aw.player.weapon == "laser" and aw.snapshot()["hud"]["weapon"] == "laser"
    row = [aw._make_enemy("staff", aw.player.x + d) for d in (200, 400, 600)]
    aw.enemies.extend(row)
    aw.key_down("fire")
    _run(aw, 0.7)
    assert all(not e.alive for e in row), "laser must pierce the whole row"
    aw = _arena(13)
    aw.items.append(Item(aw.player.x, aw.player.y - 5, "homing"))
    _run(aw, 0.1)
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
    melee_dmg = int(config["characters"]["hyunki"]["melee"]["damage"]) + mw._magic_dmg(mw.char)
    assert near.hp == 20 - melee_dmg, near.hp
    assert not any(b.owner == "player" for b in mw.bullets), "melee must replace the shot"
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
    print("PASS 9: paper storm hits enemies inside, clears enemy bullets, cooldown holds")

    # 10) shop after stage clear: buy with score, next stage, upgrades survive 'continue'
    hw = World(stages, config, {"char": "jaehwi"}, 1920, 340, seed=35)
    hw._start_game(1)
    hw._stage_clear()
    _run(hw, 2.1)
    assert hw.state == "shop", hw.state
    cost = hw._shop_cost("damage")
    hw.score = cost
    hw.state_t = 1.0
    hw.key_down("confirm"); hw.key_up("confirm")
    assert hw.upgrades["damage"] == 1 and hw.score == 0, (hw.upgrades, hw.score)
    hw.key_down("confirm"); hw.key_up("confirm")
    assert hw.upgrades["damage"] == 1 and "부족" in hw.snapshot()["hud"]["shop"]["msg"]
    _check_snapshot(hw.snapshot())
    hw.key_down("left"); hw.key_up("left")      # wraps to "next"
    hw.key_down("confirm"); hw.key_up("confirm")
    assert hw.state == "play" and hw.stage_no == 2, (hw.state, hw.stage_no)
    sd = json.loads(json.dumps(hw.save_data()))
    assert sd["upgrades"]["damage"] == 1 and sd["stage"] == 2
    cw = World(stages, config, sd, 1920, 340, seed=36)
    _run(cw, 0.3); cw.key_down("confirm"); cw.key_up("confirm")
    assert cw.state == "continue"
    _run(cw, 0.3); cw.key_down("confirm"); cw.key_up("confirm")
    assert cw.state == "play" and cw.upgrades["damage"] == 1
    cw.bullets.clear()
    cw.key_down("fire"); cw.update(DT)
    assert any(b.owner == "player" and b.dmg == 2 for b in cw.bullets), "damage upgrade applies to shots"
    print(f"PASS 10: shop buys with score (damage cost {cost}), next stage, upgrades kept on continue")

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
            assert m.boss and m.pattern == "brawler" and m.palette in ("mai", "choi") and m.element in ELEMENT_KEYS
            assert m.w == stages["ranks"][m.rank]["hit_w"] and m.h == stages["ranks"][m.rank]["hit_h"]
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
    # brawler AI actually fights: melee contact or attack2 shot within a few seconds
    fw2 = World(stages, config, {"char": "jaehwi"}, 1600, 360, seed=54)
    fw2._start_game(2)
    fw2.enemies.clear(); fw2.pending.clear()
    fw2.phase = "midboss"; fw2.boss_gap = 0.0
    fw2._spawn_mid_boss()
    mb = fw2.boss_ref
    assert mb is not None and mb.mid
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

    dtms = (time.perf_counter() - t0) * 1000
    print(f"SELFTEST OK ({dtms:.0f} ms)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print("game.py: pure logic module. Run with --selftest.")
