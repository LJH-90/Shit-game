# -*- coding: utf-8 -*-
"""
economy.py — MolGam v1.9 economy contract (INTERFACES.md "추가(v1.9)" → "경제 (B)").

Pure logic: money drops, equipment (6 slots × 3 rarities × 20 levels), shop, random box,
gambling (upgrade / double-up / slots) and the Warehouse (24 slots + 6 equipped).
No tkinter, no global random — every function takes a `random.Random` as `rng`.
Every tunable number is a module constant; `configure(cfg)` overrides them from config.json.

    python economy.py --selftest   -> balance / behaviour checks, exit 0 on success.
"""
from __future__ import annotations

import sys

# ---------------------------------------------------------------- slots / rarity
SLOTS = ("hat", "gloves", "suit", "shoes", "weapon", "acc")
SLOT_LABEL = {"hat": "안전모", "gloves": "작업 장갑", "suit": "사신 정장",
              "shoes": "운동화", "weapon": "사무용 무기", "acc": "사원증"}
RARITY = ("normal", "rare", "unique")
RARITY_LABEL = {"normal": "일반", "rare": "레어", "unique": "유니크"}
RARITY_MULT = {"normal": 1.0, "rare": 1.8, "unique": 3.0}      # 고유 효과·스탯 배수
MAX_LEVEL = 20
SHOP_RARITY = {"normal": 0.90, "rare": 0.08, "unique": 0.02}   # 상점 목록
BOSS_RARITY = {"normal": 0.85, "rare": 0.12, "unique": 0.03}   # 보스 드롭
WORD_RARITY = {"normal": 0.40, "rare": 0.40, "unique": 0.20}   # 타자 단어 보상
BOX_RARITY = {"normal": 0.70, "rare": 0.22, "unique": 0.08}    # 랜덤박스
ROLL_RANGE = (0.7, 1.3)                                        # 스탯 ±30%
# 슬롯 고유 효과: (effect key, per level, flat). 실제 = (flat + per*level) * RARITY_MULT[rarity]
SLOT_EFFECT = {"hat": ("shield", 0.25, 1.0),
               "gloves": ("rate", 0.02, 0.0),
               "suit": ("magic", 0.25, 0.0),
               "shoes": ("speed", 0.01, 0.0),
               "weapon": ("damage", 0.2, 0.0),
               "acc": ("money", 0.02, 0.0)}
INT_EFFECTS = ("shield", "magic", "damage")                    # 반올림 정수 효과
JUMP_PER_SPEED = 0.6                                           # jump = speed * 0.6
EFFECT_KEYS = ("shield", "rate", "magic", "speed", "jump", "damage", "money", "str", "agi", "int")
STAT_KEYS = ("str", "agi", "int")
STAT_BASE_SUM = 2                                              # 스탯 합 = STAT_BASE_SUM + stage // STAT_STAGE_DIV
STAT_STAGE_DIV = 5
NAME_PREFIX = {"normal": ("낡은", "보통", "튼튼한"),           # roll 3분위(하/중/상)
               "rare": ("정교한", "특제", "명품"),
               "unique": ("전설의", "회장님의", "사신의")}

# ---------------------------------------------------------------- prices
UPGRADE_BASE = 300
UPGRADE_GROWTH = 1.12
RARITY_COST = {"normal": 1.0, "rare": 1.5, "unique": 2.5}
PRICE_BASE = 600
PRICE_PER_LEVEL = 120
RARITY_PRICE = {"normal": 1, "rare": 4, "unique": 15}
PRICE_STAGE_GROWTH = 0.06
SELL_RATIO = 0.4
SHOP_LEVEL_CAP = 5
SHOP_LEVEL_STAGE_DIV = 3
BOX_PRICE_BASE = 900

# ---------------------------------------------------------------- random box
BOX_OUTCOME = {"equip": 0.60, "item": 0.25, "money": 0.10, "dud": 0.05}
BOX_MONEY_RANGE = (0.5, 3.0)                                   # × BOX_PRICE(stage)
BOX_ITEM_WEIGHTS = {"laser": 10, "homing": 10, "spread": 10, "rapid": 10, "bomb": 8,
                    "coffee": 8, "decoy": 8, "drone": 8, "dog": 8, "life": 2}   # 1UP 가중 낮음
