import ctypes
import pynput.keyboard as pkeyboard

_KEY_MAP = {
    'up':    pkeyboard.Key.up,
    'down':  pkeyboard.Key.down,
    'left':  pkeyboard.Key.left,
    'right': pkeyboard.Key.right,
}

# win32 mouse_event flags
_MOVE       = 0x0001
_LEFT_DOWN  = 0x0002
_LEFT_UP    = 0x0004
_ABSOLUTE   = 0x8000

_u32 = ctypes.windll.user32

class GameController:
    def __init__(self):
        self.kb = pkeyboard.Controller()

    def click(self, x: int, y: int):
        _u32.SetCursorPos(x, y)
        _u32.mouse_event(_LEFT_DOWN, 0, 0, 0, 0)
        _u32.mouse_event(_LEFT_UP,   0, 0, 0, 0)

    def move(self, x: int, y: int):
        _u32.SetCursorPos(x, y)

    def press_key(self, direction: str):
        key = _KEY_MAP.get(direction)
        if key:
            self.kb.press(key)
            self.kb.release(key)
