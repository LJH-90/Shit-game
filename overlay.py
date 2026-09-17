# -*- coding: utf-8 -*-
"""
overlay.py — MolGam 투명 오버레이 창.

- 마우스 커서가 있는 모니터의 작업영역(작업표시줄 제외) 하단 1/3, 가로 전체에 배치
- 테두리 없음, 항상 위, 투명색 클릭 통과 (-transparentcolor)
- 작업표시줄 / Alt+Tab 목록에 나타나지 않음 (WS_EX_TOOLWINDOW)
- 전역 핫키(RegisterHotKey)로 숨김/복귀. 숨기면 직전 창으로 포커스 반환.
- 전역 키보드 후킹은 쓰지 않는다. 게임이 보이는 동안만 키 입력을 받는다.

표준 라이브러리만 사용 (tkinter, ctypes). Windows 전용.
인터페이스는 INTERFACES.md 섹션 B 를 따른다.
"""
from __future__ import annotations

import sys
import ctypes
import threading
from ctypes import wintypes

if not sys.platform.startswith("win"):
    raise SystemExit("MolGam 은 Windows 전용입니다.")


# ---------------------------------------------------------------- DPI 인식
# tk.Tk() 생성 전에 호출해야 물리 픽셀 좌표와 창 좌표가 일치한다.
def _set_dpi_aware() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_set_dpi_aware()

import tkinter as tk  # noqa: E402  (DPI 설정 이후에 임포트)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------- Win32 상수
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOPMOST = 0x00000008

MONITOR_DEFAULTTONEAREST = 2

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
PM_REMOVE = 0x0001

HOTKEY_ID = 0x4D47  # 'MG'

# 논리 키 매핑 (tk keysym 소문자 → 논리 키 목록)
_KEYMAP = {
    "left": ["left"],        # game.py 가 select/continue 화면에서도 left/right 를 해석한다 (sel_* 중복 전송 금지)
    "right": ["right"],
    "up": ["up", "jump"],
    "down": ["down"],
    "z": ["jump"],
    "space": ["fire", "confirm"],
    "x": ["fire"],
    "c": ["skill"],
    "u": ["update"],         # molgam 이 처리 (원격 업데이트 설치)
    "return": ["confirm"],
    "kp_enter": ["confirm"],
    "p": ["pause"],
    "escape": ["quit"],
    "tab": ["tab"],          # v1.9: 마을 화면 탭 전환
    "1": ["slot1"], "2": ["slot2"], "3": ["slot3"], "4": ["slot4"], "5": ["slot5"],   # 인벤토리 사용
    "kp_1": ["slot1"], "kp_2": ["slot2"], "kp_3": ["slot3"], "kp_4": ["slot4"], "kp_5": ["slot5"],
}


def _logical_keys(ks: str) -> tuple:
    """keysym → 논리 키 목록. _KEYMAP 에 없는 한 글자 알파벳은 타자용 'char:<letter>' 로 보낸다."""
    hit = _KEYMAP.get(ks)
    if hit is not None:
        return tuple(hit)
    if len(ks) == 1 and "a" <= ks <= "z":
        return ("char:" + ks,)
    return ()

_MOD_NAMES = {
    "shift": MOD_SHIFT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "win": MOD_WIN,
    "super": MOD_WIN,
}

_VK_NAMED = {
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "pause": 0x13, "scrolllock": 0x91, "numlock": 0x90, "printscreen": 0x2C,
    "numpad0": 0x60, "numpad1": 0x61, "numpad2": 0x62, "numpad3": 0x63, "numpad4": 0x64,
    "numpad5": 0x65, "numpad6": 0x66, "numpad7": 0x67, "numpad8": 0x68, "numpad9": 0x69,
}


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


user32.GetWindowLongPtrW.restype = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
user32.SetWindowLongPtrW.restype = user32.GetWindowLongPtrW.restype
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.VkKeyScanW.restype = ctypes.c_short
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.BringWindowToTop.argtypes = [wintypes.HWND]


# ---------------------------------------------------------------- 핫키 문자열 파싱
def parse_hotkey(spec: str) -> tuple[int, int]:
    """'shift+0', 'ctrl+shift+f12', 'alt+`' → (modifiers, vk). 실패 시 ValueError."""
    if not spec or not isinstance(spec, str):
        raise ValueError("핫키 문자열이 비어 있습니다")
    parts = [p.strip().lower() for p in spec.replace(" ", "").split("+") if p.strip() != ""]
    # 'ctrl++' 처럼 '+' 자체를 키로 쓰는 경우
    if spec.strip().endswith("+") and (not parts or parts[-1] in _MOD_NAMES):
        parts.append("+")
    if not parts:
        raise ValueError("핫키 문자열이 비어 있습니다: %r" % spec)
    mods = 0
    key = parts[-1]
    for m in parts[:-1]:
        if m not in _MOD_NAMES:
            raise ValueError("알 수 없는 보조키: %r (shift/ctrl/alt/win)" % m)
        mods |= _MOD_NAMES[m]
    if key in _MOD_NAMES:
        raise ValueError("핫키에 일반 키가 없습니다: %r" % spec)

    vk = None
    if key in _VK_NAMED:
        vk = _VK_NAMED[key]
    elif len(key) >= 2 and key[0] == "f" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1:
        ch = key
        if ch.isdigit():
            vk = 0x30 + int(ch)
        elif "a" <= ch <= "z":
            vk = 0x41 + (ord(ch) - ord("a"))
        else:
            r = user32.VkKeyScanW(ch)
            if r == -1:
                raise ValueError("이 자판에서 매핑할 수 없는 키: %r" % ch)
            vk = r & 0xFF
    if vk is None:
        raise ValueError("알 수 없는 키: %r" % key)
    return mods, vk