BOX_DUD_TEXT = "꽝 · 사탕 하나"

# ---------------------------------------------------------------- gambling
GAMBLE_UPGRADE_COST_MULT = 1.5
GAMBLE_UPGRADE_ODDS = {"up": 0.60, "same": 0.30, "down": 0.10}
GAMBLE_UPGRADE_UP = 2
GAMBLE_UPGRADE_DOWN = 3
DOUBLE_WIN_CHANCE = 0.5
DOUBLE_MAX_MULT = 8
SLOT_SYMBOLS = ("₩", "★", "◆", "♥", "7")
SLOT_WEIGHTS = {"₩": 22, "★": 18, "◆": 22, "♥": 22, "7": 16}   # 릴 1개당 가중치 (기댓값 ≈ 0.82*bet)
SLOT_PAYOUT = {"7": 30, "₩": 10, "◆": 5, "♥": 5, "★": 0}      # 3개 동일 시 bet 배수 (★ = 레어 장비)
SLOT_PAIR_PAYOUT = 1                                           # 2개 동일 = bet 반환

# ---------------------------------------------------------------- money drop
MONEY_KIND = {"grunt": (20, 40), "elite": (60, 100), "mid": (300, 300),
              "boss": (800, 800), "word": (500, 500)}
MONEY_STAGE_GROWTH = 0.05      # × (1 + growth*(stage-1)); 0.05 → 보통 50스테이지 ≈ 21.8만 ₩


def configure(cfg):
    """config.json 의 같은 이름 키로 모듈 상수를 덮어쓴다(dict 상수는 키 병합, 모르는 키 무시)."""
    g = globals()
    for key, val in (cfg or {}).items():
        if key not in g or key.startswith("_") or not key.isupper():
            continue
        cur = g[key]
        if isinstance(cur, dict) and isinstance(val, dict):
            merged = dict(cur)
            for k, v in val.items():
                merged[k] = tuple(v) if isinstance(cur.get(k), tuple) and isinstance(v, list) else v
            g[key] = merged
        elif isinstance(cur, tuple) and isinstance(val, (list, tuple)):
            g[key] = tuple(val)
        elif isinstance(cur, (int, float)) and isinstance(val, (int, float)) and not isinstance(val, bool):
            g[key] = type(cur)(val) if isinstance(cur, float) else val
        elif isinstance(cur, str) and isinstance(val, str):
            g[key] = val


# ---------------------------------------------------------------- helpers
def _weighted(rng, table):
    """dict {key: weight} → 가중 랜덤 key."""
    keys = list(table)
    total = float(sum(table[k] for k in keys))
    x = rng.random() * total
    for k in keys:
        x -= table[k]
        if x < 0:
            return k
    return keys[-1]


def _roll_stats(rng, stage, roll, rarity):
    """스탯 합 = 2 + stage//5 를 셋 중 랜덤 분배 → × roll × RARITY_MULT, 반올림."""
    total = STAT_BASE_SUM + max(0, int(stage)) // STAT_STAGE_DIV
    raw = {k: 0 for k in STAT_KEYS}
    for _ in range(total):
        raw[rng.choice(STAT_KEYS)] += 1
    mult = roll * RARITY_MULT.get(rarity, 1.0)
    return {k: int(round(raw[k] * mult)) for k in STAT_KEYS}


def _prefix(rarity, roll):
    lo, hi = ROLL_RANGE
    span = (hi - lo) / 3.0 if hi > lo else 1.0
    idx = min(2, max(0, int((roll - lo) / span)))
    return NAME_PREFIX.get(rarity, NAME_PREFIX["normal"])[idx]


def make_equipment(rng, slot, rarity, level=0, stage=1):
    """장비 dict 생성. 이름 = <접두어> <슬롯라벨>, 접두어는 등급·roll 3분위로 결정(rng 에 대해 결정적)."""
    if slot not in SLOTS:
        slot = SLOTS[0]
    if rarity not in RARITY:
        rarity = "normal"
    level = max(0, min(MAX_LEVEL, int(level)))
    eid = "%012x" % rng.getrandbits(48)
    roll = round(rng.uniform(*ROLL_RANGE), 3)
    return {"id": eid, "slot": slot, "rarity": rarity, "level": level,
            "name": "%s %s" % (_prefix(rarity, roll), SLOT_LABEL[slot]),
            "roll": roll, "stats": _roll_stats(rng, stage, roll, rarity)}


