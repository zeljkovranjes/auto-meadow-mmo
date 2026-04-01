"""
Game Controller — Background Mode
==================================
Flash-focuses Discord for each input action, then restores your window.
Fast enough to be invisible on another virtual desktop.
"""

import ctypes
import ctypes.wintypes
import time
import win32gui
import pynput.keyboard as pkeyboard

_u32 = ctypes.windll.user32
_kb = pkeyboard.Controller()

_PYNPUT_KEY_MAP = {
    'up':    pkeyboard.Key.up,
    'down':  pkeyboard.Key.down,
    'left':  pkeyboard.Key.left,
    'right': pkeyboard.Key.right,
    'esc':   pkeyboard.Key.esc,
}

# ── Win32 constants ──────────────────────────────────────────────────────────

WM_MOUSEMOVE    = 0x0200
WM_LBUTTONDOWN  = 0x0201
WM_LBUTTONUP    = 0x0202
WM_KEYDOWN      = 0x0100
WM_KEYUP        = 0x0101
MK_LBUTTON      = 0x0001

_VK_MAP = {
    'up':    0x26,
    'down':  0x28,
    'left':  0x25,
    'right': 0x27,
    'esc':   0x1B,
}

_SCAN_MAP = {
    'up':    0x48,
    'down':  0x50,
    'left':  0x4B,
    'right': 0x4D,
    'esc':   0x01,
}

_EXTENDED = {'up', 'down', 'left', 'right'}


def _MAKELPARAM(x, y):
    return ctypes.wintypes.LPARAM((int(y) << 16) | (int(x) & 0xFFFF))


def _find_render_widget(parent_hwnd: int) -> int:
    """Find Chrome_RenderWidgetHostHWND child window."""
    result = [None]
    def cb(hwnd, _):
        if win32gui.GetClassName(hwnd) == 'Chrome_RenderWidgetHostHWND':
            result[0] = hwnd
            return False
        return True
    try:
        win32gui.EnumChildWindows(parent_hwnd, cb, None)
    except:
        pass
    return result[0] or parent_hwnd


class GameController:
    def __init__(self, hwnd: int):
        self.parent_hwnd = hwnd
        self.hwnd = _find_render_widget(hwnd)
        self._locked = False   # True while focus is held for a game session
        self._prev_fg = None   # window to restore when releasing

    # ── Focus management ─────────────────────────────────────────────────

    def _force_foreground(self):
        """Force Discord to foreground even when another app has focus.
        Simulates Alt press to bypass Windows' foreground lock."""
        _u32.keybd_event(0x12, 0, 0, 0)   # Alt down
        _u32.keybd_event(0x12, 0, 2, 0)   # Alt up
        _u32.SetForegroundWindow(self.parent_hwnd)

    def grab_focus(self):
        """Hold Discord focus until release_focus() is called.
        Use this for game entry sequences that need sustained focus.
        Can be called again to re-grab if user switched desktops."""
        if not self._locked:
            self._prev_fg = _u32.GetForegroundWindow()
            if self._prev_fg == self.parent_hwnd:
                self._prev_fg = None
        self._force_foreground()
        time.sleep(0.03)
        self._locked = True

    def release_focus(self):
        """Give focus back to whatever the user had open."""
        if self._locked and self._prev_fg:
            time.sleep(0.02)
            _u32.keybd_event(0x12, 0, 0, 0)
            _u32.keybd_event(0x12, 0, 2, 0)
            _u32.SetForegroundWindow(self._prev_fg)
        self._locked = False
        self._prev_fg = None

    def _flash_focus(self):
        """Briefly steal focus. If locked, re-grab if focus was lost."""
        if self._locked:
            if _u32.GetForegroundWindow() != self.parent_hwnd:
                self._force_foreground()
                time.sleep(0.03)
            return None
        prev = _u32.GetForegroundWindow()
        if prev != self.parent_hwnd:
            self._force_foreground()
            time.sleep(0.03)
        return prev

    def _restore(self, prev):
        """Give focus back — skipped if locked."""
        if self._locked:
            return
        if prev and prev != self.parent_hwnd:
            time.sleep(0.02)
            _u32.keybd_event(0x12, 0, 0, 0)
            _u32.keybd_event(0x12, 0, 2, 0)
            _u32.SetForegroundWindow(prev)

    # ── Input ────────────────────────────────────────────────────────────

    def click(self, x: int, y: int):
        prev = self._flash_focus()
        # Convert client coords to screen coords for SetCursorPos
        pt = ctypes.wintypes.POINT(int(x), int(y))
        _u32.ClientToScreen(self.parent_hwnd, ctypes.byref(pt))
        _u32.SetCursorPos(pt.x, pt.y)
        _u32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFT_DOWN
        _u32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFT_UP
        self._restore(prev)

    def move(self, x: int, y: int):
        prev = self._flash_focus()
        pt = ctypes.wintypes.POINT(int(x), int(y))
        _u32.ClientToScreen(self.parent_hwnd, ctypes.byref(pt))
        _u32.SetCursorPos(pt.x, pt.y)
        self._restore(prev)

    def press_key(self, key_name: str):
        key = _PYNPUT_KEY_MAP.get(key_name)
        if key is None:
            return
        prev = self._flash_focus()
        _kb.press(key)
        _kb.release(key)
        self._restore(prev)
