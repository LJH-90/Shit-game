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
        매핑: ←→↑↓, jump=↑/Z, fire=Space/X, pause=P, quit=Escape, confirm=Enter/Space, sel_*=←→(선택 화면에서 game이 해석)"""
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
- snapshot bullets 항목 추가 키: `"sprite": str|None, "anim": str|None, "frame": int, "flip": bool` (flip = vx<0).
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
RARITY_MULT = {"normal":1.0,"rare":1.8,"unique":3.0}      # 고유 효과·스탯 배수 (유니크 = 일반의 3배 = 200% 차이)
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
#    "stats": {"str": int, "agi": int, "int": int}}  — stats 기본 합 = 2 + stage//5, 셋 중 랜덤 분배, × roll × RARITY_MULT, 반올림
def equip_effect(eq) -> dict   # {"shield":int,"rate":float,"magic":int,"speed":float,"jump":float,"damage":int,"money":float,"str":int,"agi":int,"int":int}
def total_effect(equipped: dict[str, dict|None]) -> dict   # 슬롯 합산, 키 전부 존재
def upgrade_cost(eq) -> int          # 300 * 1.12**level * RARITY_COST[rarity](1/1.5/2.5), 레벨 20 이면 0(불가)
def buy_price(eq, stage) -> int      # (600 * RARITY_PRICE(1/4/15) + 120*level) * (1 + 0.06*(stage-1))
def sell_price(eq, stage) -> int     # buy_price * 0.4
def roll_rarity(rng, table) -> str
def make_shop_stock(rng, stage, n=10) -> list[dict]   # SHOP_RARITY, 슬롯 랜덤, level 0~min(5, stage//3)
BOX_PRICE = lambda stage: int(900 * (1 + 0.06*(stage-1)))
def open_box(rng, stage) -> dict     # {"kind": "equip"|"item"|"money"|"dud", "equip": dict|None, "item": str|None, "money": int}
#   60% equip(BOX_RARITY) / 25% item(ITEM_KINDS 중 랜덤, 1UP 제외 가중) / 10% money(BOX_PRICE*0.5~3.0) / 5% dud("꽝 · 사탕 하나")
def gamble_upgrade(rng, eq, money) -> tuple[dict, int, str]   # cost = upgrade_cost*1.5; 60% +2lv(최대 20) / 30% 변화 없음 / 10% -3lv(유니크는 -0 대신 변화 없음). 반환 (eq, 잔액, 결과 문구). 돈 부족이면 문구만
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
    def to_save(self) -> dict                   # {"items": [...], "equipped": {slot: eq|None}}
def money_drop(rng, kind: str, stage: int, diff_mult: float, acc_bonus: float) -> int
#   kind grunt 20~40 / elite 60~100 / mid 300 / boss 800 / word 500 ; × (1 + 0.08*(stage-1)) × diff_mult × (1+acc_bonus)
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
        "gamble": {"games": ["강화 도박","더블업","슬롯"], "game": int, "stake": int, "streak": int, "reels": [str×3]|None, "target": int|None}}`
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
- economy: `MONEY_STAGE_GROWTH` 0.08 → 0.05 (50스테이지 누적 ≈ 21.8만 ₩). `BOX_PRICE(stage)` 는 함수. `open_box` 결과에 `"text"` 추가. `WORD_RARITY` 상수 노출. `Warehouse.equip(idx)` 는 기존 장착품을 같은 자리(idx)에 되돌려 놓아 용량 실패가 없다.
- hud["town"] 추가 키: `"tab_index"`, `"count"`, `"hint"`(탭별 조작 안내 문자열), `"money"`, `shop["prices"]`, `store["cap"|"sell"|"upgrade_cost"]`, `gamble["stake_pct"|"bet"|"target_eq"|"target_cost"]`. 마을 조작: `Tab` 탭, `↑↓` = 창고 줄 전환 / 도박 항목 이동 / 그 외 탭 전환, `←→` 항목, `Enter` 실행, `C` 보조(창고 판매 · 도박 대상/배팅 변경).
- 인벤토리 사용 키는 `slot1..slot5`(숫자 1~5, 키패드 포함). 타자는 `char:<letter>` — `z x c p u` 는 게임 키이므로 단어에 안 쓴다(`WORD_LETTERS`).
- 새 rank 키(stages.json): `sheet: true`(자체 시트 → 근접 anim "attack"), `melee: true`, `hit_scaled: true`(hit_w/h × scale), `proj {anim, w, h, speed, aim, gravity, fuse, blast}`, `jump_odds`, `jump_mult`. 부서 `monsters`, 최상위 `monsters_from_stage`(기본 5).
- 밸런스 로그: `World.drain_log()` → 스테이지 종료(클리어/게임 오버)마다 1 dict. molgam 이 `balance_log.jsonl`(세이브 파일 옆)에 한 줄씩 append.
- 무기 상점 재고는 마을 방문(스테이지)마다 새로 뽑고, 그 마을 안에서는 유지된다(`shop_stock_stage`).
