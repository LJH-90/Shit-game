# -*- coding: utf-8 -*-
"""
economy.py — MolGam v1.9 economy contract (INTERFACES.md "추가(v1.9)" → "경제 (B)").

Pure logic: money drops, equipment (6 slots × 3 rarities × 20 levels), shop, random box,
gambling (upgrade / double-up / slots) and the Warehouse (24 slots + 6 equipped).
v2.0: deterministic paid enhance (enhance_cost / enhance, cost × ENHANCE_RARITY_COST), gear stat rolls
scaled by RARITY_STAT_MULT (slot effects keep RARITY_MULT), rare+ perks (PERKS table: rare 1 / unique 2 keys
per item from the slot's pool, rolled AFTER stats so ids/rolls/stats of existing seeds are unchanged; active set
= {key: rank} with MAX stacking; magnitudes are rank-only; never merged into total_effect).
No tkinter, no global random — every function takes a `random.Random` as `rng` (the one exception: _valid_eq
seeds a private random.Random from the item id to re-roll perks for pre-perk saves, identical on every load).
Every tunable number is a module constant; `configure(cfg)` overrides them from config.json (nested dicts merge
member by member, so {"PERKS": {"magnet": {"value": {"rare": 200}}}} retunes one number).

    python economy.py --selftest   -> balance / behaviour checks, exit 0 on success.
"""
from __future__ import annotations

import random
import sys

# ---------------------------------------------------------------- slots / rarity
SLOTS = ("hat", "gloves", "suit", "shoes", "weapon", "acc")
SLOT_LABEL = {"hat": "안전모", "gloves": "작업 장갑", "suit": "사신 정장",
              "shoes": "운동화", "weapon": "사무용 무기", "acc": "사원증"}
RARITY = ("normal", "rare", "unique")
RARITY_LABEL = {"normal": "일반", "rare": "레어", "unique": "유니크"}
RARITY_MULT = {"normal": 1.0, "rare": 1.8, "unique": 3.0}      # 슬롯 고유 효과 배수 (스탯은 RARITY_STAT_MULT)
RARITY_STAT_MULT = {"normal": 1.0, "rare": 1.5, "unique": 2.0}  # 스탯 롤 배수 (_roll_stats 전용)
MAX_LEVEL = 20
SHOP_RARITY = {"normal": 0.90, "rare": 0.08, "unique": 0.02}   # 상점 목록
BOSS_RARITY = {"normal": 0.85, "rare": 0.12, "unique": 0.03}   # 보스 드롭
WORD_RARITY = {"normal": 0.60, "rare": 0.32, "unique": 0.08}   # 타자 단어 보상
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
STAT_BASE_SUM = 1                                              # 스탯 합 = STAT_BASE_SUM + stage // STAT_STAGE_DIV
STAT_STAGE_DIV = 4
NAME_PREFIX = {"normal": ("낡은", "보통", "튼튼한"),           # roll 3분위(하/중/상)
               "rare": ("정교한", "특제", "명품"),
               "unique": ("전설의", "회장님의", "사신의")}

# ---------------------------------------------------------------- prices
UPGRADE_BASE = 300
UPGRADE_GROWTH = 1.12
RARITY_COST = {"normal": 1.0, "rare": 1.5, "unique": 2.5}      # 도박(gamble_upgrade) 기준
ENHANCE_RARITY_COST = {"normal": 1.6, "rare": 2.6, "unique": 4.5}   # 확정 강화(enhance) 배수: 등급↑ = 비용↑
ENHANCE_PERK_DISCOUNT = 0.8                                     # 'haggler' 퍼크 장착 시 강화 비용 ×0.8
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
GAMBLE_UPGRADE_DOWN_UNIQUE = 1                                 # 유니크 실패 시 -1 (확정 강화가 무의미해지지 않게)
DOUBLE_WIN_CHANCE = 0.5
DOUBLE_MAX_MULT = 8
SLOT_SYMBOLS = ("₩", "★", "◆", "♥", "7")
SLOT_WEIGHTS = {"₩": 22, "★": 18, "◆": 22, "♥": 22, "7": 16}   # 릴 1개당 가중치 (기댓값 ≈ 0.82*bet)
SLOT_PAYOUT = {"7": 30, "₩": 10, "◆": 5, "♥": 5, "★": 0}      # 3개 동일 시 bet 배수 (★ = 레어 장비)
SLOT_PAIR_PAYOUT = 1                                           # 2개 동일 = bet 반환

# ---------------------------------------------------------------- money drop
MONEY_KIND = {"grunt": (20, 40), "elite": (60, 100), "mid": (250, 250),
              "boss": (600, 600), "word": (400, 400)}
MONEY_STAGE_GROWTH = 0.05      # × (1 + growth*(stage-1)); 0.05 → 보통 50스테이지 ≈ 19만 ₩