# ---------------------------------------------------------------- 모니터 판정
def cursor_band_rect() -> tuple[int, int, int, int]:
    """커서가 있는 모니터 작업영역의 하단 1/3 (x, y, w, h). 물리 픽셀."""
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        # 폴백: 주 모니터 작업영역
        r = wintypes.RECT()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
        rw = r
    else:
        rw = mi.rcWork
    full_w = rw.right - rw.left
    full_h = rw.bottom - rw.top
    h = full_h // 3
    y = rw.bottom - h
    return int(rw.left), int(y), int(full_w), int(h)


# ---------------------------------------------------------------- 핫키 스레드
class _HotkeyThread(threading.Thread):
    """RegisterHotKey(NULL hwnd) 는 등록한 스레드의 메시지 큐로 WM_HOTKEY 를 보낸다.
    이 스레드가 그 큐를 GetMessage 로 읽고, 눌린 횟수를 카운터에 쌓는다. 메인 루프는 take() 로 가져간다."""

    def __init__(self, mods: int, vk: int):
        super().__init__(daemon=True, name="molgam-hotkey")
        self.mods = mods
        self.vk = vk
        self.error = 0
        self.tid = 0
        self._registered = threading.Event()
        self._done = threading.Event()
        self._count = 0
        self._lock = threading.Lock()

    def run(self) -> None:
        self.tid = kernel32.GetCurrentThreadId()
        # 큐 생성 (PostThreadMessage 를 받으려면 큐가 있어야 함)
        msg = MSG()
        user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 0)
        if not user32.RegisterHotKey(None, HOTKEY_ID, self.mods, self.vk):
            self.error = kernel32.GetLastError()
            self._done.set()
            self._registered.set()
            return
        self._registered.set()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    with self._lock:
                        self._count += 1
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self._done.set()

    def wait_registered(self, timeout: float) -> bool:
        self._registered.wait(timeout)
        return self._registered.is_set() and self.error == 0

    def take(self) -> int:
        with self._lock:
            n = self._count
            self._count = 0
        return n

    def stop(self) -> None:
        if self.tid:
            user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
            self._done.wait(1.0)


