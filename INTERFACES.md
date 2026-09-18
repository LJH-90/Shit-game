# MolGam 모듈 인터페이스 (고정)

병렬 작업 팀 A/B/C/D가 공유하는 계약. 여기 적힌 시그니처를 바꾸지 말 것. 추가는 허용.
전체 배경·규칙은 `PLAN.md` 참조. 런타임은 Python 3.10+ 표준 라이브러리만(tkinter, ctypes, json, zlib, struct, base64). Pillow/numpy/scipy는 `tools/` 개발 스크립트에서만 허용.

모든 파일 인코딩 UTF-8. 좌표계: 게임 공간 = 오버레이 밴드 내부 픽셀, 원점 좌상단, y 아래로 증가.

---

## A. `assets_data.py` (생성물) + `sprites.py`

### assets_data.py — `tools/recolor.py`가 생성. 손으로 수정 금지.

```python
# 픽셀 클래스 (상위 4비트) / 명암 단계 (하위 4비트, 0=가장 어두움 .. 3=가장 밝음)
CLASSES = {0:"transparent", 1:"outline", 2:"hair", 3:"skin", 4:"shirt", 5:"pants",
           6:"gun", 7:"shoe", 8:"white", 9:"fx"}
# frame_id -> (w, h, anchor_x, anchor_y, data)
#   data: 길이 w*h 의 bytes. 각 바이트 = (class<<4)|shade. 행 우선.
#   anchor: 발바닥 중앙 (하단 중앙) 픽셀 좌표. 캐릭터 배치 기준점.
FRAMES: dict[str, tuple[int,int,int,int,bytes]]
# 애니메이션 이름 -> frame_id 목록 (순서대로 재생). 필수 키:
#   "idle","run","jump","fall","shoot","shoot_run","crouch","crouch_shoot","death","victory"
#   (시트에 없으면 가장 가까운 프레임으로 대체하되 키는 반드시 존재)
ANIMS: dict[str, list[str]]
# 애니메이션별 프레임당 지속시간(초)
ANIM_FPS: dict[str, float]   # 예: {"run": 12, "idle": 6, ...}
```

### sprites.py

```python
PALETTES: dict[str, dict[str, str]]
# palette_name -> {class_name: "#rrggbb"} (shade 2 = 기본색; 0,1 어둡게, 3 밝게는 sprites.py가 자동 계산)
# 필수 palette_name:
#   플레이어: "jaehwi"(회색 티, 검정 머리), "hyunki"(남색 티), "dongil"(검정 티)
#   잡병: "intern","staff","assistant","manager"        (인턴/사원/대리/과장) — 셔츠 흰~밝은 정장, 직급 오를수록 짙게
#   정예: "deputy","general","teamlead"                 (차장/부장/팀장) — 짙은 정장
#   중간보스: "director","md","evp"                     (실장/상무/전무)
#   최종: "ceo","chairman"
#   연구소: "lab1","lab2","lab3","lab4","lab5"          (연구원/선임/책임/수석/연구소장) — 흰 가운

class SpriteBank:
    def __init__(self, tk_root, base_scale: int = 2): ...
    def get(self, anim: str, frame: int, palette: str, flip: bool = False, scale: int | None = None) -> "tk.PhotoImage":
        """캐시된 PhotoImage. frame은 len(ANIMS[anim])로 자동 모듈로. scale None이면 base_scale.
        flip=True 는 좌우 반전(기본 프레임은 오른쪽을 보고 있음). 투명 픽셀은 실제 알파 투명."""
    def anim_len(self, anim: str) -> int: ...
    def frame_time(self, anim: str) -> float: ...
    def anchor(self, anim: str, frame: int, flip: bool = False, scale: int | None = None) -> tuple[int, int]:
        """반환된 PhotoImage 내에서 발바닥 중앙 픽셀 위치(스케일 적용). Canvas 배치 시 anchor="nw" 로 (x-ax, y-ay)."""
    def size(self, anim: str, frame: int, scale: int | None = None) -> tuple[int, int]: ...
    def preload(self, palettes: list[str], scales: list[int] = (2,)) -> None: ...
```

구현 메모: PNG는 zlib+struct로 직접 인코딩해 `tk.PhotoImage(data=base64)`로 생성(알파 지원). 외부 라이브러리 금지.

추가(v1.2, additive): 플레이어 캐릭터 전용 프레임 세트.
- `assets_chars.py` — `tools/import_char_sheets.py`가 `sheets/<key>.png`(432×800, 셀 72×80, 한 줄 = 한 애니메이션, 발끝 = 셀 y77·x36)에서 생성. 손으로 수정 금지.
  `CHAR_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba)` — rgba 는 w*h*4 바이트(알파 0/255). frame_id·ANIMS·ANIM_FPS 는 `assets_data` 와 공유.
- `sprites.py` — 팔레트 이름이 `CHAR_FRAMES` 에 있으면(jaehwi/hyunki/dongil) 팔레트 스왑 대신 그 캐릭터의 원색 프레임을 쓴다. 적은 기존 `assets_data` 그대로.
  캐릭터마다 프레임 크기·앵커가 다르므로 `size(..., palette=None)`, `anchor(..., palette=None)` 에 팔레트를 넘긴다(생략 시 공용 프레임 기준).

추가(v1.3, additive):
- `assets_extra.py` — `tools/build_run_frames.py` 가 원본 시트의 서서 달리는 프레임으로 생성. assets_data 와 같은 형식의 `FRAMES`, 그리고 `ANIMS`/`ANIM_FPS` 의 `run`(4장)·`shoot_run`(3장) 교체분. 손으로 수정 금지.
  같은 스크립트가 캐릭터별로 칠한 `sheets/<key>_run.png`(셀 100×80, 발끝 y77·x50, 0행 run / 1행 shoot_run)도 만든다. `import_char_sheets.py` 가 이를 읽는다.
- `sprites.py` — `FRAMES`/`ANIMS`/`ANIM_FPS` = assets_data + assets_extra 병합본. 공용(팔레트) 프레임은 로드 시 1px 윤곽선을 둘러 1px 패딩(앵커 +1).
- 문현기 실드: `config.json` 캐릭터 항목 `"shield": N`(기본 0). 적 탄환·보스 돌진 피격 시 실드가 먼저 1 깎이고 `SHIELD_INV` 초 무적, 0이면 목숨 차감. 스테이지 시작·부활 때 가득 채움. 구덩이 낙사는 실드 무시.
  snapshot `hud` 에 `"shield": int`, `"shield_max": int` 추가.

추가(v1.4, additive):
- `CHAR_KEYS` 에 히든 캐릭터 `"masked"` 추가(4명). config 캐릭터 항목 `"hidden": true`, `"unlock_stage": N` 이면 N스테이지 클리어 전까지 잠김(선택 불가, 실루엣). 해금 목록은 `save_data()["unlocked"]`.
  `sprites.PALETTES["silhouette"]` — 잠긴 캐릭터 표시용. `assets_chars.CHAR_FRAMES["masked"]` 는 `import_char_sheets.py` 가 공용 프레임을 칠해 생성.
- 근접 공격: config 캐릭터 항목 `"melee": {range, damage, knockback, cooldown, both_sides, only, text}`. 사격 키를 눌렀을 때 사거리 안에 적이 있으면 사격 대신 근접 타격(밀쳐내기). `only: true` 면 사격하지 않는다.
- 스킬: 논리 키 `'skill'`(C). config `"storm": {label, cooldown, duration, width, tick, damage}` 캐릭터만 사용. 앞쪽에 영역을 만들어 tick 마다 안의 적에게 피해, 안의 적 탄환 제거.
  snapshot 최상위 `"zones": [{"kind": "storm", "x", "w", "h", "t", "ttl"}]` (x = 영역 중심, 바닥 기준 높이 h).
- 상점: `STATES` 에 `"shop"`. stage_clear 2초 뒤 진입. 좌우로 고르고 confirm 으로 구매 / "다음 스테이지". 강화: damage(+1), rate(+20%), shield(+1), life(+1). 가격 = cost × growth^레벨, config `"shop": {key: {label, cost, growth, max}}` 로 조정. 산 점수는 차감.
  강화는 게임 한 판 동안 유지, `save_data()["upgrades"]` 에 저장되어 '이어하기' 에서 복원.
- snapshot `hud` 추가 키: `"melee_t"`, `"skill_label"`, `"skill_cd"`, `"char_locked": [bool×CHAR_KEYS]`, `"shop": {"index", "items": [{key,label,cost,level,max,afford}], "msg"} | None`.

추가(v1.5, additive): 원격 업데이트 — 게임 로직(World)과 무관, 통합 계층(molgam)만 사용.
- `version.py`: `VERSION`, `REPO`. 릴리스 태그는 `"v" + VERSION`.
- `updater.py`: `Updater(exe_path|None, repo, current, enabled)` — `check_async()`, `start_install() -> bool`, `state`, `notice() -> str|None`. 모듈 함수 `cleanup(exe)`, `restart(exe)`, `merge_missing(dst, src) -> bool`.
- overlay 논리 키 `'update'`(U) 추가. molgam 이 가로채며 World 에는 전달하지 않는다.
- molgam 은 exe 옆 `config.json`/`stages.json` 을 읽을 때 동봉본에만 있는 키를 채워 넣어 저장한다.