def _zero_effect():
    return {k: 0 for k in EFFECT_KEYS}


def equip_effect(eq):
    """장비 1개의 효과. 모든 EFFECT_KEYS 존재, 장비 없으면 0."""
    out = _zero_effect()
    if not isinstance(eq, dict):
        return out
    slot = eq.get("slot")
    if slot in SLOT_EFFECT:
        key, per, flat = SLOT_EFFECT[slot]
        level = max(0, min(MAX_LEVEL, int(eq.get("level", 0) or 0)))
        mult = RARITY_MULT.get(eq.get("rarity"), 1.0)
        val = (flat + per * level) * mult
        out[key] = int(round(val)) if key in INT_EFFECTS else val
    out["jump"] = out["speed"] * JUMP_PER_SPEED
    stats = eq.get("stats") or {}
    for k in STAT_KEYS:
        try:
            out[k] = int(round(float(stats.get(k, 0) or 0)))
        except (TypeError, ValueError):
            out[k] = 0
    return out


def total_effect(equipped):
    """슬롯 합산(equipped = {slot: eq|None}). 키 전부 존재."""
    out = _zero_effect()
    for eq in (equipped or {}).values():
        if not eq:
            continue
        e = equip_effect(eq)
        for k in EFFECT_KEYS:
            out[k] += e[k]
    for k in INT_EFFECTS + STAT_KEYS:
        out[k] = int(round(out[k]))
    out["jump"] = out["speed"] * JUMP_PER_SPEED
    return out


# ---------------------------------------------------------------- prices
def upgrade_cost(eq):
    """300 * 1.12**level * RARITY_COST; 레벨 20 이면 0(불가)."""
    level = int(eq.get("level", 0) or 0)
    if level >= MAX_LEVEL:
        return 0
    return int(UPGRADE_BASE * (UPGRADE_GROWTH ** level) * RARITY_COST.get(eq.get("rarity"), 1.0))


def buy_price(eq, stage):
    """(600 * RARITY_PRICE + 120*level) * (1 + 0.06*(stage-1))."""
    level = int(eq.get("level", 0) or 0)
    base = PRICE_BASE * RARITY_PRICE.get(eq.get("rarity"), 1) + PRICE_PER_LEVEL * level
    return int(base * (1 + PRICE_STAGE_GROWTH * (max(1, int(stage)) - 1)))


def sell_price(eq, stage):
    return int(buy_price(eq, stage) * SELL_RATIO)


def roll_rarity(rng, table):
    return _weighted(rng, table)