# ---------------------------------------------------------------- perks (rare+ convenience skills)
# key -> {"label": 라벨(<= 6자, 카드/HUD 칩), "slots": 롤되는 슬롯 풀(<= 2), "min": 최소 등급, "value": {등급: 크기},
#         "ui": {등급: 표시 문구(숫자 치환 완료 — 렌더러는 포맷하지 않는다)}, "desc": 효과 설명}.
# 크기는 등급(rank)으로만 정해지고 레벨과 무관; 1/2 = 단계(bool 계열), 9999 = 밴드 전체, 99 = 완전 관통.
# 슬롯 풀(각 4키): hat 실드/생존 · gloves 연사/아이템 · suit 궁극/생존 · shoes 이동 · weapon 피해 · acc 돈/편의.
# 게임 쪽 훅은 game.py(_perk / _perk_mult); economy 가 직접 쓰는 건 haggler(enhance_cost) 뿐. 표가 비면 롤은 [] (rng 소비 없음).
PERKS = {
    "magnet": {"label": "코인 자석", "slots": ("acc", "shoes"), "min": "rare",
             "value": {"rare": 160, "unique": 9999},
             "ui": {"rare": "코인 자석 160px", "unique": "코인 자석 전체"},
             "desc": "FLAGSHIP 편의 퍽. 기본 룰(코인은 죽은 자리에 남고 COIN_PICK_R 26 px 안에서 걸어가 줍는다, COIN_TTL 20 s)을 되돌린다: 반경 안의 코인이 플레이어에게 날아온다. 반경 밖 코인은 바닥 룰 그대로."},
    "double_jump": {"label": "더블 점프", "slots": ("shoes",), "min": "rare",
                  "value": {"rare": 1, "unique": 2},
                  "ui": {"rare": "공중 점프 1회", "unique": "공중 점프 2회"},
                  "desc": "공중에서 추가 점프. 발판 이동·구덩이 회피가 쉬워지고 masked(hip)/jaehwi(knife) 점프인 근접 빌드의 핵심. 착지(지면·발판)마다 충전, 발판 드롭(drop_t > 0) 중엔 불가."},
    "ult_time": {"label": "궁극 지속", "slots": ("suit",), "min": "rare",
               "value": {"rare": 1.5, "unique": 2.0},
               "ui": {"rare": "궁극기 지속 x1.5", "unique": "궁극기 지속 x2.0"},
               "desc": "궁극기(C) 존 지속시간 배수 (dongil 서류 스톰 3 s, hyunki 해머 강타 1.2 s). 초상화 버스트 ULT_T 1 s 는 그대로. storm 이 없는 jaehwi/masked 에게는 롤되지 않는다(규칙 7)."},
    "ult_haste": {"label": "궁극 쿨감", "slots": ("suit",), "min": "rare",
                "value": {"rare": 0.75, "unique": 0.6},
                "ui": {"rare": "궁극기 쿨 x0.75", "unique": "궁극기 쿨 x0.6"},
                "desc": "궁극기(C) 쿨다운 단축 (dongil 8 s, hyunki 10 s). ult_time 과 함께 '스톰 상시 유지' 빌드; 업타임 플로어(dur+1 s)가 100% 를 막는다. storm 없는 캐릭터 제외."},
    "shield_regen": {"label": "실드 재생", "slots": ("hat", "suit"), "min": "rare",
                   "value": {"rare": 15.0, "unique": 8.0},
                   "ui": {"rare": "실드 15초마다 +1", "unique": "실드 8초마다 +1"},
                   "desc": "실드가 최대치 미만이면 피격 없이 N초마다 1칸 재생. 실드가 흡수할 때마다 타이머 리셋이라 연속 탱킹은 불가. hyunki(기본 실드 3) 탱크 빌드, 다른 캐릭터도 안전모=서스테인 슬롯이 된다."},
    "shield_burst": {"label": "실드 파열", "slots": ("hat",), "min": "rare",
                   "value": {"rare": 140, "unique": 9999},
                   "ui": {"rare": "탄막 소거 140px", "unique": "탄막 소거 전체"},
                   "desc": "실드가 피격을 흡수하는 순간 주변 적 탄환이 사라진다 — 피격이 곧 미니 결재폭탄이 되는 방어 손맛. '적 탄이 잘 안 보인다' 문제의 안전망."},
    "second_wind": {"label": "재기", "slots": ("hat",), "min": "rare",
                  "value": {"rare": 1, "unique": 2},
                  "ui": {"rare": "치명타 1회 버팀", "unique": "치명타 1회+실드"},
                  "desc": "목숨을 잃을 치명타(실드 0)를 스테이지당 1회 버틴다. 구덩이 추락(force kill)은 제외. 초급 유저가 쉬움/보통에서 먼저 쌓는 생존 퍽."},
    "loot_luck": {"label": "드롭 행운", "slots": ("hat", "acc"), "min": "rare",
                "value": {"rare": 1.5, "unique": 2.0},
                "ui": {"rare": "아이템 드롭 x1.5", "unique": "아이템 드롭 x2.0"},
                "desc": "잡몹/엘리트 처치 시 아이템 드롭 확률 배수 (progression drop_grunt 0.10 / drop_elite 0.30). 코인 가치·보스 드롭은 건드리지 않아 economy 수입 selftest 유지."},
    "melee_reach": {"label": "근접 리치", "slots": ("gloves", "weapon"), "min": "rare",
                  "value": {"rare": 1.3, "unique": 1.6},
                  "ui": {"rare": "근접 사거리 x1.3", "unique": "근접 사거리 x1.6"},
                  "desc": "근접 사거리 배수 (knife 42, hammer 52, whip 95, hip 60 px). 유니크는 등 뒤의 적도 맞춘다. 근접 자동 전환(_melee_targets 가 비면 사격)도 같은 사거리를 쓰므로 근접이 더 멀리서 발동한다."},
    "kill_haste": {"label": "처치 연사", "slots": ("gloves",), "min": "rare",
                 "value": {"rare": 1, "unique": 2},
                 "ui": {"rare": "처치 시 즉시 재발사", "unique": "처치 시 연사 +30%"},
                 "desc": "적을 처치하면 발사/근접 쿨다운(fire_cd 공유)이 즉시 0 이 되어 다음 공격을 바로 잇는다. 연속 처치 리듬을 만드는 장갑(연사) 정체성 퍽."},
    "inv_stack": {"label": "인벤 스택", "slots": ("gloves",), "min": "rare",
                "value": {"rare": 1, "unique": 2},
                "ui": {"rare": "인벤 스택 +1", "unique": "인벤 스택 +2"},
                "desc": "인벤토리 슬롯당 스택 상한(INV_STACK 3) 증가. 폭탄/커피를 보스전용으로 쌓아둘 수 있다. 해제하면 초과 스택은 남지만 더 늘지 않는다."},
    "item_time": {"label": "아이템 지속", "slots": ("gloves", "acc"), "min": "rare",
                "value": {"rare": 1.5, "unique": 2.0},
                "ui": {"rare": "아이템 지속 x1.5", "unique": "아이템 지속 x2.0"},
                "desc": "시간제 인벤토리 아이템이 오래 간다: 레이저/3연발/속사 시간, 유도탄 탄수, 야근 커피 슬로우, 분신/보안 드론/찹츄 지속. SLOW_FACTOR 는 그대로."},
    "keep_weapon": {"label": "무기 보존", "slots": ("suit",), "min": "rare",
                  "value": {"rare": 1, "unique": 2},
                  "ui": {"rare": "죽어도 무기 유지", "unique": "무기유지+무적 3.5초"},
                  "desc": "죽어도 특수 무기(레이저/유도탄/3연발/속사 + 남은 시간·탄수)를 잃지 않는다. 동료는 이미 부활을 넘긴다(게임오버에서만 clear). 초급 생존 퍽."},
    "stomp": {"label": "착지 충격파", "slots": ("shoes",), "min": "rare",
            "value": {"rare": 1, "unique": 2},
            "ui": {"rare": "착지 충격파 1dmg", "unique": "착지 충격파 2dmg"},
            "desc": "일정 높이 이상에서 착지하면 양쪽으로 지면 충격파(현기 해머 웨이브 재사용)가 나간다. 점프 자체가 공격이 되어 double_jump 와 시너지."},
    "pit_save": {"label": "낙하 구조", "slots": ("shoes",), "min": "rare",
               "value": {"rare": 1, "unique": 2},
               "ui": {"rare": "추락 구조 1회", "unique": "추락 구조 무제한"},
               "desc": "구덩이에 떨어지면 목숨을 잃는 대신 마지막으로 서 있던 지면으로 복귀한다. '피지컬을 쌓는' 초급 구간의 안전망."},
    "pierce": {"label": "관통탄", "slots": ("weapon",), "min": "rare",
             "value": {"rare": 1, "unique": 99},
             "ui": {"rare": "관통 +1", "unique": "완전 관통"},
             "desc": "일반/3연발/속사 탄이 적을 관통한다 (레이저는 이미 관통, 유도탄 제외). dongil 은 config pierce:true 로 이미 완전 관통이라 롤에서 제외(규칙 7); jaehwi(fire_rate 1.5) 총 빌드의 이유."},
    "crit": {"label": "급소", "slots": ("weapon",), "min": "rare",
           "value": {"rare": 0.1, "unique": 0.2},
           "ui": {"rare": "치명타 10% x2", "unique": "치명타 20% x2"},
           "desc": "플레이어의 총알·근접 타격이 확률적으로 2배 피해 + '크리!' 텍스트. 존/동료/폭탄/타자 wipe 는 제외해 궁극·폭탄 수치를 건드리지 않는다."},
    "boss_killer": {"label": "보스 킬러", "slots": ("weapon",), "min": "rare",
                  "value": {"rare": 0.2, "unique": 0.4},
                  "ui": {"rare": "보스 피해 +20%", "unique": "보스 피해 +40%"},
                  "desc": "보스·중간보스(e.boss, e.mid 포함)에게 주는 플레이어 피해 증가 — KOF 보스전 시간을 줄여 고난이도 진입을 완충. 결재 폭탄(BOMB_BOSS_FRAC)·타자 wipe 20% 청크는 제외."},
    "haggler": {"label": "강화 할인", "slots": ("acc",), "min": "rare",
              "value": {"rare": ENHANCE_PERK_DISCOUNT, "unique": 0.65},
              "ui": {"rare": "강화비 x0.8", "unique": "강화비 x0.65"},
              "desc": "확정 강화(economy.enhance) 비용 할인. 오너의 '고급 장비일수록 강화비 증가'(ENHANCE_RARITY_COST 1.6/2.6/4.5) 를 일부 상쇄: 유니크 x0.65 여도 일반의 1.8배. economy.py 스캐폴드에 이미 'haggler' 키로 배선돼 있다."},
}
PERK_COUNT = {"normal": 0, "rare": 1, "unique": 2}             # 등급별 퍼크 수
RARITY_RANK = {"normal": 0, "rare": 1, "unique": 2}


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _merge_dict(cur, val):
    """dict 상수 병합(새 dict 반환): 멤버는 기존 값의 모양에 맞추고, 양쪽 다 dict 면 재귀(PERKS 한 항목의 숫자 하나만 손댈 수 있게)."""
    merged = dict(cur)
    for k, v in val.items():
        ck = cur.get(k)
        if isinstance(ck, dict) and isinstance(v, dict):
            merged[k] = _merge_dict(ck, v)
        elif isinstance(ck, tuple):
            merged[k] = tuple(v) if isinstance(v, (list, tuple)) else ((v, v) if _is_num(v) else ck)
        elif _is_num(ck):
            merged[k] = type(ck)(v) if _is_num(v) else ck
        elif isinstance(ck, str):
            merged[k] = v if isinstance(v, str) else ck
        else:
            merged[k] = v
    return merged