---

## B. `overlay.py`

```python
class Overlay:
    def __init__(self, hotkey: str = "shift+0", on_toggle=None, on_quit=None):
        """tk.Tk 루트 생성. 투명 클릭통과 오버레이, topmost, 테두리 없음, 작업표시줄/Alt+Tab 미노출.
        hotkey 문자열: "shift+0", "ctrl+shift+f12", "alt+`" 등. 파싱 실패 시 ValueError."""
    root: "tk.Tk"
    canvas: "tk.Canvas"          # 배경색 == trans_color, 하이라이트 두께 0
    trans_color: str             # 예: "#010203". 이 색은 투명 처리되므로 그리기에 사용 금지
    x: int; y: int; w: int; h: int   # 현재 밴드 사각형(화면 좌표, 물리 픽셀)
    visible: bool
    def place_on_cursor_monitor(self) -> bool:
        """커서 위치 모니터의 작업영역(rcWork, 작업표시줄 제외) 하단 1/3, 가로 전체로 창 이동/크기 조정.
        캔버스 크기도 갱신. 크기가 바뀌었으면 True."""
    def show(self) -> None:      # 재배치 + deiconify + 포커스 획득(SetForegroundWindow, 필요 시 AttachThreadInput)
    def hide(self) -> None:      # 직전 포그라운드 창 기억 → withdraw → 그 창에 포커스 반환
    def toggle(self) -> None:
    def poll(self) -> None:      # 매 틱 호출. WM_HOTKEY 감지 시 toggle() 후 on_toggle(self.visible) 호출
    def bind_keys(self, on_down, on_up) -> None:
        """on_down(key: str), on_up(key: str). key는 정규화된 논리 키:
        'left','right','up','down','jump','fire','pause','quit','confirm','sel_left','sel_right'
        매핑: ←→↑↓, jump=↑/Z, fire=Space/X, pause=P, quit=Escape, confirm=Enter, sel_*=←→(선택 화면에서 game이 해석)
        (v2.0: Space 는 fire 만 보낸다 — game 이 메뉴에서 fire 도 확정으로 받으므로 confirm 을 같이 보내면 확정이 두 번 된다)"""
    def destroy(self) -> None:   # 핫키 해제, 창 파괴
```

구현 메모: `overrideredirect(True)`, `attributes("-topmost", True)`, `attributes("-transparentcolor", trans_color)`.
`GWL_EXSTYLE`에 `WS_EX_TOOLWINDOW` 추가, `WS_EX_APPWINDOW` 제거(작업표시줄·Alt+Tab 제외). DPI: `SetProcessDpiAwarenessContext(-4)` 또는 `SetProcessDpiAwareness(2)` 시도 후 폴백.
핫키: `RegisterHotKey` + `PeekMessageW(PM_REMOVE, WM_HOTKEY)` 폴링. 전역 키보드 후킹(WH_KEYBOARD_LL) 금지.

---

## C. `game.py` + `stages.json` + `config.json`

```python
CHAR_KEYS = ["jaehwi", "hyunki", "dongil"]

class World:
    def __init__(self, stages: dict, config: dict, save: dict, width: int, height: int, seed: int | None = None): ...
    state: str   # "select" | "play" | "stage_clear" | "game_over" | "paused" | "continue"
    def resize(self, width: int, height: int) -> None:
    def key_down(self, key: str) -> None   # overlay.bind_keys 의 논리 키 그대로
    def key_up(self, key: str) -> None
    def update(self, dt: float) -> None    # dt 초. 최대 0.05로 클램프해서 처리
    def snapshot(self) -> dict:
        """그리기 전용 읽기 스냅샷. 구조:
        {
          "state": str,
          "ground_y": int,
          "platforms": [(x, y, w, h), ...],
          "pits": [(x, w), ...],
          "player": {"x": float, "y": float, "anim": str, "frame": int, "flip": bool, "palette": str,
                     "scale": 2, "invincible": bool, "visible": bool},
          "enemies": [{"id": int, "x", "y", "anim", "frame", "flip", "palette", "scale": 2|4|6,
                       "label": "대리", "hp": int, "hp_max": int, "boss": bool}, ...],
          "bullets": [{"x", "y", "w", "h", "owner": "player"|"enemy"}, ...],
          "effects": [{"kind": "hit"|"spark"|"text", "x", "y", "t": float, "text": str|None}, ...],
          "hud": {"lives": int, "score": int, "best": int, "stage_no": int, "stage_name": str,
                  "difficulty": "easy"|"normal"|"hard", "boss_hp": int|None, "boss_hp_max": int|None,
                  "banner": str|None, "banner_t": float,
                  "char_name": str, "select_index": int, "char_names": [str, str, str],
                  "continue_stage": int|None},
        }
        x,y = 발바닥 중앙(앵커). 그리기 계층은 sprites.anchor() 로 보정."""
    def save_data(self) -> dict     # cache.dat 에 쓸 JSON. {"stage", "best", "char", ...}
