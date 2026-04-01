import ctypes
import ctypes.wintypes
import pynput.keyboard as pkeyboard

_KEY_MAP = {
    'up':    pkeyboard.Key.up,
    'down':  pkeyboard.Key.down,
    'left':  pkeyboard.Key.left,
    'right': pkeyboard.Key.right,
}

# win32 mouse_event flags
_LEFT_DOWN  = 0x0002
_LEFT_UP    = 0x0004

_u32 = ctypes.windll.user32

# Declare proper argument/return types so ctypes doesn't silently fail
_u32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
_u32.SetCursorPos.restype  = ctypes.wintypes.BOOL

_u32.mouse_event.argtypes = [
    ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
    ctypes.POINTER(ctypes.c_ulong),
]
_u32.mouse_event.restype = None


class GameController:
    def __init__(self):
        self.kb = pkeyboard.Controller()

    def click(self, x: int, y: int):
        _u32.SetCursorPos(int(x), int(y))
        _u32.mouse_event(_LEFT_DOWN, 0, 0, 0, None)
        _u32.mouse_event(_LEFT_UP,   0, 0, 0, None)

    def move(self, x: int, y: int):
        _u32.SetCursorPos(int(x), int(y))

    def press_key(self, direction: str):
        key = _KEY_MAP.get(direction)
        if key:
            self.kb.press(key)
            self.kb.release(key)