def configure(cfg):
    """config.json 의 같은 이름 키로 모듈 상수를 덮어쓴다(dict 상수는 키 병합, 모르는 키 무시).
    dict 멤버는 기존 값의 모양에 맞춘다: tuple 엔 list/tuple 또는 스칼라(→ (v, v)), 숫자엔 숫자(같은 타입), 문자열엔 문자열.
    모양이 안 맞는 멤버는 무시한다(잘못된 config 로 한판 중간에 죽지 않게)."""
    g = globals()
    for key, val in (cfg or {}).items():
        if key not in g or key.startswith("_") or not key.isupper():
            continue
        cur = g[key]
        if isinstance(cur, dict) and isinstance(val, dict):
            g[key] = _merge_dict(cur, val)
        elif isinstance(cur, tuple) and isinstance(val, (list, tuple)):
            g[key] = tuple(val)
        elif isinstance(cur, (int, float)) and isinstance(val, (int, float)) and not isinstance(val, bool):
            g[key] = type(cur)(val) if isinstance(cur, float) else val
        elif isinstance(cur, str) and isinstance(val, str):
            g[key] = val
    # ENHANCE_PERK_DISCOUNT is the rare 'haggler' magnitude (PERKS captured it at import): retuning only the
    # constant follows through to the table (and its ui string) unless config.PERKS.haggler sets that member itself
    if isinstance(cfg, dict) and "ENHANCE_PERK_DISCOUNT" in cfg and isinstance(PERKS.get("haggler"), dict):
        own = cfg.get("PERKS") if isinstance(cfg.get("PERKS"), dict) else {}
        own = own.get("haggler") if isinstance(own.get("haggler"), dict) else {}
        sync = {}
        if not (isinstance(own.get("value"), dict) and "rare" in own["value"]):
            sync["value"] = {"rare": ENHANCE_PERK_DISCOUNT}
        if not (isinstance(own.get("ui"), dict) and "rare" in own["ui"]):
            sync["ui"] = {"rare": "강화비 x%g" % sync.get("value", PERKS["haggler"]["value"])["rare"]}
        if sync:
            g["PERKS"] = _merge_dict(PERKS, {"haggler": sync})


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
    """스탯 합 = STAT_BASE_SUM + stage//STAT_STAGE_DIV 를 셋 중 랜덤 분배 → × roll × RARITY_STAT_MULT, 반올림."""
    total = STAT_BASE_SUM + max(0, int(stage)) // STAT_STAGE_DIV
    raw = {k: 0 for k in STAT_KEYS}
    for _ in range(total):
        raw[rng.choice(STAT_KEYS)] += 1
    mult = roll * RARITY_STAT_MULT.get(rarity, 1.0)
    return {k: int(round(raw[k] * mult)) for k in STAT_KEYS}


def _perk_fits(p, slot):
    """퍼크 항목 p 가 slot 에 붙을 수 있나 (slot None 이거나 항목에 slots 가 없으면 어디든)."""
    slots = p.get("slots")
    return slot is None or not slots or slot in slots


def perk_pool(rarity, slot=None, exclude=()):
    """rarity 에서 롤 가능한 퍼크 키(PERKS 순서): min 등급 <= rarity, slot 풀 안(slot 주면), exclude 제외."""
    rank = RARITY_RANK.get(rarity, 0)
    ex = set(exclude or ())
    return [k for k, v in PERKS.items()
            if k not in ex and RARITY_RANK.get(v.get("min", "rare"), 1) <= rank and _perk_fits(v, slot)]