```

추가(v1.1, additive): snapshot에 `"items": [{"x","y","kind","t"}]` (kind: laser/homing/spread/rapid/life), bullets에 `"kind"` (normal/laser/missile), hud에 `"weapon"`, `"weapon_label"`, `"weapon_left"`. stages.json에 `"progression"` 블록(hp_per_stage, boss_hp_per_stage, drop_grunt, drop_elite).

키 처리: `select` 상태에서 `sel_left/sel_right/left/right`로 캐릭터 순환, `confirm/fire`로 시작. `continue` 상태에서 `left/right`로 이어하기/처음부터, `confirm`. `play`에서 `pause` 토글. 오버레이가 숨겨질 때 통합 레이어가 `paused`로 전환(`World.set_paused(True/False)` 제공).

### stages.json 스키마 (C가 작성, 값은 PLAN.md 2.3/2.4 따름)

```json
{
  "departments": [
    {"name": "총무팀", "waves": 3, "grunts": ["intern","staff"], "elites": [], "boss": "teamlead", "boss_title": "총무팀장", "platforms": 1, "pits": 0, "lab": false},
    ...
  ],
  "executive_stages": [ {"name": "실장단", "bosses": ["director","director","director"], ...}, {"name": "상무·전무", ...}, {"name": "CEO", ...}, {"name": "회장", ...} ],
  "ranks": {"intern": {"title": "인턴", "hp": 1, "speed": 40, "fire_rate": 0.1, "score": 100}, ...},
  "difficulty": {"easy": {"hp": 1.0, "speed": 1.0, "count": 1.0}, "normal": {...}, "hard": {...}}
}
```

### config.json 기본값 (C가 작성)

```json
{
  "hotkey": "shift+0",
  "characters": {
    "jaehwi": {"name": "이재휘", "trait": "민첩", "damage": 1.0, "speed": 1.3, "fire_rate": 1.5, "jump": 1.2, "pierce": false},
    "hyunki": {"name": "문현기", "trait": "힘",   "damage": 2.0, "speed": 0.9, "fire_rate": 1.0, "jump": 1.0, "pierce": false},
    "dongil": {"name": "석동일", "trait": "지능", "damage": 1.0, "speed": 1.0, "fire_rate": 1.0, "jump": 1.0, "pierce": true, "show_enemy_hp": true}
  },
  "lives": 3,
  "fps": 30,
  "save_file": "cache.dat"
}
```

`python game.py --selftest` 는 창 없이: 스테이지 전이, 보스 처치→클리어, 사망→목숨 감소→게임오버, 저장/복원 라운드트립을 검증하고 exit code 0.

---

## 통합 (`molgam.py`, 메인 스레드 담당)

```
Overlay(hotkey=config["hotkey"], on_toggle=...) → SpriteBank(overlay.root) → World(...)
tick: overlay.poll(); world.update(dt); draw(world.snapshot()); root.after(1000//fps, tick)
```
그리기 계층은 Canvas 아이템을 재사용(엔티티 id별 image item 풀, coords/itemconfig 갱신).

---

추가(v1.6, additive): 스탯 · 속성(사신) · 중간 보스. 팀 A(에셋/sprites) · B(game) · C(molgam 렌더러) 병렬. 아래 계약을 바꾸지 말 것, 추가만 허용.

### 스탯 (B)
- config 캐릭터 항목 `"stats": {"agi": int, "str": int, "int": int}` (민첩/힘/지혜, 1~10, 기준 5). 없으면 기존 `speed/jump/damage` 키를 그대로 쓴다.
- 파생치(game.py 상수): 이동속도 배율 `1 + 0.06*(agi-5)`, 점프 배율 `1 + 0.04*(agi-5)`, 물리 피해 `max(1, str//3)` (+상점 damage), 마법 피해 `int//3`.
- 총알·근접·스톰 피해 = 물리 + 마법×속성배율. 물리는 속성 무관.

### 속성 (B, C)
- `ELEMENT_KEYS = ["cheongryong", "baekho", "jujak", "hyeonmu"]` (청룡·백호·주작·현무). config `"elements": {key: {"name", "color": "#rrggbb", "beats": key}}`, `"element_mult": {"strong": 1.5, "weak": 0.5}`.
  상성: 청룡→현무→주작→백호→청룡 (앞이 뒤를 이김). 공격 속성이 대상 속성을 이기면 strong, 지면 weak, 그 외 1.0. 대상이 무속성(None)이면 1.0.
- 플레이어: 선택 화면에서 `up/down` 으로 속성 순환. `save_data()["element"]` 저장·복원.
- 적: 스폰 시 rank 항목 `"element"`(고정) 또는 `ELEMENT_KEYS` 무작위. 보스도 동일. 적 탄환은 속성 배율 없음(플레이어는 목숨제).
- snapshot: `player["element"]: key|None`; enemies 각 항목 `"element": key|None`; hud `"element": key`, `"element_name": str`, `"element_names": [str×4]`, `"element_index": int`,
  `"stats": {"agi","str","int"}`, `"char_stats": [{"agi","str","int"}|None × CHAR_KEYS]`, `"element_colors": {key: "#rrggbb"}`.
  effects 에 `"kind": "elem"`(속성 피격, text = 배율 표시 "강!"/"약" 또는 None) 추가.
- 렌더: 플레이어 발밑 타원 오라 + 몸 뒤 반투명 링(색 = element_colors). 적은 발밑 작은 색 링. 선택 화면에 스탯 3줄 + 속성 행(↑↓).

### 중간 보스 (A, B, C)
- 에셋: `assets_boss.py` (생성물, `tools/import_boss_sheets.py` 가 `적/여자 보스.png`, `적/남자 보스.png` 에서 생성).
  `BOSS_FRAMES[key][frame_id] = (w, h, ax, ay, rgba)` — CHAR_FRAMES 와 같은 형식, 1x, 오른쪽 보기, 앵커 = 발 중앙(불투명 bbox 하단 중앙).
  `BOSS_ANIMS[key] = {"idle","run","attack","attack2","hurt","death","jump": [frame_id...]}` (필수 7키), `BOSS_ANIM_FPS[key] = {anim: fps}`.
  key: `"mai"`(여자 보스), `"choi"`(남자 보스).
- sprites.py: `CHAR_FRAMES` 에 BOSS_FRAMES 병합. `CHAR_ANIMS[palette] = BOSS_ANIMS[key]` 노출. `SpriteBank.get/size/anchor` 는 팔레트에 전용 ANIMS 가 있으면 그것을 쓰고,
  없는 anim 은 별칭으로 대체: shoot→attack, shoot_run→run, fall→jump, crouch→idle, crouch_shoot→attack, victory→idle, 그 외→idle.
  `anim_len(anim, palette=None)` 팔레트 인자 추가(기본값 None = 공용). `frame_time` 도 동일.
- game: stages.json `"ranks"` 에 `"boss_mai"`, `"boss_choi"` (`"sprite": "mai"|"choi"` → e.palette, `"hit_w"`, `"hit_h"` 논리 히트박스 px, `"boss_scale": 2`, `"pattern": "brawler"`, `"element"`).
  stages.json `"mid_bosses": [{"rank": "boss_mai", "title": "...", "from_stage": 2}, ...]`. waves ≥ 2 인 스테이지에서 `waves//2` 웨이브를 끝낸 뒤 자격 있는 중간 보스를 스테이지 번호로 번갈아 스폰(phase `"midboss"`), 처치하면 남은 웨이브 진행. 사망 시 중간 보스부터 재시작.
  brawler 패턴: 접근 → 사거리 안이면 `attack`(근접, 애니 중 접촉 피해) / 원거리 `attack2`(투사체 1발) / 가끔 플레이어 쪽 점프. 피격 시 `hurt` 잠깐.
  enemies 항목 `"mid": bool` 추가. hud `"boss_hp"` 는 중간 보스에도 표시.

---

추가(v1.7, additive): 밸런스 · 스테이지 보스 교체 · 투사체 스프라이트 · 장비 · 스탯 상점. 팀 A(에셋/sprites) · B(game/config/stages) · C(molgam). 바꾸지 말고 추가만.

### 에셋 (A)
- `적/뚱뚱보 보스.png` → key `"chang"` (쇠공 든 거구). `BOSS_FRAMES/BOSS_ANIMS/BOSS_ANIM_FPS["chang"]` 7키 동일 + 모든 보스에 8번째 anim `"proj"` (투사체 스프라이트, 1~4프레임, 오른쪽으로 날아가는 방향 기준):
  mai = 날아가는 부채(시트의 빙글 도는 부채 셀), choi = 손톱 베기 바람 이펙트, chang = 쇠공(사슬 없이 공만). 앵커 = 중앙(ax=w//2, ay=h//2) — 투사체는 중심 기준으로 그린다.
  `BOSS_PROJ = {key: (w, h)}` 노출(1x 픽셀 크기, 히트박스 참고용). 모든 프레임은 오른쪽 보기로 미러링(기존과 동일).
- sprites.py: 변경 없음이 목표. `"proj"` 는 CHAR_ANIMS 로 자동 해석됨.

### 게임 (B)
- 체력: stages.json ranks 의 `hp` ×3, `boss_hp` ×5 (모든 rank). KOF 보스 base boss_hp: mai 30, choi 34, chang 38 (×5 전 값).
- 스테이지 마지막 보스: stages.json `"final_bosses": ["boss_mai", "boss_choi", "boss_chang"]`. 부서 스테이지(waves>0)의 최종 보스 rank = `final_bosses[(stage_no-1) % len]`, 타이틀은 부서의 `boss_title` 유지. 임원 스테이지(executive)는 기존 유지.
- 중간 보스: `"mid_bosses"` 를 기존 팔레트 보스로 교체: `[{"rank":"teamlead","title":"팀장 대행","from_stage":2},{"rank":"general","title":"감사 부장","from_stage":3},{"rank":"deputy","title":"기획 차장","from_stage":4}]` (pattern `"mid"` 기존 보스 AI, e.mid=True, boss_scale 4).
- rank 항목 `"proj": {"speed": 1.2, "w": 40, "h": 20}` 가 있으면 brawler 의 attack2 투사체는 sprite 탄. Bullet 에 `sprite: str|None`(팔레트 key), `anim: str|None`, `frame: int`, `anim_t` 추가. `_update_bullets` 가 anim 을 진행(BOSS_ANIM_FPS 를 모르므로 8fps 고정). rank `boss_chang`: hit_w 64, hit_h 100, proj w 34 h 34 speed 1.0; boss_mai proj 40×22 speed 1.3; boss_choi proj 48×24 speed 1.5.
- snapshot bullets 항목 추가 키: `"sprite": str|None, "anim": str|None, "frame": int, "flip": bool` (flip = vx<0). v2.0: `"vx": float, "vy": float` (px/s, 소수 1자리 — 적탄 잔상 방향용; 히트박스 w/h 는 그대로).
- 아이템: 유도탄 ttl 없음·속도 2배(MISSILE_SPEED 860, 회전 MISSILE_TURN 유지), 3연발 각도 ±5°(0.087 rad), 레이저 dmg 절반(`max(1, (dmg+1)//2)`).
- 장비: config `"equipment": {"hat": {"label":"안전모","shield":1}, "gloves": {"label":"작업 장갑","rate":0.2}, "suit": {"label":"사신 정장","magic":1}, "shoes": {"label":"운동화","speed":0.12,"jump":0.08}}`, 레벨 무제한.
  스테이지 최종 보스(mid 아님, 부서 스테이지)를 잡으면 레벨이 가장 낮은 슬롯(동률이면 hat→gloves→suit→shoes 순) +1, 배너 `"장비 획득 · <label> Lv<n>"` 2초, 텍스트 이펙트. `self.equip = {slot: level}`; `save_data()["equip"]`, 이어하기 시 복원(upgrades 와 같은 방식). 효과는 스탯/실드/연사에 합산.
- 스탯 상점: DEFAULT_SHOP 에서 `"damage"` 제거, `"str"`(힘 +1, 1500, 1.25, max 0=무제한), `"agi"`(민첩 +1, 1500, 1.25, 무제한), `"int"`(지혜 +1, 1500, 1.25, 무제한) 추가. SHOP_ORDER = ("str","agi","int","rate","shield","life","next"). max 0 = 무제한(_shop_view 의 max 는 0 으로 내려보냄). 유효 스탯 = config stats + upgrades[str/agi/int].
  스탯 정의 변경: 힘 → 물리 피해 `max(1, str//3)`; 민첩 → 이동/점프(기존 식); 지혜 → **총알 속도** `BULLET_SPEED × (1 + 0.08×(int-5))` (레이저 제외) **그리고** 마법 피해 `int//3` (속성 피해 유지, + 장비 suit magic).
- hud 추가: `"equip": {slot: level}`, `"equip_labels": {slot: label}`, `"stats"` 는 유효 스탯(상점 포함), `"shop"["stats"]: {"str","agi","int"}` (상점 화면 표시용).

### 렌더 (C)
- bullets 에 `sprite` 가 있으면 사각형 대신 `bank.get(anim, frame, sprite, flip, 1)` 이미지(중심 앵커: x - w/2, y - h/2). 이미지 아이템 풀 별도 유지. 없으면 기존 사각형.
- HUD: 장비 한 줄 `"장비: 안전모 Lv1 · 운동화 Lv2"` (레벨 0 제외, 없으면 표시 안 함). 상점 화면: 상단에 `힘 N · 민첩 N · 지혜 N` 현재 유효 스탯 표시, 항목 라벨 그대로, max 0 이면 "Lv n" 만 표시(max 없음).
- 선택 화면 스탯 설명 한 줄: `"힘=공격력 · 민첩=이동/점프 · 지혜=탄속/마법"`.

추가(v1.8, additive): 템포 · 적 움직임 다양화 · 등장 경고 · 연출. 시그니처 변경 없음.

### 게임 (B)
- 적 이동 속도 = rank speed × 난이도 speed × `_enemy_speed_mult()` = `ENEMY_SPEED_BASE(2.0) × min(ENEMY_SPEED_STAGE_CAP(3.0), 1.1^(stage_no-1))`. 보스 포함.
- 대기 시간 절반: `DEFAULT_WAVE.spawn_stagger` 0.3, `WAVE_GAP` 0.5, `BOSS_GAP` 0.5, `BOSS_NEXT_GAP` 0.6, `CLEAR_TO_SHOP` 1.0. 스테이지 시작 무적 1.5초.
- `pending` 항목은 `(rank, side, spawn_kind)` 3-튜플. spawn_kind ∈ {"side","ground","sky"}; 웨이브 첫 슬롯은 항상 side, 이후 슬롯은 `SPECIAL_SPAWN_BASE + SPECIAL_SPAWN_PER_STAGE×(stage-1)` (최대 0.55) 확률로 ground/sky.
- `World.warnings: [{"kind","x","t","ttl","rank"}]` — ground/sky 스폰은 먼저 경고(`WARN_T` 0.9/1.0초)를 만들고, 만료 시 `_update_warnings` 가 적을 생성. ground: `y = ground_y + h + 4`, 위로 `sqrt(2g(h+4+POP_EXTRA))` 로 솟음(바닥 아래는 밴드 하단이 잘라줌). sky: `y = SKY_Y(-60)`, `drop=True` 로 낙하. 착지 시 `land_t = LAND_STUN(0.3)` 정지 + "dust" 이펙트. 낙하 중 몸(vy>0) / 솟는 중 몸(vy<0)이 플레이어와 겹치면 `_hit_player()`.
- `Enemy` 슬롯 추가: `move_mode`("walk"|"sprint"|"pause"), `move_t`, `land_t`, `drop`, `spawn_kind`. `_Ent.anim_rate`(질주 시 SPRINT_MULT). 잡병·정예 접근은 `_approach()` 가 `MOVE_WEIGHTS`(walk 55 / sprint 25 / pause 20)로 모드를 갈아탐. 밴드 밖·연속 pause 금지.
- 웨이브 종료 조건에 `not self.warnings` 포함. 스테이지 시작·사망·클리어 때 warnings 비움.
- snapshot 추가: 최상위 `"warnings": [{"kind","x","t","ttl"}]`; enemies 항목 `"sprint": bool`, `"drop": bool`; effects kind `"dust"`(ttl 0.35).

### 렌더 (C)
- 플레이어 속성 오라: 발밑 타원·링 제거 → 불꽃 폴리곤 3층(smooth) + 불씨 6개. 색 = `hud.element_colors[element]`.
- 적 속성 링 → 발밑 작은 불꽃 폴리곤 1개(키 "ring" 유지).
- `warnings` 표시: ground = 바닥 점선 브래킷 + `!` + 금, sky = 상단 `▼` + 착지 그림자 + 세로 가이드선. `u = 1 - t/ttl` 로 색(노랑→빨강)·점멸 가속.
- effects "dust" = 회색 타원 3개 확산. enemies `sprint` = 뒤쪽 속도선 3개, `drop` = 바닥 착지 그림자.
- 서류 스톰 영역: 점선 사각형 → 회오리 깔때기 폴리곤 + 바람 링 + 궤도를 도는 종이 폴리곤(`PAPERS_PER_ZONE` 14), 마지막 0.4초 축소.

추가(v1.9, additive): 아이템 10종 + 인벤토리 · 캐릭터별 근접 · 적 근접 · 새 적 5시트 · 돈/장비/창고/마을/도박 · 난이도 6종 · 낙하 타자 단어. 팀 A(에셋) · B(economy.py) · C(molgam 렌더) · 로직(game.py). 시그니처 변경 금지, 추가만. 모든 수치는 `config.json` 으로 덮어쓸 수 있게 DEFAULT_* 상수로.

### 에셋 (A) — `tools/import_enemy_sheets.py` → `assets_enemy.py` (손수정 금지)
- 소스와 key. 파랑(#1a3a8a 계열) 또는 마젠타(#ff00ff) 배경 시트. 셀은 배경이 아닌 픽셀의 연결 성분 bbox(행 밴드 → 열 런). 모든 프레임 오른쪽 보기로 통일(원본이 왼쪽 보기면 미러). 1px 어두운 윤곽선(import_boss_sheets.py 규칙). 앵커 = bbox 하단 중앙, `proj*` 는 중앙.
  - `적/적 (1).png` → `"dino"`(파랑 갑주 공룡). 같은 시트의 빨강/금 색 변형 행은 각각 `"dino_red"`, `"dino_gold"` 의 **idle/run/attack 프레임**으로 쓰고 나머지 anim 은 dino 프레임을 팔레트 재색(hue shift)해서 채운다. `proj` = 화염탄(불꽃 구), `proj2` = 화염 브레스 길쭉한 불줄기.
  - `적/적 (3).png` → `"golem"`(금색 바위 골렘), 변형 `"golem_blue"`, `"golem_green"`. `proj` = 바위(구형 돌), `proj2` = 초록 독 구.
  - `적/적 (4).png` → `"slime"`(초록 슬라임 괴수), 변형 `"slime_red"`, `"slime_blue"`. `proj` = 점액 방울(작은 타원 모션 3프레임, 없으면 몸 뭉침 프레임 축소).
  - `적/적 (2).png` → `"mario"`(작은 마리오 행), `"luigi"`(작은 루이지 행), `"mario_fire"`(파이어 마리오 슈퍼 크기). 시트 배경은 파랑(#5c94fc 계열) — 배경색은 (0,0) 픽셀로 잡는다. `proj` = 파이어볼(없으면 4프레임 회전 주황 원 합성).
  - `적/적 (1).gif` → `"bomber_w"`(흰 봄버맨), `"bomber_b"`(검은 봄버맨). 마젠타 배경. `proj` = 폭탄(검은 구 + 도화선, 있으면 시트에서, 없으면 16×16 합성 3프레임 깜빡임).
- 출력: `ENEMY_FRAMES[key][frame_id] = (w, h, ax, ay, rgba)` (1x), `ENEMY_ANIMS[key] = {"idle","run","attack","attack2","hurt","death","jump","proj"(,"proj2")}` — 시트에 없는 anim 은 가장 가까운 것으로 채워 **키는 반드시 존재**(attack2 없으면 attack, jump 없으면 run 1프레임 등). `ENEMY_ANIM_FPS[key]`, `ENEMY_PROJ[key] = {"proj": (w,h), "proj2": (w,h)}`, `ENEMY_HIT[key] = (hit_w, hit_h)` (idle 프레임 bbox 기준, 1x). frame_id = `<key>_<anim>_<n>`.
- `sprites.py`: `CHAR_FRAMES/CHAR_ANIMS/CHAR_ANIM_FPS` 에 `assets_enemy` 병합(`import` 실패 시 빈 dict 로 폴백). `__all__` 에 `ENEMY_PROJ`, `ENEMY_HIT` 추가.
- `--contact` 로 라벨 붙은 컨택트 시트를 `tools/contact/<key>.png` 에 저장(셀 (row,col) 인덱스 표기). 프레임 표 `CELLS` 는 컨택트 시트를 **직접 보고** 고른다. 각 anim 미리보기 스트립도 `tools/contact/<key>_<anim>.png`.
- 크기 참고: 게임은 잡병 scale 2, 이 몬스터들은 1x 원본이 이미 크므로 stages.json rank 에 `"scale": 1` 로 두고 마리오/봄버맨(작음)은 `"scale": 2`.

### 경제 (B) — 새 모듈 `economy.py` (순수 로직, random.Random 주입, tkinter 금지, `python economy.py --selftest`)
```python
SLOTS = ("hat","gloves","suit","shoes","weapon","acc")   # 안전모·작업 장갑·사신 정장·운동화·사무용 무기·사원증
SLOT_LABEL = {"hat":"안전모","gloves":"작업 장갑","suit":"사신 정장","shoes":"운동화","weapon":"사무용 무기","acc":"사원증"}
RARITY = ("normal","rare","unique"); RARITY_LABEL = {"normal":"일반","rare":"레어","unique":"유니크"}
RARITY_MULT = {"normal":1.0,"rare":1.8,"unique":3.0}      # 슬롯 고유 효과 배수 (스탯은 RARITY_STAT_MULT {1.0/1.5/2.0} — v2.0)
MAX_LEVEL = 20
SHOP_RARITY = {"normal":0.90,"rare":0.08,"unique":0.02}   # 상점 목록
BOSS_RARITY = {"normal":0.85,"rare":0.12,"unique":0.03}   # 보스 드롭 / 타자 단어 보상은 {"normal":0.4,"rare":0.4,"unique":0.2}
BOX_RARITY  = {"normal":0.70,"rare":0.22,"unique":0.08}   # 랜덤박스
ROLL_RANGE = (0.7, 1.3)                                    # 스탯 ±30%
# 슬롯 고유 효과: 레벨당 증가량(일반 기준). 실제 = base_per_level * level * RARITY_MULT[rarity] (+ level 0 도 base_flat)
SLOT_EFFECT = {"hat": ("shield", 0.25, 1.0),      # (effect key, per level, flat)  → 실드 = round(flat + per*lv*mult)
               "gloves": ("rate", 0.02, 0.0),     # 연사 +2%/lv
               "suit": ("magic", 0.25, 0.0),      # 마법 피해 +0.25/lv (반올림)
               "shoes": ("speed", 0.01, 0.0),     # 이동 +1%/lv (점프 = speed*0.6)
               "weapon": ("damage", 0.2, 0.0),    # 물리 피해 +0.2/lv (반올림)
               "acc": ("money", 0.02, 0.0)}       # 돈 드롭 +2%/lv
def make_equipment(rng, slot, rarity, level=0, stage=1) -> dict
#   {"id": str(uuid-ish/rng hex), "slot", "rarity", "level", "name": "<접두어> <슬롯라벨>", "roll": 0.7~1.3,
#    "stats": {"str": int, "agi": int, "int": int}, "perks": [str]}  — stats 기본 합 = 1 + stage//4, 셋 중 랜덤 분배, × roll × RARITY_STAT_MULT, 반올림; perks normal 0 / rare 1 / unique 2 (v2.0)
def equip_effect(eq) -> dict   # {"shield":int,"rate":float,"magic":int,"speed":float,"jump":float,"damage":int,"money":float,"str":int,"agi":int,"int":int}
def total_effect(equipped: dict[str, dict|None]) -> dict   # 슬롯 합산, 키 전부 존재
def upgrade_cost(eq) -> int          # 300 * 1.12**level * RARITY_COST[rarity](1/1.5/2.5), 레벨 20 이면 0(불가) — 도박 기준가
def enhance_cost(eq, perks=None) -> int   # v2.0 확정 강화 비용: 300 * 1.12**level * ENHANCE_RARITY_COST(1.6/2.6/4.5), 'haggler' 퍼크 ×0.8(레어) / ×0.65(유니크), 레벨 20 이면 0
def enhance(eq, money, perks=None) -> tuple[dict, int, str, bool]   # v2.0 확정 +1 (입력 eq 불변). 돈 부족 / MAX_LEVEL 이면 ok False, 문구만
def buy_price(eq, stage) -> int      # (600 * RARITY_PRICE(1/4/15) + 120*level) * (1 + 0.06*(stage-1))
def sell_price(eq, stage) -> int     # buy_price * 0.4
def roll_rarity(rng, table) -> str
def make_shop_stock(rng, stage, n=10) -> list[dict]   # SHOP_RARITY, 슬롯 랜덤, level 0~min(5, stage//3)
BOX_PRICE = lambda stage: int(900 * (1 + 0.06*(stage-1)))
def open_box(rng, stage) -> dict     # {"kind": "equip"|"item"|"money"|"dud", "equip": dict|None, "item": str|None, "money": int}
#   60% equip(BOX_RARITY) / 25% item(ITEM_KINDS 중 랜덤, 1UP 제외 가중) / 10% money(BOX_PRICE*0.5~3.0) / 5% dud("꽝 · 사탕 하나")
def gamble_upgrade(rng, eq, money) -> tuple[dict, int, str]   # cost = upgrade_cost*1.5; 60% +2lv(최대 20) / 30% 변화 없음 / 10% -3lv(유니크는 -1lv, GAMBLE_UPGRADE_DOWN_UNIQUE; Lv 0 이면 "변화 없음" 문구). 반환 (eq, 잔액, 결과 문구). 돈 부족이면 문구만
def gamble_double(rng, stake, streak) -> tuple[bool, int]      # 50% 성공 → 배당 stake*2, 연속 성공 시 x2 누적(최대 x8) ; 실패 → 0
SLOT_SYMBOLS = ("₩","★","◆","♥","7")
def gamble_slots(rng, bet, stage) -> dict   # {"reels": [s,s,s], "payout": int, "prize": None|{"kind":"item"|"equip", ...}, "text": str}
#   확률: 3개 동일 7 = 잭팟 bet*30 + 유니크 장비 / 3개 동일 ★ = 레어 장비 / 3개 동일 ₩ = bet*10 / 3개 동일 ◆·♥ = bet*5 / 2개 동일 = bet 반환 / 그 외 0. 기댓값 ≈ 0.85*bet
class Warehouse:  # 창고 24칸 + 장착 6슬롯
    CAP = 24
    def __init__(self, data: dict|None): ...   # data = save_data 형식
    items: list[dict]; equipped: dict[str, dict|None]
    def add(self, eq) -> bool                   # 꽉 차면 False
    def equip(self, idx) -> dict|None           # 창고 idx 를 장착, 기존 장착품은 창고로 (자리 없으면 실패 None)
    def unequip(self, slot) -> bool
    def remove(self, idx) -> dict
    def effect(self) -> dict                    # total_effect(equipped)
    def to_save(self) -> dict                   # {"items": [...], "equipped": {slot: eq|None}} — stats dict / perks list 는 복사(라이브 장비와 공유 없음)
def money_drop(rng, kind: str, stage: int, diff_mult: float, acc_bonus: float) -> int
#   kind grunt 20~40 / elite 60~100 / mid 250 / boss 600 / word 400 ; × (1 + 0.05*(stage-1)) × diff_mult × (1+acc_bonus)   (v2.0 MONEY_KIND / MONEY_STAGE_GROWTH)
```
- 밸런스 목표: 보통 난이도 50스테이지 누적 드롭 ≈ 20만 ₩, 6슬롯 20레벨 전부 강화 ≈ 13만 ₩. selftest 에서 기대값 시뮬로 검증(오차 ±25%).
- 난이도 표(게임이 참조): `DIFFICULTY = {"easy":0.7,"normal":1.0,"hard_":1.3,...}` 는 game.py 가 가진다(B 는 diff_mult 만 받음).

### 로직 (game.py) — 스냅샷/키 계약 (C 가 그린다)
- 논리 키 추가(overlay `_KEYMAP`): `"1".."5"` → `"slot1".."slot5"`; 알파벳 a~y 중 게임 키가 아닌 것 → `"char:<letter>"` (타자용). overlay 는 keysym 이 한 글자 소문자 알파벳이고 `_KEYMAP` 에 없으면 `char:<letter>` 를 보낸다. 마을 화면용 `"tab"` → `"tab"`.
- `World.STATES` 에 `"town"` 추가(5의 배수 스테이지 클리어 → 상점 대신 마을; 마을 안에 스탯 탭 포함).
- 난이도: `DIFFICULTIES = ["easy","normal","hard","harder","hell","crazy"]`, 라벨 쉬움/보통/어려움/하드/헬/크레이지, 배수 `{"easy":0.7,"normal":1.0,"hard":1.3,"harder":1.6,"hell":2.2,"crazy":3.0}` → 적 HP·투사체 속도·돈 배수 그대로, 이동 속도는 `1 + (m-1)/2`. 선택 화면에서 `skill`(C) 키로 순환. 잠김: hell = 어느 난이도로든 20스테이지 클리어, crazy = hell 로 30스테이지 클리어. save: `"best_clear": {diff: int}`, `"difficulty": str`. 무한 모드 로테이션 폐지(라벨은 선택 난이도).
- snapshot 추가 키:
  - `hud["money"]: int`, `hud["difficulty_label"]: str`, `hud["difficulty_locked"]: [bool×6]`, `hud["difficulty_index"]: int`
  - `hud["inventory"]: [{"kind": str, "count": int} | None] ×5`, `hud["inv_flash"]: int|None` (방금 쓴/얻은 슬롯 0~4, 0.4초)
  - `hud["melee_style"]: "knife"|"hammer"|"whip"|"hip"`, `hud["melee_hit"]: int` (콤보 타수 1~3)
  - `hud["slow_t"]: float` (야근 커피 남은 초, 0 이면 없음), `hud["equip_effect"]: dict` (economy.total_effect), `hud["equipped"]: {slot: eq|None}`
  - `hud["town"]: None | {"tab": "stat"|"shop"|"store"|"gamble", "tabs": [라벨×4], "index": int, "msg": str, "stage": int,
        "stat": {"items": [...기존 shop items...]}, "shop": {"stock": [eq|{"kind":"box","price":int}...10+1], "afford": [bool]},
        "store": {"items": [eq...], "equipped": {slot: eq|None}, "mode": "list"|"equipped"}, 
        "gamble": {"games": ["강화 도박","더블업","슬롯"], "game": int, "stake": int, "streak": int, "reels": [str×3]|None, "target": int|None, "text": str(마지막 슬롯 결과 문구; 탐색해도 남는다)}}`
    마을 조작: `tab`(Tab) 또는 `up/down` = 탭 전환, `left/right` = 항목, `confirm` = 실행(구매/장착/강화/도박), `skill`(C) = 보조(창고: 판매 / 상점: 박스 열기 대신 없음 / 더블업: 스테이크 변경), `down` 은 창고에서 장착↔목록 모드 전환, 마지막 항목 "다음 스테이지".
  - 최상위 `"allies": [{"kind": "decoy"|"drone"|"dog", "x","y","anim","frame","flip","palette","t","ttl"}]` — decoy 는 플레이어 팔레트로 그림(회색 반투명 느낌은 렌더가 dim 처리), drone/dog 는 렌더러 내장 픽셀아트.
  - 최상위 `"words": [{"text": str, "typed": int, "x": float, "y": float, "kind": "wipe"|"gear"|"money"|"life", "t": float, "vy": float}]` — 스테이지마다 정확히 2번(웨이브 중 랜덤 시점), 위(-20)에서 `vy` ≈ 34px/s 로 낙하, 바닥 도달 시 소멸. 글자 = 소문자 영문(z,x,c,p,u,r 제외; 3~7자), kind 별 단어 사전. 완성 시: wipe = 화면 적 전멸(보스 HP 20%), gear = 장비 드롭(창고, RARITY 0.4/0.4/0.2), money = 돈, life = 목숨+1. 이펙트 `"word"` kind.
  - bullets 항목 추가: `"gravity": bool`(포물선 투사체: 폭탄·바위), `"r": float`(반지름, 폭발 원용), kind 추가 `"bomb"`(플레이어 결재 폭탄 낙하물), `"blast"`(폭발 원, 짧은 ttl, r 커짐), `"wave"`(현기 해머 지면 충격파, 바닥을 따라 진행).
  - effects kind 추가: `"slash"`(근접 궤적: text 에 style), `"word"`, `"coin"`(돈 획득 +N 텍스트, 금색), `"boxopen"`.
  - enemies 항목 추가: `"attack": bool`(근접 공격 중), `"slow": bool`.
  - items 항목 `kind` 확장: `"laser","homing","spread","rapid","life","bomb","coffee","decoy","drone","dog","coin"` (coin = 바닥에 떨어진 돈, `"value": int` 추가).
- 인벤토리: 5칸, 같은 kind 는 겹침(최대 3). 주우면 즉시 적용하지 않고 슬롯에 저장, coin 은 즉시 돈. 꽉 차고 겹칠 수 없으면 못 주움(아이템은 바닥에 남음). `slotN` 으로 사용: 무기류 = 지속시간 시작, life = 목숨+1, bomb = 화면 전체 폭발(잡병 즉사·보스 15%·적 탄 제거), coffee = 6초 슬로우(적·적탄 40% 속도), decoy = 분신 8초(자리에 서서 자동 사격, 적 조준 50% 분신), drone = 15초 머리 위 드론 초당 3발 유도, dog = 찹츄 10초(바닥 달려가 근접, 물기 데미지 2, 넉백).
- 근접(자동 전환): fire 시 사거리 안에 적이 있으면 근접. config 캐릭터 `melee` 확장 `{"style","range","damage","knockback","cooldown","hits"(콤보 수),"pierce"(범위 내 전부),"wave"(true 면 지면 충격파 탄)}`. 재휘 knife(3연타 0.15s 간격, 3타째 넉백 300), 현기 hammer(느림 0.6s, 넉백 420, wave), 동일 whip(사거리 95, pierce, 마법 피해 = int//3), 복면 hip(기존).
- 적 근접: 모든 잡병·정예에 `reach = w*0.6+22`. 사거리 안이면 `attack_t` 0.45s, 창 (0.15~0.3) 에 겹치면 `_hit_player()`. 팔레트 적은 anim "shoot" 로 대체, 새 몬스터는 "attack". 근접 쿨 1.0~1.6s. 근접 적은 stop_dist 를 reach 로.
- 새 적 rank(stages.json ranks 추가, 팀 A 의 key): dino(정예, hp 9, speed 90, proj 화염탄, 근접 물기), dino_red(정예, 더 빠름), dino_gold(중간보스 후보), golem(정예 탱커 hp 15, speed 45, proj 바위 포물선 gravity), golem_blue, golem_green(proj2 독), slime(잡병 hp 4, speed 110, 돌진 근접), slime_red/blue, mario(잡병 hp 3, 점프 잦음), luigi(잡병, 더 높이 점프), mario_fire(정예, 파이어볼), bomber_w/bomber_b(잡병, 폭탄 포물선 투척, 착지 후 0.8s 뒤 폭발 r 40). 부서 스테이지 grunts/elites 목록에 5스테이지부터 섞어 넣기(회사 부서 테마는 유지, `"monsters": [...]` 키로 부서마다 1~2종).
- 보스: 점프 vs 대시 확률 1:5(둘 다 가능할 때 대시 5/6). MAX_BULLETS 400(플레이어 사격은 제한 없음, 적 사격만 캡). MISSILE_TURN 14, MISSILE_SPEED 700. SPREAD_ANGLE 0.0436(±2.5°).
- 저장(`save_data`): `"money"`, `"warehouse"`(economy.Warehouse.to_save), `"difficulty"`, `"best_clear"`, `"inventory"`. 게임 오버에도 유지.

#### v1.9 구현 메모 (계약과 다른 점)
- economy: `MONEY_STAGE_GROWTH` 0.08 → 0.05 (50스테이지 누적 ≈ 19만 ₩, v2.0 MONEY_KIND 기준). `BOX_PRICE(stage)` 는 함수. `open_box` 결과에 `"text"` 추가. `WORD_RARITY` 상수 노출. `Warehouse.equip(idx)` 는 기존 장착품을 같은 자리(idx)에 되돌려 놓아 용량 실패가 없다.
- hud["town"] 추가 키: `"tab_index"`, `"count"`, `"hint"`(탭별 조작 안내 문자열), `"money"`, `shop["prices"]`, `store["cap"|"sell"|"upgrade_cost"]`, `gamble["stake_pct"|"bet"|"target_eq"|"target_cost"]`. 마을 조작: `Tab` 탭, `↑↓` = 창고 줄 전환 / 도박 항목 이동 / 그 외 탭 전환, `←→` 항목, `Enter` 실행, `C` 보조(창고 판매 · 도박 대상/배팅 변경).
- 인벤토리 사용 키는 `slot1..slot5`(숫자 1~5, 키패드 포함). 타자는 `char:<letter>` — `z x c p u` 는 게임 키이므로 단어에 안 쓴다(`WORD_LETTERS`).
- 새 rank 키(stages.json): `sheet: true`(자체 시트 → 근접 anim "attack"), `melee: true`, `hit_scaled: true`(hit_w/h × scale), `proj {anim, w, h, speed, aim, gravity, fuse, blast}`, `jump_odds`, `jump_mult`. 부서 `monsters`, 최상위 `monsters_from_stage`(기본 5).
- 밸런스 로그: `World.drain_log()` → 스테이지 종료(클리어/게임 오버)마다 1 dict. molgam 이 `balance_log.jsonl`(세이브 파일 옆)에 한 줄씩 append.
- 무기 상점 재고는 마을 방문(스테이지)마다 새로 뽑고, 그 마을 안에서는 유지된다(`shop_stock_stage`).

#### v2.0 구현 메모 (밸런스·경제·시각 — 계약 변경분)
- 난이도 곡선: `DIFF_CURVE` (game.py, stages.json `"curve"` 로 덮어씀) 는 easy / normal 에만 존재. hp/speed/count/proj/money 를 직접 지정하고 1~3스테이지에 `warmup`(hp·speed) / `count_warmup`(count) 을 곱한다(무한 사이클 보너스 +0.25/+0.05/+0.1 은 그대로). `hp_per_stage`(easy .22 / normal .28) · `boss_hp_per_stage` · `speed_cap`(2.2 / 2.6) 도 곡선에서 가져와 `stage["hp_per_stage"|"boss_hp_per_stage"|"speed_cap"]` 로 빌드 시점에 확정한다. hard / harder / hell / crazy 는 항목이 없으므로 `DIFF_MULT` 공식·progression 0.35·ENEMY_SPEED_STAGE_CAP 3.0 그대로(숫자 불변, selftest 로 고정). stages.json `"difficulty"` 표는 legacy(미사용).
- 돈: `MONEY_KIND` grunt 20~40 / elite 60~100 / mid 250 / boss 600 / word 400 (game.py fallback 표 동일). 부서 최종 보스(mid 아님)는 코인 없이 즉시 `money` 에 가산(+ `"coin"` 이펙트). 잡병·정예·중간보스는 바닥 코인. 스테이지 클리어 시 바닥 코인 전부 자동 회수(배너 접미 ` · 바닥 ₩{n:,} 회수`), 리스폰에도 코인은 남는다(비코인 아이템만 정리). `economy.configure(config["economy"])` 를 World 생성 시 호출. 밸런스 로그 `spent` 에 장비 구매·박스·강화·강화 도박·더블업 스테이크·슬롯 배팅 전부 기록(마을 동안은 `_bal_carry` 에 모아 다음 스테이지 레코드에 합산). 마을의 돈 수입(창고 판매·박스 돈·창고 가득 자동 판매·더블업/슬롯 배당)도 같은 방식으로 `money` 에 이월되어 `World` 의 모든 돈 변동이 기록된다 → 레코드마다 `money_end == 직전 money_end + money_gained - money_spent`. `World.resize()` 는 바닥 아이템(코인)도 지면·너비와 함께 옮긴다(구덩이 위면 가장자리로). `economy.configure` 는 dict 멤버를 기존 값의 모양(tuple / 숫자 / 문자열)에 맞춰 강제하고 안 맞으면 무시한다.
- 바닥 코인: 자동 흡수 없음(`magnet` 퍼크 장착 시에만 COIN_HOME_* 홈잉). `COIN_TTL` 20s, `COIN_PICK_R` 26px(|Δx|, 플레이어 높이 밴드 안), `COIN_MERGE_R` 18px 안의 착지 코인에 합산(TTL 갱신), `MAX_COINS` 16 초과 시 가장 가까운 더미에 합산, 낙하 중 좌우 산개 vx ±70, 구덩이 위 착지는 가장자리(±10px)로 이동. 스냅샷 `items` 는 `MAX_ITEMS + MAX_COINS` 이하(코인 ≤ 16, 비코인 ≤ 10). effects ttl: coin/word 0.8, boxopen 0.6, slash 0.2 (렌더 FX_TTL 과 일치). 렌더 권장: 값 구간별 더미 크기, `₩{value:,}` 라벨, t < `COIN_BLINK_T`(3s) 깜빡임.
- 적탄: bullets `"vx"|"vy"` 추가(BULLET_KEYS). 렌더는 링 코어 + 잔상 등으로 가시성 확보(히트박스 불변).
- 스탯 상점(점수): str/agi/int 1200 × 1.20^lv, rate 2500 × 1.6^lv (max 5), shield 2500 × 1.6^lv (max 3), life 4000 × 1.8^lv (max 3).
- 레거시 장비(config `"equipment"`): 슬롯당 `"max"`(기본 3), 레벨당 hat shield 1 / gloves rate 0.10 / suit magic 1 / shoes speed 0.06·jump 0.04. `_grant_equip` 은 max 슬롯을 건너뛰고, 전부 max 면 `LEGACY_CAP_MONEY`(300)×스테이지 ₩ 를 대신 지급(배너 `"장비 최대 · 보너스 ₩n"`). 이어하기 시 저장 레벨을 max 로 clamp.
- 장비 스탯: economy `RARITY_STAT_MULT` {1 / 1.5 / 2.0} 은 스탯 롤에만, `RARITY_MULT` {1 / 1.8 / 3.0} 은 슬롯 고유 효과에만. `STAT_BASE_SUM` 1, `STAT_STAGE_DIV` 4 (스탯 합 = 1 + stage//4). `WORD_RARITY` 0.60 / 0.32 / 0.08.
- 강화(확정): `economy.enhance_cost(eq, perks)` = 300 × 1.12^lv × `ENHANCE_RARITY_COST` {1.6 / 2.6 / 4.5} (`haggler` 퍼크 ×0.8, MAX_LEVEL 이면 0), `economy.enhance(eq, money, perks) -> (eq, 잔액, 문구, ok)` +1 확정. 도박(`gamble_upgrade`) 은 그대로 upgrade_cost×1.5 기준, 유니크 실패 시 -1. 마을 창고 탭 장착 줄에서 `C` = 강화(창고 줄 `C` 는 판매). `TOWN_HINT["store"]` 갱신.
- hud["town"]["store"] 추가 키: `"enhance_cost": {slot: int}`, `"can_enhance": {slot: bool}`, `"max_level": int`, `"slot_labels": {slot: label}`, `"slot_order": [slot×6]`, `"effect": {slot: equip_effect|None}`, `"effect_next": {slot: +1레벨 equip_effect|None}`, `"items_slot": [slot per items[i]]`, `"total": total_effect`, `"perks": {perk: rank}`, `"perk_labels": {perk: label}`, `"perk_desc": {perk: desc}`, `"perk_ui": {perk: {rarity: text}}`, `"perk_excluded": [perk]`(현재 캐릭터 미적용 키, 정렬). `"upgrade_cost"` 는 도박 패널용으로 유지.
- 퍼크(v2.0 2차 패스): economy.PERKS 19키 `{label, slots, min, value{rare,unique}, ui{rare,unique}, desc}`, 장비 dict `"perks": [str]` (normal 0 / rare 1 / unique 2, 스탯 뒤에 뽑아 기존 seed 의 id/roll/stats 불변), `Warehouse.perks()` = `{key: rank}` (같은 키는 최고 등급 하나 = MAX, 합산 없음; total_effect 에 안 섞임). game.py: `World.perks` 캐시 + `_refresh_perks()` (창고 로드 / `_start_stage` / 마을 장착·해제·판매 / `_gear_to_warehouse` 에서만, 프레임마다 아님), `_perk(key)` = 등급 값(없거나 캐릭터 부적합이면 0), `_perk_mult(key)` = 값 또는 1.0, `_perk_exclusions()` (storm 없음 → ult_time·ult_haste, config pierce → pierce; 보스 드롭·타자 gear·상점 목록·박스·슬롯 모든 롤에 `exclude=` 로 전달), `perk_used` 스테이지당 충전(second_wind 플래그 / pit_save 횟수; `_start_stage` 와 리스폰에 리셋). 훅: magnet(코인 홈잉 160px / 9999=전체·딜레이 0), double_jump(`Player.air_jumps`, 85% 높이, 착지마다 충전), ult_time / ult_haste(`_use_skill`: dur×, cd×, `skill_cd = max(cd, dur+1)`), shield_regen(`regen_t`, 피격 시 리셋), shield_burst(실드 흡수 시 반경/전체 적탄 소거 + dmg 0 blast), second_wind(치명타 1회 버팀, 유니크 실드 회복+탄 소거), loot_luck(드롭 확률 ×, 상한 0.9), melee_reach(사거리 ×, 유니크 both_sides), kill_haste(처치 시 fire_cd 0, 유니크 `haste_t` 2s → `_fire_rate_mult` ×1.3), inv_stack(INV_STACK +n), item_time(무기 시간·유도탄 탄수·커피·동료 ×), keep_weapon(사망 시 무기 유지, 유니크 부활 무적 3.5s; 게임오버에 해제), stomp(`air_top` 기준 40px 낙하 착지 → 양방향 wave), pit_save(`_last_ground_x` 로 복귀; 레어 1회, 유니크 무제한·2회째부터 실드 1), pierce(`Bullet.extra` 레어 +1 / 유니크 pierce=True), crit(`_crit`, 총알·근접만), boss_killer(`_boss_dmg`, 총알·근접·존), haggler(economy.enhance_cost). hud 추가 키: `"perks": [{"key","label","rank","text","used"}]` (활성·최고 등급·유니크 우선, 미적용 키 제외), `"perk_labels": {key: label}`; 스테이지 배너는 퍽 세트가 바뀐 스테이지에만 ` · 퍽: 라벨 · 라벨` 접미. `_gear_to_warehouse` 배너 이름 뒤 ` ★라벨`. 밸런스 로그 `revives`. 렌더(molgam): HUD 점수/장비 줄 아래 퍽 칩 줄(등급 색, 충전형 ● 남음/○ 소진), 마을 장착 카드 4줄째 퍽 라벨(미적용/중복 회색), 창고 카드 `★`/`★★`, 상점 카드 스탯 아래 퍽 줄. 리뷰 반영: `Bullet.ally`(분신·드론 탄, crit/boss_killer 제외 — `_collide` 에서 `b.dmg` 그대로), `INV_STACK_MAX` = INV_STACK+2(저장 로드 clamp 와 `_check_snapshot` 상한; 퍽 해제 후에도 초과 스택 유지), `resize()` 가 `_last_ground_x` 도 rx 배율 + 구조 지점은 항상 `_pit_edge()` 통과, 근접 처치도 kill_haste 로 fire_cd 0(`_player_melee` 가 처치 여부를 보고 cd 를 건너뜀), stomp 웨이브 쌍은 `hit` set 공유(걸친 적은 d 1회) 와 `MAX_BULLETS` 가드(shield_burst blast·해머 웨이브도), `economy.configure({"ENHANCE_PERK_DISCOUNT": x})` 가 `PERKS.haggler` rare 값·ui(`강화비 x{v}`) 를 동기화(명시 멤버 우선), keep_weapon 유니크 ui `무기유지+무적 3.5초`(규칙 13, 12자).

#### v2.1 마을 화면 v2 — 선반 커서 (game.py 계약; 렌더러 molgam.py 는 같은 계약으로 별도 작성)
- 상수: `SHELF_ORDER = ("hat","acc","suit","gloves","weapon","shoes")`(몸 순서 위→아래), `SLOT_EFFECT_LABEL` {shield 실드 / rate 연사 / magic 마법 / speed 이동 / damage 물리 / money 돈}, `PCT_EFFECTS = ("rate","speed","money")`, `TOWN_CARDS_VISIBLE = 3`. `TOWN_HINT` 문구는 새 키 배치로 갱신.
- 커서: `town["cursor"] = {"row": int, "col": int}` (현재 탭의 `town["cursors"][tab]` 과 같은 dict). 행 = `_town_list(tab)`: stat = ("stat", key)×6, shop = ("shelf", slot)×6 + ("box", None), store = ("shelf", slot)×6, gamble = ("game", i)×3; 마지막 행은 항상 ("next", None). 행별 마지막 열(`town["col_mem"][tab]`)과 선반별 창 시작(`town["window"][tab]`)을 탭마다 기억. 처음 방문한 선반의 기본 열 = 장착 카드(0); 슬롯이 비었는데 카드가 있으면 1(상점은 재고가 있으면 항상 1).
- 키: `Tab` 다음 탭(↑↓ 는 더 이상 탭을 바꾸지 않는다). `↑↓` 행 이동(모든 탭, 양끝 순환). `←→` 같은 선반의 카드 이동(순환; 창고 열 0 = 장착 카드, 상점 열 0 = '비교 기준' 카드라 커서가 건너뛰고 1..n 만 순환, 재고 없는 선반은 열 0 고정·선택 불가) / stat·gamble 탭에서는 ←→ 도 행 이동. `Enter`/`fire`(CONFIRM_GUARD 뒤): 창고 열 0 = 해제, 열>0 = 장착(장착품과 교체), 상점 = 구매(그 슬롯이 비어 있으면 창고를 거치지 않고 바로 장착 + "구매 · 바로 장착" 문구, 아니면 창고로), box = 랜덤박스, stat = `_shop_select`, game = `_town_gamble`, next = 다음 스테이지. `C`(`skill`): 창고 열 0 = 강화(`economy.enhance`, 장착 퍼크 반영), 열>0 = 판매, 도박장 = 대상/판돈/배팅 순환, stat·shop = 없음. `_shop_select` / `_town_gamble` 로직은 그대로.
- 선반 카드 순서: 등급 내림차순 → 레벨 내림차순 → 이름 → 원본 인덱스. `window` 는 커서 카드가 보이는 3장 안에 들도록 밀리고(`_town_clamp`, 모든 키·뷰 뒤 멱등 호출) 카드가 줄면 함께 줄어든다.
- hud["town"] 추가 키(기존 키 전부 유지; `index` = 커서 행, `count` = 행 수, `store["mode"]` = 창고 열 0 이면 "equipped" 아니면 "list", `gamble["game"]` = 도박 탭 커서 행):
  - `score: int`, `char: {key, name, trait, stats{str,agi,int}, shield_max, lives}`, `cursor: {row, col}`, `rows_total: int`, `shelf_order: [slot×6]`, `capacity: {used, cap, equipped}`.
  - `shelves`: store/shop 에서만 6개(그 외 탭은 []). `{slot, label, effect_key, effect_label, count, window, equipped: eq_view|None, cards: [eq_view|None, ...]}` — cards[0] = 장착 카드(None = 고스트 "<슬롯> 없음"), cards[1..] = 그 슬롯의 창고 카드(store) / 재고 카드(shop); 커서 `col` 이 그대로 cards 인덱스, `count = len(cards) - 1`.
  - eq_view = 장비 dict(stats/perks 는 복사) + `price`(shop 구매가 / store 판매가; shop 의 장착 카드는 None), `enhance`(store 장착 카드만: 강화 비용, MAX 면 0; 그 외 None), `delta_effect {key, now, after}`, `delta_stats {str, agi, int}`(그 선반 장착품 대비; 장착 카드 자신은 절대값 = now 0 → after 값), `perk_labels: [str]`, `perk_texts: [str]`(등급별 `PERKS[..]["ui"]` 문구; 현재 캐릭터가 못 쓰는 특전(`_perk_ex`)은 둘 다 끝에 `PERK_OFF_SUFFIX` = " (미적용)" 이 붙고 compare.perks 도 같다 — 렌더러는 그 칩을 흐리게), `is_equipped: bool`, `owned: int`(shop 만: 그 슬롯 보유 수 = 창고 + 장착), `afford: bool`, `idx`(warehouse.items / shop_stock 인덱스, 장착 카드는 None).
  - `compare`: None(고스트 위 / 재고 없는 상점 선반) | `{name, rarity, level, slot, slot_label, action: "equip"|"unequip"|"buy"|"box"|"next"|"stat"|"gamble", rows: [{label, now, after, delta, fmt}]×4, perks: [{label, text}], sell, enhance, buy, after_msg}`. 장비 4행 = 힘/민첩/지혜/<슬롯 효과 라벨>; now = 현재 유효값(`_eff_stats`, 실드는 `_shield_max`, 그 외 효과는 `_equip_fx()[key]`), after = 실행 후, delta = after - now(0 이면 None). `fmt == "pct"`(rate/speed/money) 행의 값은 분수 그대로(0.12 = 12%) → 렌더러가 % 로 표기; `fmt == "int"` 는 정수. store: `sell` = 판매가, `enhance` = 강화 비용(열>0 이면 "장착 후 강화"), `buy` None; shop: `buy` = 구매가. stat 탭 4행 = 힘/민첩/지혜/점수(rate·shield·life 항목은 4행이 연사(pct)/실드/목숨), `buy` = 점수 비용(최대 단계면 0), `slot` = 스탯 키(str/agi/int/rate/shield/life), `slot_label` = 힘/민첩/지혜/연사/실드/목숨(렌더러의 색·글리프 키); 도박장 = 판돈 → 기대 결과(강화 도박 ↑/=/↓ 확률 행: `slot` = 대상 장비 슬롯, 더블업 성공/실패/연승: `slot` "g1", 슬롯 배당: `slot` "g2", 둘 다 `slot_label` "도박장"); box = ₩ + 확률 행(문자열 셀은 delta None); next = 스테이지/₩/창고/장착.
  - `legend: [[키, 동사], ...]` 커서 문맥별 — 창고 카드 `[["←→","카드"],["↑↓","선반"],["Enter","장착"],["C","판매"],["Tab","탭"]]`, 장착 카드는 Enter "해제"/C "강화", 상점 `[["←→","상품"],["↑↓","선반"],["Enter","구매"],["Tab","탭"]]`, 랜덤박스 Enter "열기", stat `[["↑↓","항목"],["Enter","구매"],["Tab","탭"]]`, 도박장 C = "대상"/"판돈"/"배팅", next 행 Enter "다음 스테이지" + Esc "게임 종료"(그 행에서 두 번째 Esc = 종료; 다른 행은 Esc "나가기" = 그 행으로 점프).
  - `message: str` 푸터 문맥 문구; 대상 슬롯은 `[슬롯 라벨]` 로 넣는다(렌더러가 부위색 태그로 그림). 예 `"Enter 사신의 작업 장갑 → [작업 장갑] 슬롯에 장착 (빈 슬롯) · C 판매 ₩5,691"`, `"Enter 보통 안전모 해제 → 창고 9/24 · C 강화 ₩674 (Lv 3 → 4)"`, `"[사원증] 재고 없음 · ↑↓ 다른 선반"`. 직전 실행 결과는 기존 `msg`.
- `_check_snapshot`: 위 키 존재, cursor 범위(row < rows_total, 선반 행이면 col < len(cards), 창 안), store/shop 에서 shelves 6개(count/window/고스트 정합), compare 4행 스키마, legend 쌍, capacity/char 키.
- Esc: 논리 키 `"escape"` 는 커서를 마지막 행("다음 스테이지")으로 점프만 시킨다(확정은 Enter). molgam.App 은 Esc 를 마을에서 그 점프로 보내고, 커서가 이미 마지막 행이면(두 번째 Esc) 다른 화면과 같이 게임을 종료한다; 창 닫기(WM_DELETE_WINDOW)는 항상 종료(overlay `on_quit`, Esc 는 `on_escape`). 선반 카드 폭 맞춤(… 생략)·"+N" 표기는 렌더러 몫(`count - window - 보이는 카드 수`; 띠 폭 < 1528 이면 렌더러가 3 → 2 → 1 장으로 줄이고 오른쪽 열을 왼쪽으로 민다).