# ---------------------------------------------------------------- 오버레이
class Overlay:
    def __init__(self, hotkey: str = "shift+0", on_toggle=None, on_quit=None):
        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self.hotkey_spec = hotkey
        self.trans_color = "#010203"
        self.visible = True
        self._prev_fg: int | None = None
        self._pressed: set[str] = set()
        self._on_down = None
        self._on_up = None
        self._hotkey_registered = False

        self.x, self.y, self.w, self.h = cursor_band_rect()

        self.root = tk.Tk()
        self.root.title("")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("%dx%d+%d+%d" % (self.w, self.h, self.x, self.y))
        self.root.configure(bg=self.trans_color)
        try:
            self.root.attributes("-transparentcolor", self.trans_color)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h,
                                bg=self.trans_color, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.root.update_idletasks()
        self.hwnd = self._resolve_hwnd()
        self._apply_exstyle()

        # 전역 핫키는 별도 스레드에서 등록/수신한다.
        # (tk 의 메시지 펌프가 큐를 먼저 비우기 때문에 메인 스레드에서 PeekMessage 로는 WM_HOTKEY 를 못 받는다)
        mods, vk = parse_hotkey(hotkey)
        self._hotkey_thread = _HotkeyThread(mods | MOD_NOREPEAT, vk)
        self._hotkey_thread.start()
        if not self._hotkey_thread.wait_registered(2.0):
            err = self._hotkey_thread.error
            raise RuntimeError(
                "핫키 %r 등록 실패 (오류 %d). 다른 프로그램이 이미 쓰고 있으면 config.json 의 hotkey 를 바꾸세요."
                % (hotkey, err))
        self._hotkey_registered = True

        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.after(50, self._grab_focus)

    # ------------------------------------------------------------ 내부
    def _resolve_hwnd(self) -> int:
        # tk 의 winfo_id 는 내부 자식 창. 실제 최상위 창은 그 부모.
        inner = self.root.winfo_id()
        parent = user32.GetParent(inner)
        return int(parent) if parent else int(inner)

    def _apply_exstyle(self) -> None:
        try:
            st = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
            st = (st | WS_EX_TOOLWINDOW | WS_EX_TOPMOST) & ~WS_EX_APPWINDOW
            user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, st)
        except Exception:
            pass

    def _grab_focus(self) -> None:
        try:
            user32.SetForegroundWindow(self.hwnd)
            if user32.GetForegroundWindow() != self.hwnd:
                fg = user32.GetForegroundWindow()
                cur = kernel32.GetCurrentThreadId()
                pid = wintypes.DWORD()
                fg_tid = user32.GetWindowThreadProcessId(fg, ctypes.byref(pid)) if fg else 0
                if fg_tid and fg_tid != cur:
                    user32.AttachThreadInput(cur, fg_tid, True)
                    try:
                        user32.BringWindowToTop(self.hwnd)
                        user32.SetForegroundWindow(self.hwnd)
                    finally:
                        user32.AttachThreadInput(cur, fg_tid, False)
        except Exception:
            pass
        try:
            self.root.focus_force()
            self.canvas.focus_set()
        except tk.TclError:
            pass

    def _quit(self) -> None:
        if self.on_quit:
            self.on_quit()

    # ------------------------------------------------------------ 공개 API
    def place_on_cursor_monitor(self) -> bool:
        x, y, w, h = cursor_band_rect()
        changed = (w, h) != (self.w, self.h)
        self.x, self.y, self.w, self.h = x, y, w, h
        self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
        if changed:
            self.canvas.config(width=w, height=h)
        return changed

    def show(self) -> None:
        self.place_on_cursor_monitor()
        self.root.deiconify()
        self.root.update_idletasks()
        self._apply_exstyle()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.visible = True
        self._pressed.clear()
        self._grab_focus()

    def hide(self) -> None:
        fg = user32.GetForegroundWindow()
        if fg and fg != self.hwnd:
            self._prev_fg = int(fg)
        self.root.withdraw()
        self.visible = False
        self._pressed.clear()
        if self._prev_fg and user32.IsWindow(self._prev_fg):
            try:
                user32.SetForegroundWindow(self._prev_fg)
            except Exception:
                pass

    def toggle(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()

    def poll(self) -> None:
        if self._hotkey_thread.take():
            self.toggle()
            if self.on_toggle:
                self.on_toggle(self.visible)

    def bind_keys(self, on_down, on_up) -> None:
        self._on_down = on_down
        self._on_up = on_up
        self.root.bind("<KeyPress>", self._key_press)
        self.root.bind("<KeyRelease>", self._key_release)

    def _key_press(self, e) -> None:
        ks = (e.keysym or "").lower()
        if ks in self._pressed:
            return  # 자동 반복
        self._pressed.add(ks)
        for logical in _logical_keys(ks):
            if self._on_down:
                self._on_down(logical)
            if logical == "quit":
                self._quit()

    def _key_release(self, e) -> None:
        ks = (e.keysym or "").lower()
        self._pressed.discard(ks)
        for logical in _logical_keys(ks):
            if self._on_up:
                self._on_up(logical)

    def destroy(self) -> None:
        if self._hotkey_registered:
            self._hotkey_thread.stop()
            self._hotkey_registered = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- 데모
if __name__ == "__main__":
    import time

    for spec in ["shift+0", "ctrl+shift+f12", "alt+`", "win+g", "f9", "ctrl+alt+numpad0"]:
        try:
            print("%-18s -> mods=0x%x vk=0x%02x" % (spec, *parse_hotkey(spec)))
        except ValueError as ex:
            print("%-18s -> ERROR %s" % (spec, ex))

    ov = Overlay(hotkey="shift+0",
                 on_toggle=lambda v: print("toggle ->", "visible" if v else "hidden"),
                 on_quit=lambda: ov.root.after(0, ov.root.quit))
    print("band rect:", (ov.x, ov.y, ov.w, ov.h))
    ov.canvas.create_rectangle(10, 10, 620, 70, fill="#202830", outline="#7fd4ff", width=2)
    ov.canvas.create_text(20, 40, anchor="w", fill="#e8f4ff", font=("Malgun Gothic", 14, "bold"),
                          text="MolGam overlay OK — Shift+0 토글, Esc 종료 (8초 후 자동 종료)")
    ov.canvas.create_line(0, ov.h - 10, ov.w, ov.h - 10, fill="#7fd4ff", width=2)
    ov.bind_keys(lambda k: print("down", k), lambda k: print("up", k))

    t0 = time.perf_counter()

    def tick():
        ov.poll()
        if time.perf_counter() - t0 > 8:
            ov.root.quit()
            return
        ov.root.after(33, tick)

    ov.root.after(33, tick)
    ov.root.mainloop()
    ov.destroy()
    print("exit ok")