def roll_perks(rng, rarity, slot=None, exclude=()):
    """PERK_COUNT[rarity]개를 perk_pool(rarity, slot, exclude) 에서 중복 없이 뽑는다(seed 에 대해 결정적).
    풀이 비면 rng 소비 없이 []. exclude = 캐릭터에 안 맞는 키(storm 없음 → ult_*, pierce 내장 → pierce)."""
    n = int(PERK_COUNT.get(rarity, 0))
    pool = perk_pool(rarity, slot, exclude)
    out = []
    while pool and len(out) < n:
        k = rng.choice(pool)
        pool.remove(k)
        out.append(k)
    return out


def _prefix(rarity, roll):
    lo, hi = ROLL_RANGE
    span = (hi - lo) / 3.0 if hi > lo else 1.0
    idx = min(2, max(0, int((roll - lo) / span)))
    return NAME_PREFIX.get(rarity, NAME_PREFIX["normal"])[idx]


def make_equipment(rng, slot, rarity, level=0, stage=1, exclude=()):
    """장비 dict 생성. 이름 = <접두어> <슬롯라벨>, 접두어는 등급·roll 3분위로 결정(rng 에 대해 결정적).
    perks 는 슬롯 풀에서 exclude 를 뺀 뒤 뽑는다(캐릭터 부적합 키는 game.py 가 넘긴다)."""
    if slot not in SLOTS:
        slot = SLOTS[0]
    if rarity not in RARITY:
        rarity = "normal"
    level = max(0, min(MAX_LEVEL, int(level)))
    eid = "%012x" % rng.getrandbits(48)
    roll = round(rng.uniform(*ROLL_RANGE), 3)
    stats = _roll_stats(rng, stage, roll, rarity)          # 퍼크는 스탯 뒤에 뽑는다(기존 seed 의 id/roll/stats 유지)
    return {"id": eid, "slot": slot, "rarity": rarity, "level": level,
            "name": "%s %s" % (_prefix(rarity, roll), SLOT_LABEL[slot]),
            "roll": roll, "stats": stats, "perks": roll_perks(rng, rarity, slot, exclude)}


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


def active_perks(equipped):
    """장착 장비의 퍼크 {perk: rank} — 같은 키가 여럿이면 최고 등급 하나(MAX, 합산 없음; 유니크 2 > 레어 1).
    rank 는 장비 등급이되 퍼크의 min 등급 아래로는 안 내려간다. total_effect 와 별도 — 효과에 섞이지 않는다."""
    out = {}
    for eq in (equipped or {}).values():
        if not isinstance(eq, dict):
            continue
        rank = RARITY_RANK.get(eq.get("rarity"), 0)
        for p in (eq.get("perks") or []):
            if p in PERKS:
                r = max(rank, RARITY_RANK.get(PERKS[p].get("min", "rare"), 1))
                if r > out.get(p, 0):
                    out[p] = r
    return out


def perk_value(perks, key, default=1.0):
    """perks = {key: rank} (list/set 는 rank 1 = 레어로 본다). PERKS[key]["value"][RARITY[rank]];
    key 가 없거나 그 등급의 값이 없으면 default. 크기는 등급으로만 정해진다(레벨 무관)."""
    if not perks or key not in perks or key not in PERKS:
        return default
    vals = PERKS[key].get("value")
    if not isinstance(vals, dict):                          # 스칼라 value(등급 무관 표) 도 허용
        return default if vals is None else vals
    try:
        rank = max(0, min(len(RARITY) - 1, int(perks[key] if isinstance(perks, dict) else 1)))
    except (TypeError, ValueError):
        return default
    v = vals.get(RARITY[rank])
    return default if v is None else v


# ---------------------------------------------------------------- prices
def upgrade_cost(eq):
    """300 * 1.12**level * RARITY_COST; 레벨 20 이면 0(불가)."""
    level = int(eq.get("level", 0) or 0)
    if level >= MAX_LEVEL:
        return 0
    return int(UPGRADE_BASE * (UPGRADE_GROWTH ** level) * RARITY_COST.get(eq.get("rarity"), 1.0))


def enhance_cost(eq, perks=None):
    """확정 강화 비용 = 300 * 1.12**level * ENHANCE_RARITY_COST; 'haggler' 퍼크 ×value(레어 0.8 / 유니크 0.65);
    레벨 20 이면 0(불가). perks 는 {key: rank} (list 도 됨 = 레어)."""
    level = int(eq.get("level", 0) or 0)
    if level >= MAX_LEVEL:
        return 0
    c = UPGRADE_BASE * (UPGRADE_GROWTH ** level) * ENHANCE_RARITY_COST.get(eq.get("rarity"), 1.0)
    if perks and "haggler" in perks:
        c *= perk_value(perks, "haggler", ENHANCE_PERK_DISCOUNT)
    return int(c)


def enhance(eq, money, perks=None):
    """확정 강화 +1 (도박 아님). 반환 (eq, 잔액, 문구, ok). 입력 eq 는 바꾸지 않는다."""
    eq = dict(eq)
    level = int(eq.get("level", 0) or 0)
    if level >= MAX_LEVEL:
        return eq, money, "이미 최대 레벨(%d)입니다" % MAX_LEVEL, False
    cost = enhance_cost(eq, perks)
    if money < cost:
        return eq, money, "돈이 부족합니다 (%d ₩ 필요)" % cost, False
    eq["level"] = level + 1
    return eq, money - cost, "강화 성공! Lv %d → %d (-%d ₩)" % (level, level + 1, cost), True


def buy_price(eq, stage):
    """(600 * RARITY_PRICE + 120*level) * (1 + 0.06*(stage-1))."""
    level = int(eq.get("level", 0) or 0)
    base = PRICE_BASE * RARITY_PRICE.get(eq.get("rarity"), 1) + PRICE_PER_LEVEL * level
    return int(base * (1 + PRICE_STAGE_GROWTH * (max(1, int(stage)) - 1)))


def sell_price(eq, stage):
    return int(buy_price(eq, stage) * SELL_RATIO)


def roll_rarity(rng, table):
    return _weighted(rng, table)


