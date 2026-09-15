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