def make_shop_stock(rng, stage, n=10):
    """상점 목록 n개: SHOP_RARITY, 슬롯 랜덤, level 0~min(5, stage//3)."""
    stage = max(1, int(stage))
    lv_max = min(SHOP_LEVEL_CAP, stage // SHOP_LEVEL_STAGE_DIV)
    return [make_equipment(rng, rng.choice(SLOTS), roll_rarity(rng, SHOP_RARITY),
                           rng.randint(0, lv_max), stage) for _ in range(int(n))]


def BOX_PRICE(stage):
    return int(BOX_PRICE_BASE * (1 + PRICE_STAGE_GROWTH * (max(1, int(stage)) - 1)))


def _box_item(rng):
    return _weighted(rng, BOX_ITEM_WEIGHTS)


def open_box(rng, stage):
    """랜덤박스: 60% equip(BOX_RARITY) / 25% item / 10% money / 5% dud."""
    kind = _weighted(rng, BOX_OUTCOME)
    out = {"kind": kind, "equip": None, "item": None, "money": 0, "text": ""}
    if kind == "equip":
        eq = make_equipment(rng, rng.choice(SLOTS), roll_rarity(rng, BOX_RARITY), 0, stage)
        out["equip"] = eq
        out["text"] = "%s %s 획득!" % (RARITY_LABEL[eq["rarity"]], eq["name"])
    elif kind == "item":
        out["item"] = _box_item(rng)
        out["text"] = "아이템 획득: %s" % out["item"]
    elif kind == "money":
        out["money"] = int(BOX_PRICE(stage) * rng.uniform(*BOX_MONEY_RANGE))
        out["text"] = "+%d ₩" % out["money"]
    else:
        out["text"] = BOX_DUD_TEXT
    return out


# ---------------------------------------------------------------- gambling
def gamble_upgrade(rng, eq, money):
    """강화 도박: cost = upgrade_cost*1.5; 60% +2lv / 30% 유지 / 10% -3lv(유니크는 유지). 반환 (eq, 잔액, 문구)."""
    eq = dict(eq)
    level = int(eq.get("level", 0) or 0)
    if level >= MAX_LEVEL:
        return eq, money, "이미 최대 레벨(%d)입니다" % MAX_LEVEL
    cost = int(upgrade_cost(eq) * GAMBLE_UPGRADE_COST_MULT)
    if money < cost:
        return eq, money, "돈이 부족합니다 (%d ₩ 필요)" % cost
    money -= cost
    res = _weighted(rng, GAMBLE_UPGRADE_ODDS)
    if res == "up":
        new = min(MAX_LEVEL, level + GAMBLE_UPGRADE_UP)
        text = "대성공! +%d 레벨 (Lv %d)" % (new - level, new)
    elif res == "down":
        if eq.get("rarity") == "unique":
            new, text = level, "유니크의 가호 · 변화 없음 (Lv %d)" % level
        else:
            new = max(0, level - GAMBLE_UPGRADE_DOWN)
            text = "실패... -%d 레벨 (Lv %d)" % (level - new, new)
    else:
        new, text = level, "변화 없음 (Lv %d)" % level
    eq["level"] = new
    return eq, money, text


def gamble_double(rng, stake, streak):
    """더블업: 50% 성공 → stake * min(2**(streak+1), 8); 실패 → 0. streak = 이전 연속 성공 횟수."""
    if rng.random() < DOUBLE_WIN_CHANCE:
        mult = min(DOUBLE_MAX_MULT, 2 ** (max(0, int(streak)) + 1))
        return True, int(stake) * mult
    return False, 0


def _spin(rng):
    return [_weighted(rng, SLOT_WEIGHTS) for _ in range(3)]


def gamble_slots(rng, bet, stage):
    """슬롯: 777 = bet*30 + 유니크 / ★★★ = 레어 장비 / ₩₩₩ = bet*10 / ◆◆◆·♥♥♥ = bet*5 / 2개 동일 = bet (7 페어는 아이템도)."""
    bet = max(0, int(bet))
    reels = _spin(rng)
    out = {"reels": reels, "payout": 0, "prize": None, "text": " ".join(reels)}
    a, b, c = reels
    if a == b == c:
        out["payout"] = bet * SLOT_PAYOUT.get(a, 0)
        if a == "7":
            eq = make_equipment(rng, rng.choice(SLOTS), "unique", 0, stage)
            out["prize"] = {"kind": "equip", "equip": eq}
            out["text"] = "잭팟!!! +%d ₩ · %s" % (out["payout"], eq["name"])
        elif a == "★":
            eq = make_equipment(rng, rng.choice(SLOTS), "rare", 0, stage)
            out["prize"] = {"kind": "equip", "equip": eq}
            out["text"] = "★★★ 레어 장비: %s" % eq["name"]
        else:
            out["text"] = "%s 3개! +%d ₩" % (a, out["payout"])
    elif a == b or b == c or a == c:
        out["payout"] = bet * SLOT_PAIR_PAYOUT
        pair = a if (a == b or a == c) else b
        if pair == "7":
            out["prize"] = {"kind": "item", "item": _box_item(rng)}
            out["text"] = "7 페어 · 배팅 반환 + 아이템 %s" % out["prize"]["item"]
        else:
            out["text"] = "%s 페어 · 배팅 반환" % pair
    else:
        out["text"] = "꽝"
    return out


# ---------------------------------------------------------------- warehouse
def _valid_eq(eq):
    """세이브에서 읽은 장비가 쓸 만한지: dict 이고 slot 이 SLOTS 에 있어야 한다. 빠진 필드는 채운다."""
    if not isinstance(eq, dict) or eq.get("slot") not in SLOTS:
        return None
    out = dict(eq)
    if out.get("rarity") not in RARITY:
        out["rarity"] = "normal"
    try:
        out["level"] = max(0, min(MAX_LEVEL, int(out.get("level", 0) or 0)))
    except (TypeError, ValueError):
        out["level"] = 0
    try:
        out["roll"] = float(out.get("roll", 1.0) or 1.0)
    except (TypeError, ValueError):
        out["roll"] = 1.0
    stats = out.get("stats") if isinstance(out.get("stats"), dict) else {}
    clean = {}
    for k in STAT_KEYS:
        try:
            clean[k] = int(stats.get(k, 0) or 0)
        except (TypeError, ValueError):
            clean[k] = 0
    out["stats"] = clean
    out["id"] = str(out.get("id") or "")
    out["name"] = str(out.get("name") or "%s %s" % (_prefix(out["rarity"], out["roll"]), SLOT_LABEL[out["slot"]]))
    return out


class Warehouse:
    """창고 24칸 + 장착 6슬롯. to_save() ↔ __init__(data) 라운드트립."""
    CAP = 24

    def __init__(self, data=None):
        self.items = []
        self.equipped = {s: None for s in SLOTS}
        if not isinstance(data, dict):
            return
        for eq in (data.get("items") or []) if isinstance(data.get("items"), list) else []:
            v = _valid_eq(eq)
            if v is not None and len(self.items) < self.CAP:
                self.items.append(v)
        eqd = data.get("equipped")
        if isinstance(eqd, dict):
            for slot, eq in eqd.items():
                v = _valid_eq(eq)
                if v is not None and slot in SLOTS and v["slot"] == slot:
                    self.equipped[slot] = v

    def add(self, eq):
        """꽉 차면 False."""
        if len(self.items) >= self.CAP or not isinstance(eq, dict):
            return False
        self.items.append(eq)
        return True

    def equip(self, idx):
        """창고 idx 를 장착; 기존 장착품은 같은 자리로 돌아간다. 실패 None."""
        if not (0 <= idx < len(self.items)):
            return None
        eq = self.items[idx]
        slot = eq.get("slot")
        if slot not in SLOTS:
            return None
        old = self.equipped.get(slot)
        if old is not None:
            self.items[idx] = old
        else:
            self.items.pop(idx)
        self.equipped[slot] = eq
        return eq

    def unequip(self, slot):
        eq = self.equipped.get(slot)
        if eq is None or len(self.items) >= self.CAP:
            return False
        self.items.append(eq)
        self.equipped[slot] = None
        return True

    def remove(self, idx):
        return self.items.pop(idx)

    def effect(self):
        return total_effect(self.equipped)

    def to_save(self):
        return {"items": [dict(e) for e in self.items],
                "equipped": {s: (dict(self.equipped[s]) if self.equipped.get(s) else None) for s in SLOTS}}


# ---------------------------------------------------------------- money
def money_drop(rng, kind, stage, diff_mult, acc_bonus):
    """kind grunt 20~40 / elite 60~100 / mid 300 / boss 800 / word 500 ; × (1+growth*(stage-1)) × diff × (1+acc)."""
    lo, hi = MONEY_KIND.get(kind, MONEY_KIND["grunt"])
    base = rng.randint(int(lo), int(hi)) if hi > lo else lo
    stage_mult = 1 + MONEY_STAGE_GROWTH * (max(1, int(stage)) - 1)
    return int(round(base * stage_mult * float(diff_mult) * (1 + float(acc_bonus))))


# ---------------------------------------------------------------- selftest
def _selftest():
    import random
    R = random.Random

    # (a) income of a normal run, 50 stages
    rng = R(1)
    income = 0
    for s in range(1, 51):
        for _ in range(18):
            income += money_drop(rng, "grunt", s, 1.0, 0.0)
        for _ in range(4):
            income += money_drop(rng, "elite", s, 1.0, 0.0)
        if s >= 2:
            income += money_drop(rng, "mid", s, 1.0, 0.0)
        income += money_drop(rng, "boss", s, 1.0, 0.0)
    print("income 50 stages (normal): %d (target 200000 +/-25%%)" % income)
    assert 150000 <= income <= 250000, income

    # (b) six normal items 0 -> 20
    cost = 0
    for slot in SLOTS:
        eq = {"slot": slot, "rarity": "normal", "level": 0}
        for lv in range(MAX_LEVEL):
            eq["level"] = lv
            c = upgrade_cost(eq)
            assert c > 0
            cost += c
        eq["level"] = MAX_LEVEL
        assert upgrade_cost(eq) == 0
    print("upgrade 6 x normal 0->20: %d (target 130000 +/-25%%)" % cost)
    assert 97500 <= cost <= 162500, cost

    # (c) rarity tables
    for table in (SHOP_RARITY, BOSS_RARITY, BOX_RARITY, WORD_RARITY):
        rng = R(2)
        n = 20000
        cnt = {k: 0 for k in RARITY}
        for _ in range(n):
            cnt[roll_rarity(rng, table)] += 1
        for k in RARITY:
            assert abs(cnt[k] / n - table[k]) <= 0.015, (table, cnt)

    # (d) shop stock
    rng = R(3)
    for stage in (1, 7, 30):
        stock = make_shop_stock(rng, stage, 10)
        assert len(stock) == 10
        for eq in stock:
            assert eq["slot"] in SLOTS and eq["rarity"] in RARITY
            assert 0 <= eq["level"] <= min(SHOP_LEVEL_CAP, stage // SHOP_LEVEL_STAGE_DIV)
            assert eq["name"].endswith(SLOT_LABEL[eq["slot"]]) and eq["name"].split(" ", 1)[0] in NAME_PREFIX[eq["rarity"]]
            assert ROLL_RANGE[0] <= eq["roll"] <= ROLL_RANGE[1]
            assert set(eq["stats"]) == set(STAT_KEYS)
            assert buy_price(eq, stage) > sell_price(eq, stage) > 0
    assert make_shop_stock(R(3), 5, 4) == make_shop_stock(R(3), 5, 4)   # deterministic

    # (e) box outcomes
    rng = R(4)
    n = 20000
    cnt = {k: 0 for k in BOX_OUTCOME}
    for _ in range(n):
        r = open_box(rng, 10)
        cnt[r["kind"]] += 1
        if r["kind"] == "equip":
            assert r["equip"]["slot"] in SLOTS
        elif r["kind"] == "item":
            assert r["item"] in BOX_ITEM_WEIGHTS
        elif r["kind"] == "money":
            assert BOX_PRICE(10) * 0.5 <= r["money"] <= BOX_PRICE(10) * 3.0
        else:
            assert r["text"] == BOX_DUD_TEXT
    for k in BOX_OUTCOME:
        assert abs(cnt[k] / n - BOX_OUTCOME[k]) <= 0.015, cnt

    # (f) gamble_upgrade
    rng = R(5)
    for rarity in RARITY:
        delta = 0
        n = 5000
        for _ in range(n):
            lv = rng.randint(0, MAX_LEVEL)
            eq = make_equipment(rng, "hat", rarity, lv, 1)
            new, left, text = gamble_upgrade(rng, eq, 10 ** 9)
            assert 0 <= new["level"] <= MAX_LEVEL
            if lv >= MAX_LEVEL:
                assert new["level"] == lv and left == 10 ** 9
                continue
            assert left == 10 ** 9 - int(upgrade_cost(eq) * GAMBLE_UPGRADE_COST_MULT)
            if rarity == "unique":
                assert new["level"] >= lv
            delta += new["level"] - lv
        assert delta > 0, (rarity, delta)
    eq = make_equipment(R(6), "hat", "normal", 3, 1)
    same, left, text = gamble_upgrade(R(6), eq, 0)
    assert same["level"] == 3 and left == 0 and "부족" in text

    # (g) double-up cap
    rng = R(7)
    seen_win = seen_lose = False
    for streak in range(0, 8):
        for _ in range(200):
            ok, pay = gamble_double(rng, 100, streak)
            if ok:
                seen_win = True
                assert pay == 100 * min(DOUBLE_MAX_MULT, 2 ** (streak + 1)) and pay <= 800
            else:
                seen_lose = True
                assert pay == 0
    assert seen_win and seen_lose

    # (h) slots EV
    rng = R(8)
    n = 50000
    total = 0
    prizes = {"item": 0, "equip": 0}
    for _ in range(n):
        r = gamble_slots(rng, 100, 10)
        assert len(r["reels"]) == 3 and all(s in SLOT_SYMBOLS for s in r["reels"])
        total += r["payout"]
        if r["prize"]:
            prizes[r["prize"]["kind"]] += 1
    ev = total / n / 100.0
    print("slots EV: %.3f x bet (prizes item=%d equip=%d)" % (ev, prizes["item"], prizes["equip"]))
    assert 0.75 <= ev <= 0.95, ev
    assert prizes["item"] > 0 and prizes["equip"] > 0

    # (i) warehouse
    rng = R(9)
    w = Warehouse(None)
    assert set(w.equipped) == set(SLOTS)
    for i in range(Warehouse.CAP):
        assert w.add(make_equipment(rng, SLOTS[i % 6], "normal", i % 21, 1))
    assert not w.add(make_equipment(rng, "hat", "normal", 0, 1))
    assert len(w.items) == 24
    first = w.items[0]
    assert w.equip(0) is first and w.equipped["hat"] is first and len(w.items) == 23
    assert w.add(make_equipment(rng, "suit", "rare", 0, 1)) and len(w.items) == 24
    assert not w.unequip("hat")                       # full: cannot unequip
    w.remove(23)
    second = w.items[5]                               # another hat (index 6 originally)
    assert second["slot"] == "hat"
    assert w.equip(5) is second and w.items[5] is first and len(w.items) == 23   # swap in place
    assert w.unequip("gloves") is False
    w.remove(0)
    assert len(w.items) == 22 and w.unequip("hat") and w.equipped["hat"] is None and w.items[-1] is second
    assert w.equip(99) is None
    eff = w.effect()
    assert set(eff) == set(EFFECT_KEYS)
    save = w.to_save()
    assert Warehouse(save).to_save() == save
    bad = Warehouse({"items": [None, 3, {"slot": "nope"}, {"slot": "suit"}], "equipped": {"zzz": {"slot": "hat"}, "hat": {"slot": "gloves"}, "acc": {"slot": "acc", "level": "x"}}})
    assert len(bad.items) == 1 and bad.equipped["hat"] is None and bad.equipped["acc"]["level"] == 0
    assert Warehouse(bad.to_save()).to_save() == bad.to_save()

    # (j) unique = 3x normal
    for slot in SLOTS:
        for lv in (0, 7, 20):
            a = equip_effect(make_equipment(R(10), slot, "normal", lv, 40))
            b = equip_effect(make_equipment(R(10), slot, "unique", lv, 40))
            for k in EFFECT_KEYS:
                if k in INT_EFFECTS or k in STAT_KEYS:
                    assert abs(b[k] - 3 * a[k]) <= 2, (slot, lv, k, a[k], b[k])
                else:
                    assert abs(b[k] - 3 * a[k]) < 1e-9, (slot, lv, k)
    z = total_effect({s: None for s in SLOTS})
    assert set(z) == set(EFFECT_KEYS) and all(v == 0 for v in z.values())
    sh = equip_effect({"slot": "shoes", "rarity": "normal", "level": 10})
    assert abs(sh["speed"] - 0.10) < 1e-9 and abs(sh["jump"] - 0.06) < 1e-9

    # configure: override & ignore unknown
    old = MONEY_STAGE_GROWTH
    configure({"MONEY_STAGE_GROWTH": 0.5, "RARITY_MULT": {"rare": 2.0}, "NOT_A_KEY": 1, "ROLL_RANGE": [0.5, 1.5]})
    assert MONEY_STAGE_GROWTH == 0.5 and RARITY_MULT["rare"] == 2.0 and RARITY_MULT["unique"] == 3.0 and ROLL_RANGE == (0.5, 1.5)
    configure({"MONEY_STAGE_GROWTH": old, "RARITY_MULT": {"rare": 1.8}, "ROLL_RANGE": [0.7, 1.3]})
    print("economy selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    print(__doc__)