def make_shop_stock(rng, stage, n=10, exclude=()):
    """상점 목록 n개: SHOP_RARITY, 슬롯 랜덤, level 0~min(5, stage//3). exclude → make_equipment."""
    stage = max(1, int(stage))
    lv_max = min(SHOP_LEVEL_CAP, stage // SHOP_LEVEL_STAGE_DIV)
    return [make_equipment(rng, rng.choice(SLOTS), roll_rarity(rng, SHOP_RARITY),
                           rng.randint(0, lv_max), stage, exclude) for _ in range(int(n))]


def BOX_PRICE(stage):
    return int(BOX_PRICE_BASE * (1 + PRICE_STAGE_GROWTH * (max(1, int(stage)) - 1)))


def _box_item(rng):
    return _weighted(rng, BOX_ITEM_WEIGHTS)


def open_box(rng, stage, exclude=()):
    """랜덤박스: 60% equip(BOX_RARITY) / 25% item / 10% money / 5% dud. exclude → make_equipment."""
    kind = _weighted(rng, BOX_OUTCOME)
    out = {"kind": kind, "equip": None, "item": None, "money": 0, "text": ""}
    if kind == "equip":
        eq = make_equipment(rng, rng.choice(SLOTS), roll_rarity(rng, BOX_RARITY), 0, stage, exclude)
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
    """강화 도박: cost = upgrade_cost*1.5; 60% +2lv / 30% 유지 / 10% -3lv(유니크는 -1lv). 반환 (eq, 잔액, 문구)."""
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
            new = max(0, level - GAMBLE_UPGRADE_DOWN_UNIQUE)
            text = "실패... 유니크의 가호로 -%d 레벨 (Lv %d)" % (level - new, new)
        else:
            new = max(0, level - GAMBLE_UPGRADE_DOWN)
            text = "실패... -%d 레벨 (Lv %d)" % (level - new, new)
        if new == level:                                    # Lv 0: nothing to lose — say so, not "-0 레벨"
            text = ("유니크의 가호 · 변화 없음 (Lv %d)" if eq.get("rarity") == "unique"
                    else "실패... 이미 Lv %d (변화 없음)") % level
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


def gamble_slots(rng, bet, stage, exclude=()):
    """슬롯: 777 = bet*30 + 유니크 / ★★★ = 레어 장비 / ₩₩₩ = bet*10 / ◆◆◆·♥♥♥ = bet*5 / 2개 동일 = bet (7 페어는 아이템도).
    exclude → make_equipment(장비 상품의 퍼크 풀)."""
    bet = max(0, int(bet))
    reels = _spin(rng)
    out = {"reels": reels, "payout": 0, "prize": None, "text": " ".join(reels)}
    a, b, c = reels
    if a == b == c:
        out["payout"] = bet * SLOT_PAYOUT.get(a, 0)
        if a == "7":
            eq = make_equipment(rng, rng.choice(SLOTS), "unique", 0, stage, exclude)
            out["prize"] = {"kind": "equip", "equip": eq}
            out["text"] = "잭팟!!! +%d ₩ · %s" % (out["payout"], eq["name"])
        elif a == "★":
            eq = make_equipment(rng, rng.choice(SLOTS), "rare", 0, stage, exclude)
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
    if "perks" not in out:                                     # 퍼크 이전 세이브의 레어/유니크: id 로 결정적 재롤(로드마다 동일)
        try:
            seed = int(str(out.get("id") or "0"), 16)
        except ValueError:
            seed = 0
        raw = roll_perks(random.Random(seed), out["rarity"], out["slot"])
    else:
        raw = out.get("perks")
    perks = []                                                 # 아는 키만, 중복 제거, min 등급·슬롯 풀 검사, PERK_COUNT 로 자름
    rank = RARITY_RANK.get(out["rarity"], 0)
    for p in (raw if isinstance(raw, list) else []):
        if (isinstance(p, str) and p in PERKS and p not in perks
                and RARITY_RANK.get(PERKS[p].get("min", "rare"), 1) <= rank and _perk_fits(PERKS[p], out["slot"])):
            perks.append(p)
    out["perks"] = perks[:int(PERK_COUNT.get(out["rarity"], 0))]
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

    def perks(self):
        """장착 퍼크 {perk: rank} (같은 키는 최고 등급 하나 = MAX). effect() 에는 섞이지 않는다."""
        return active_perks(self.equipped)

    @staticmethod
    def _copy_eq(e):
        """세이브용 복사: stats/perks 컨테이너까지 새로 만들어 라이브 장비와 공유하지 않는다."""
        d = dict(e)
        if isinstance(d.get("stats"), dict):
            d["stats"] = dict(d["stats"])
        d["perks"] = list(d.get("perks") or [])
        return d

    def to_save(self):
        return {"items": [self._copy_eq(e) for e in self.items],
                "equipped": {s: (self._copy_eq(self.equipped[s]) if self.equipped.get(s) else None) for s in SLOTS}}


# ---------------------------------------------------------------- money
def money_drop(rng, kind, stage, diff_mult, acc_bonus):
    """kind grunt 20~40 / elite 60~100 / mid 250 / boss 600 / word 400 ; × (1+growth*(stage-1)) × diff × (1+acc)."""
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
    print("income 50 stages (normal): %d (target 190000 +/-25%%)" % income)
    assert 142500 <= income <= 237500, income

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
        downs = 0
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
            down = GAMBLE_UPGRADE_DOWN_UNIQUE if rarity == "unique" else GAMBLE_UPGRADE_DOWN
            assert new["level"] >= max(0, lv - down), (rarity, lv, new["level"])
            if new["level"] < lv:
                downs += 1
            delta += new["level"] - lv
        assert delta > 0, (rarity, delta)
        assert downs > 0, rarity                          # 유니크도 이제 -1 은 맞는다
    eq = make_equipment(R(6), "hat", "normal", 3, 1)
    same, left, text = gamble_upgrade(R(6), eq, 0)
    assert same["level"] == 3 and left == 0 and "부족" in text
    for rar in ("unique", "normal"):            # Lv 0 'down' roll (seed 2): nothing to lose, no "-0 레벨" wording
        lv0, _, text = gamble_upgrade(R(2), {"slot": "hat", "rarity": rar, "level": 0, "name": "x"}, 10 ** 6)
        assert lv0["level"] == 0 and "변화 없음" in text and "-0" not in text, (rar, text)

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

    # (j) unique: stats x RARITY_STAT_MULT, slot effects x RARITY_MULT (two separate multipliers)
    ms, me = RARITY_STAT_MULT["unique"], RARITY_MULT["unique"]
    assert ms != me and RARITY_STAT_MULT["normal"] == 1.0 and RARITY_MULT["normal"] == 1.0
    for slot in SLOTS:
        for lv in (0, 7, 20):
            a = equip_effect(make_equipment(R(10), slot, "normal", lv, 40))
            b = equip_effect(make_equipment(R(10), slot, "unique", lv, 40))
            for k in EFFECT_KEYS:
                if k in STAT_KEYS:
                    assert abs(b[k] - ms * a[k]) <= 2, (slot, lv, k, a[k], b[k])
                elif k in INT_EFFECTS:
                    assert abs(b[k] - me * a[k]) <= 2, (slot, lv, k, a[k], b[k])
                else:
                    assert abs(b[k] - me * a[k]) < 1e-9, (slot, lv, k)
    pts = STAT_BASE_SUM + 20 // STAT_STAGE_DIV                 # stage 20, roll 1.0: sum is exact
    assert pts == 6
    assert sum(_roll_stats(R(11), 20, 1.0, "normal").values()) == pts
    assert sum(_roll_stats(R(11), 20, 1.0, "unique").values()) == int(pts * ms)
    assert sum(_roll_stats(R(11), 1, 1.0, "normal").values()) == STAT_BASE_SUM
    z = total_effect({s: None for s in SLOTS})
    assert set(z) == set(EFFECT_KEYS) and all(v == 0 for v in z.values())
    sh = equip_effect({"slot": "shoes", "rarity": "normal", "level": 10})
    assert abs(sh["speed"] - 0.10) < 1e-9 and abs(sh["jump"] - 0.06) < 1e-9

    # (k) deterministic enhance: one item 0->20 per rarity, cost order, haggler, MAX_LEVEL, no money
    target = {"normal": 34600, "rare": 56200, "unique": 97200}
    for rarity in RARITY:
        eq = make_equipment(R(12), "gloves", rarity, 0, 1)
        money = 10 ** 6
        total = 0
        for lv in range(MAX_LEVEL):
            assert eq["level"] == lv
            c = enhance_cost(eq)
            assert c > 0 and c == int(UPGRADE_BASE * UPGRADE_GROWTH ** lv * ENHANCE_RARITY_COST[rarity])
            before = dict(eq)
            eq, money, text, ok = enhance(eq, money)
            assert ok and eq["level"] == lv + 1 and "성공" in text and before["level"] == lv   # input untouched
            total += c
        assert money == 10 ** 6 - total
        print("enhance %s 0->20: %d (target %d +/-25%%)" % (rarity, total, target[rarity]))
        assert target[rarity] * 0.75 <= total <= target[rarity] * 1.25, (rarity, total)
        assert enhance_cost(eq) == 0
        same, left, text, ok = enhance(eq, money)
        assert not ok and same["level"] == MAX_LEVEL and left == money and "최대" in text
    e5 = {"slot": "hat", "level": 5}
    assert enhance_cost(dict(e5, rarity="normal")) < enhance_cost(dict(e5, rarity="rare")) < enhance_cost(dict(e5, rarity="unique"))
    assert enhance_cost(dict(e5, rarity="unique")) > int(upgrade_cost(dict(e5, rarity="unique")) * GAMBLE_UPGRADE_COST_MULT)
    r5 = dict(e5, rarity="rare")
    full = enhance_cost(r5)
    assert abs(enhance_cost(r5, {"haggler": 1}) - full * ENHANCE_PERK_DISCOUNT) <= 1 and full > enhance_cost(r5, {"haggler": 1})
    assert enhance_cost(r5, ["haggler"]) == enhance_cost(r5, {"haggler": 1})
    assert enhance_cost(r5, {"magnet": 1}) == full and enhance_cost(r5, {}) == full and enhance_cost(r5, None) == full
    same, left, text, ok = enhance(r5, full - 1)
    assert not ok and same["level"] == 5 and left == full - 1 and "부족" in text
    new, left, text, ok = enhance(r5, full, {"haggler": 1})
    assert ok and new["level"] == 6 and left == full - enhance_cost(r5, {"haggler": 1}) and r5["level"] == 5
    # configure round-trip: ENHANCE_PERK_DISCOUNT is the rare haggler magnitude, so retuning the constant reprices
    cheap = enhance_cost(r5, {"haggler": 1})
    configure({"ENHANCE_PERK_DISCOUNT": 0.5})
    assert ENHANCE_PERK_DISCOUNT == 0.5 and PERKS["haggler"]["value"] == {"rare": 0.5, "unique": 0.65}
    assert PERKS["haggler"]["ui"]["rare"] == "강화비 x0.5" and abs(enhance_cost(r5, {"haggler": 1}) - full * 0.5) <= 1
    configure({"ENHANCE_PERK_DISCOUNT": 0.6, "PERKS": {"haggler": {"value": {"rare": 0.7}}}})   # explicit member wins
    assert ENHANCE_PERK_DISCOUNT == 0.6 and PERKS["haggler"]["value"]["rare"] == 0.7 and PERKS["haggler"]["ui"]["rare"] == "강화비 x0.7"
    configure({"ENHANCE_PERK_DISCOUNT": 0.8})
    assert PERKS["haggler"]["value"]["rare"] == 0.8 and PERKS["haggler"]["ui"]["rare"] == "강화비 x0.8" and enhance_cost(r5, {"haggler": 1}) == cheap

    # (l) perks — table contract (19 keys, 6 slot pools x 4, ui strings pre-formatted, unique beats rare)
    assert PERK_COUNT == {"normal": 0, "rare": 1, "unique": 2} and RARITY_RANK["unique"] > RARITY_RANK["rare"] > RARITY_RANK["normal"]
    POOLS = {"hat": {"shield_regen", "shield_burst", "second_wind", "loot_luck"},
             "gloves": {"melee_reach", "kill_haste", "inv_stack", "item_time"},
             "suit": {"ult_time", "ult_haste", "shield_regen", "keep_weapon"},
             "shoes": {"double_jump", "stomp", "pit_save", "magnet"},
             "weapon": {"pierce", "crit", "boss_killer", "melee_reach"},
             "acc": {"magnet", "item_time", "loot_luck", "haggler"}}
    LOWER_IS_BETTER = ("ult_haste", "haggler", "shield_regen")   # cooldown/cost multipliers, regen interval: unique is the smaller number
    assert len(PERKS) == 19 and set().union(*POOLS.values()) == set(PERKS)
    for k, p in PERKS.items():
        assert set(p) >= {"label", "slots", "min", "value", "ui", "desc"} and p["min"] == "rare", k
        assert 1 <= len(p["label"]) <= 6 and p["desc"], k
        assert isinstance(p["slots"], tuple) and 1 <= len(p["slots"]) <= 2 and all(s in SLOTS for s in p["slots"]), k
        assert set(p["value"]) == set(p["ui"]) == {"rare", "unique"}, k
        r, u = p["value"]["rare"], p["value"]["unique"]
        assert _is_num(r) and _is_num(u) and ((u < r) if k in LOWER_IS_BETTER else (u > r)), (k, r, u)
        for s in p["ui"].values():                              # rule 13: <= 12 chars after {v} substitution
            assert isinstance(s, str) and s and "{" not in s and len(s) <= 12, (k, s)
    for slot in SLOTS:
        assert set(perk_pool("unique", slot)) == set(perk_pool("rare", slot)) == POOLS[slot], slot
        assert perk_pool("normal", slot) == [] and perk_pool("rare", slot) == [k for k in PERKS if k in POOLS[slot]]
        for ex in (("ult_time", "ult_haste"), ("pierce",)):        # jaehwi/masked (no storm) · dongil (pierce built in)
            left = perk_pool("unique", slot, ex)
            assert len(left) >= 2 and not set(left) & set(ex), (slot, ex, left)
    assert perk_pool("unique") == list(PERKS) and perk_pool("unique", None, list(PERKS)) == [] and perk_pool("zzz") == []
    assert PERKS["magnet"]["value"] == {"rare": 160, "unique": 9999} and PERKS["haggler"]["value"] == {"rare": ENHANCE_PERK_DISCOUNT, "unique": 0.65}
    assert PERKS["magnet"]["ui"] == {"rare": "코인 자석 160px", "unique": "코인 자석 전체"} and PERKS["pierce"]["ui"]["unique"] == "완전 관통"
    assert PERKS["ult_time"]["value"] == {"rare": 1.5, "unique": 2.0} and PERKS["ult_time"]["ui"]["rare"] == "궁극기 지속 x1.5"
    # rolls: 10k per slot x rarity — normal [], rare 1 key of the slot pool, unique 2 distinct, every pool key seen, seed-stable
    for slot in SLOTS:
        for rarity in RARITY:
            rng = R(20)
            seen = set()
            for _ in range(10000):
                ps = make_equipment(rng, slot, rarity, 0, 5)["perks"]
                assert len(ps) == PERK_COUNT[rarity] == len(set(ps)) and set(ps) <= POOLS[slot], (slot, rarity, ps)
                seen.update(ps)
            assert seen == (POOLS[slot] if rarity != "normal" else set()), (slot, rarity, seen)
        assert make_equipment(R(21), slot, "unique", 2, 9) == make_equipment(R(21), slot, "unique", 2, 9)
    kept = dict(PERKS)
    PERKS.clear()
    try:                                                           # empty table: no rng use, no perks
        rr = R(13)
        state = rr.getstate()
        assert roll_perks(rr, "unique", "acc") == [] and rr.getstate() == state
        bare = make_equipment(R(17), "suit", "unique", 3, 12)
        assert bare["perks"] == [] and isinstance(bare["perks"], list)
    finally:
        PERKS.update(kept)
    filled = make_equipment(R(17), "suit", "unique", 3, 12)        # perks drawn AFTER stats: id/roll/stats unchanged
    assert (filled["id"], filled["roll"], filled["stats"]) == (bare["id"], bare["roll"], bare["stats"])
    assert len(filled["perks"]) == 2 and set(filled["perks"]) <= POOLS["suit"] and make_equipment(R(17), "hat", "normal", 0, 12)["perks"] == []
    PERKS["crit"]["min"] = "unique"                                # unique-only gating still works (min rank)
    try:
        assert all("crit" not in roll_perks(R(seed), "rare", "weapon") for seed in range(200))
        assert any("crit" in roll_perks(R(seed), "unique", "weapon") for seed in range(200))
        assert _valid_eq({"slot": "weapon", "rarity": "rare", "perks": ["crit", "pierce"]})["perks"] == ["pierce"]
    finally:
        PERKS["crit"]["min"] = "rare"
    # exclusions thread through every gear source; old call forms unchanged
    ex = ("ult_time", "ult_haste", "pierce")
    hit = 0
    for seed in range(40):
        hit += sum(bool(set(eq["perks"]) & set(ex)) for eq in make_shop_stock(R(seed), 30, 10))
        assert not any(set(eq["perks"]) & set(ex) for eq in make_shop_stock(R(seed), 30, 10, exclude=ex))
        r = open_box(R(seed), 30, exclude=ex)
        assert r["equip"] is None or not set(r["equip"]["perks"]) & set(ex)
        r = gamble_slots(R(seed), 100, 30, exclude=ex)
        assert not r["prize"] or r["prize"]["kind"] != "equip" or not set(r["prize"]["equip"]["perks"]) & set(ex)
    assert hit > 0                                                 # without exclude those keys do roll
    assert set(make_equipment(R(22), "suit", "unique", 0, 9, exclude=("ult_time", "ult_haste"))["perks"]) == {"shield_regen", "keep_weapon"}
    assert make_shop_stock(R(3), 5, 4) == make_shop_stock(R(3), 5, 4, exclude=()) and open_box(R(4), 3) == open_box(R(4), 3, ())
    assert gamble_slots(R(8), 100, 10) == gamble_slots(R(8), 100, 10, ()) and roll_perks(R(1), "rare") == roll_perks(R(1), "rare", None, ())
    # _valid_eq: unknown / non-str / dup / slot-mismatch / over-cap dropped; normal -> []; legacy (no key) re-rolled from id
    v = _valid_eq({"slot": "hat", "rarity": "rare", "perks": ["zzz", "magnet", 3, "shield_regen", "shield_regen", "second_wind"]})
    assert v["perks"] == ["shield_regen"], v["perks"]
    v = _valid_eq({"slot": "hat", "rarity": "unique", "perks": ["loot_luck", "magnet", "second_wind", "shield_burst"]})
    assert v["perks"] == ["loot_luck", "second_wind"]
    assert _valid_eq({"slot": "hat", "rarity": "normal", "perks": ["shield_regen"]})["perks"] == []
    assert _valid_eq({"slot": "hat", "rarity": "rare", "perks": "magnet"})["perks"] == [] and _valid_eq({"slot": "hat", "rarity": "rare", "perks": []})["perks"] == []
    assert _valid_eq({"slot": "hat"})["perks"] == []               # legacy normal: nothing to roll
    for rarity in ("rare", "unique"):
        for slot in SLOTS:
            old = {"slot": slot, "rarity": rarity, "id": "00000000abcd", "level": 4}
            a, b = _valid_eq(old)["perks"], _valid_eq(dict(old))["perks"]
            assert a == b == roll_perks(random.Random(0xabcd), rarity, slot) and len(a) == PERK_COUNT[rarity] and set(a) <= POOLS[slot], (slot, rarity, a)
    assert _valid_eq({"slot": "acc", "rarity": "unique", "id": "zz"})["perks"] == roll_perks(random.Random(0), "unique", "acc")   # bad id -> seed 0
    assert _valid_eq({"slot": "acc", "rarity": "unique"})["perks"] == roll_perks(random.Random(0), "unique", "acc")
    legacy = Warehouse({"items": [{"slot": "shoes", "rarity": "rare", "id": "0000000000ff"}], "equipped": {"acc": {"slot": "acc", "rarity": "unique", "id": "0000000000ff"}}})
    assert legacy.items[0]["perks"] == roll_perks(random.Random(255), "rare", "shoes") and len(legacy.equipped["acc"]["perks"]) == 2
    assert Warehouse(legacy.to_save()).to_save() == legacy.to_save()
    # active_perks / Warehouse.perks = {key: rank} (MAX, never add); perk_value rank-aware; to_save copies; effect() untouched
    w = Warehouse(None)
    ea = dict(make_equipment(R(15), "acc", "unique", 0, 9), perks=["magnet", "haggler"])
    es = dict(make_equipment(R(16), "shoes", "rare", 0, 9), perks=["magnet"])
    eh = dict(make_equipment(R(18), "hat", "rare", 0, 9), perks=["shield_regen"])
    su = dict(make_equipment(R(19), "suit", "unique", 0, 9), perks=["shield_regen", "ult_time"])
    assert w.add(es) and w.add(eh) and w.equip(0) is es and w.equip(0) is eh
    assert w.perks() == {"magnet": 1, "shield_regen": 1}
    assert w.add(ea) and w.add(su) and w.equip(0) is ea and w.equip(0) is su
    assert w.perks() == {"magnet": 2, "haggler": 2, "shield_regen": 2, "ult_time": 2} and active_perks(w.equipped) == w.perks()
    assert w.unequip("acc") and w.perks()["magnet"] == 1 and "haggler" not in w.perks()   # rare copy takes over
    assert w.equip(len(w.items) - 1) is ea and w.perks()["magnet"] == 2
    assert active_perks(None) == {} and active_perks({"hat": None, "acc": {"perks": ["nope"]}}) == {}
    assert active_perks({"hat": {"rarity": "normal", "perks": ["second_wind"]}}) == {"second_wind": 1}   # hand-made: never below min rank
    p = w.perks()
    assert perk_value(p, "magnet") == 9999 and perk_value({"magnet": 1}, "magnet") == 160 and perk_value({"magnet": 0}, "magnet", 7) == 7
    assert perk_value(p, "ult_time") == 2.0 and perk_value({"ult_time": 1}, "ult_time") == 1.5 and perk_value(p, "haggler") == 0.65
    assert perk_value(p, "double_jump", 0) == 0 and perk_value(p, "nope", 7) == 7 and perk_value({}, "ult_time", 5) == 5
    assert perk_value(["double_jump"], "double_jump", False) == 1 and perk_value(None, "magnet") == 1.0   # list = rare rank
    assert perk_value({"magnet": "x"}, "magnet", 3) == 3 and perk_value({"magnet": 9}, "magnet") == 9999   # bad / over-high rank
    assert set(w.effect()) == set(EFFECT_KEYS) and "magnet" not in w.effect()
    save = w.to_save()
    assert save["equipped"]["acc"]["perks"] == ["magnet", "haggler"]
    assert save["equipped"]["acc"]["perks"] is not ea["perks"] and save["equipped"]["acc"]["stats"] is not ea["stats"]
    save["equipped"]["acc"]["perks"].append("x")
    save["equipped"]["acc"]["stats"]["str"] = 999
    assert ea["perks"] == ["magnet", "haggler"] and ea["stats"]["str"] != 999
    w2 = Warehouse(w.to_save())
    assert w2.to_save() == w.to_save() and w2.perks() == w.perks()
    assert Warehouse(save).equipped["acc"]["perks"] == ["magnet", "haggler"]   # edited 'x' dropped
    # enhance / gamble never touch perks; haggler rank prices the enhance (rare 0.8, unique 0.65)
    e2, _, _, ok = enhance(ea, 10 ** 6)
    assert ok and e2["perks"] == ea["perks"] == ["magnet", "haggler"] and gamble_upgrade(R(1), ea, 10 ** 6)[0]["perks"] == ea["perks"]
    assert abs(enhance_cost(r5, {"haggler": 2}) - full * 0.65) <= 1 and enhance_cost(r5, {"haggler": 2}) < enhance_cost(r5, {"haggler": 1}) < full
    assert enhance_cost(r5, p) == enhance_cost(r5, {"haggler": 2}) and enhance_cost(r5, {"haggler": True}) == enhance_cost(r5, ["haggler"])
    # configure: nested dicts merge one member at a time (retune one magnitude / slot pool / ui string, keep the rest)
    configure({"PERKS": {"magnet": {"value": {"rare": 200}, "slots": ["acc"]}, "haggler": {"ui": {"rare": "강화비 -20%"}}}})
    assert PERKS["magnet"]["value"] == {"rare": 200, "unique": 9999} and PERKS["magnet"]["slots"] == ("acc",) and PERKS["magnet"]["label"] == "코인 자석"
    assert PERKS["haggler"]["ui"] == {"rare": "강화비 -20%", "unique": "강화비 x0.65"} and PERKS["haggler"]["value"]["rare"] == ENHANCE_PERK_DISCOUNT
    assert "magnet" not in perk_pool("rare", "shoes") and perk_value({"magnet": 1}, "magnet") == 200 and len(PERKS) == 19
    assert _valid_eq({"slot": "shoes", "rarity": "rare", "perks": ["magnet"]})["perks"] == []
    configure({"PERKS": {"magnet": {"value": {"rare": 160}, "slots": ["acc", "shoes"]}, "haggler": {"ui": {"rare": "강화비 x0.8"}}}})
    assert PERKS == kept and list(PERKS) == list(kept)

    # configure: override & ignore unknown
    old = MONEY_STAGE_GROWTH
    configure({"MONEY_STAGE_GROWTH": 0.5, "RARITY_MULT": {"rare": 2.0}, "NOT_A_KEY": 1, "ROLL_RANGE": [0.5, 1.5]})
    assert MONEY_STAGE_GROWTH == 0.5 and RARITY_MULT["rare"] == 2.0 and RARITY_MULT["unique"] == 3.0 and ROLL_RANGE == (0.5, 1.5)
    configure({"MONEY_STAGE_GROWTH": old, "RARITY_MULT": {"rare": 1.8}, "ROLL_RANGE": [0.7, 1.3]})
    # configure: dict members are coerced to the existing member's shape (scalar -> (v, v), 1.0 -> 1, str ignored)
    configure({"MONEY_KIND": {"boss": 600}, "PERK_COUNT": {"rare": 1.0}, "ENHANCE_RARITY_COST": {"rare": "2.6"}})
    assert MONEY_KIND["boss"] == (600, 600) and PERK_COUNT["rare"] == 1 and type(PERK_COUNT["rare"]) is int
    assert ENHANCE_RARITY_COST["rare"] == 2.6 and money_drop(R(1), "boss", 1, 1.0, 0.0) == 600
    assert _valid_eq({"slot": "hat", "rarity": "rare"})["perks"] == roll_perks(random.Random(0), "rare", "hat")   # legacy: no key, no id
    assert _valid_eq({"slot": "hat", "rarity": "rare", "perks": []})["perks"] == [] and enhance_cost({"rarity": "rare", "level": 0}) > 0
    PERK_COUNT["rare"] = 1.0                    # consumers tolerate a float count even when set directly
    assert _valid_eq({"slot": "hat", "rarity": "rare", "perks": ["x"]})["perks"] == [] and len(roll_perks(R(1), "rare")) == 1
    PERK_COUNT["rare"] = 1
    print("economy selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    print(__doc__)
