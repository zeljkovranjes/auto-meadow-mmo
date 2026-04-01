"""
Meadow MMO Discord Bot — Background Mode
==========================================
Runs fully in the background via PrintWindow + PostMessage.
No cursor movement, no window focus required.
Works across Windows virtual desktops.

Priority:  Craft (available) > Battle (available) > Adventure (fallback)
Press F at any time to stop the bot.
"""

import time
import threading
import win32gui
from enum import Enum, auto
from pynput import keyboard as pkb

from vision     import GameVision
from controller import GameController
import config as cfg
import logger as log


class State(Enum):
    IDLE      = auto()
    ADVENTURE = auto()
    CRAFT     = auto()
    BATTLE    = auto()


class Bot:
    def __init__(self):
        self.vision = GameVision()
        self.ctrl: GameController | None = None
        self.state  = State.IDLE

        self.craft_round    = 0
        self.battle_btn_pos: tuple | None = None

        self._idle_frames = 0
        self._stop = threading.Event()
        self._hwnd: int | None = None
        self._last_win_size: tuple[int, int] = (0, 0)

    # ── Stop key ─────────────────────────────────────────────────────────

    def _start_hotkey(self):
        def on_press(key):
            try:
                if key.char and key.char.lower() == 'f':
                    log.separator()
                    log.system("Kill signal received — shutting down")
                    self._stop.set()
                    return False
            except AttributeError:
                pass
        pkb.Listener(on_press=on_press, daemon=True).start()

    # ── Discord window ────────────────────────────────────────────────────

    def _refresh_window(self):
        found = []
        def cb(hwnd, _):
            if 'Discord' in win32gui.GetWindowText(hwnd):
                found.append(hwnd)
        win32gui.EnumWindows(cb, None)
        if found:
            self._hwnd = found[0]
            self.ctrl = GameController(self._hwnd)

    def _client_size(self) -> tuple[int, int]:
        """Return (width, height) of the Discord client area."""
        if not self._hwnd:
            return (0, 0)
        r = win32gui.GetClientRect(self._hwnd)
        return (r[2] - r[0], r[3] - r[1])

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        log.banner()
        log.separator()
        log.system("Initializing modules")
        log.info("SYS", f"Vision engine loaded — {len(self.vision.templates)} templates")
        log.info("SYS", f"Arrow templates — {len(self.vision.arrow_templates)}/4 loaded")
        log.info("SYS", "Controller ready (background mode)")
        log.separator()

        log.system(f"Starting in {cfg.STARTUP_DELAY}s — press F to abort")
        self._start_hotkey()
        time.sleep(cfg.STARTUP_DELAY)

        log.system("Acquiring Discord window")
        self._refresh_window()
        if self._hwnd:
            log.success(f"Discord window acquired (hwnd: {self._hwnd})")
        else:
            log.warn("Discord window not found — will retry")
        time.sleep(cfg.WINDOW_SETTLE_DELAY)

        # Calibrate template scale to current window size
        if self._hwnd:
            log.system("Calibrating templates to screen")
            _, gray = self.vision.capture(self._hwnd)
            self.vision.calibrate(gray)
            self._last_win_size = self._client_size()

        log.separator()
        log.system("Bot is now running")
        log.separator()

        while not self._stop.is_set():
            if not self._hwnd:
                log.warn("Discord window lost — retrying")
                time.sleep(cfg.WINDOW_RETRY_DELAY)
                self._refresh_window()
                continue

            color, gray = self.vision.capture(self._hwnd)

            # Re-calibrate if window was resized
            cur_size = self._client_size()
            if cur_size != self._last_win_size and cur_size[0] > 0:
                log.system(f"Window resized to {cur_size[0]}x{cur_size[1]} — recalibrating")
                self.vision.recalibrate(gray)
                self._last_win_size = cur_size

            self._tick(gray, color)
            time.sleep(cfg.MAIN_LOOP_INTERVAL)

        log.separator()
        log.system("Bot stopped — session ended")
        log.separator()

    # ── State machine ─────────────────────────────────────────────────────

    def _tick(self, gray, color):
        # Global out-of-resources check
        if self.vision.find(gray, 'out_of_resources'):
            self._dismiss_out_of_resources(gray)
            self.state = State.IDLE
            self._idle_frames = 0
            return

        craft_avail    = self.vision.is_craft_available(gray)
        battle_avail   = self.vision.is_battle_available(gray)
        craft_visible  = self.vision.find(gray, 'craft_btn',  cfg.THRESH_CRAFT_BTN) is not None
        battle_visible = self.vision.find(gray, 'battle_btn', cfg.THRESH_BATTLE_BTN) is not None

        cd_pos = self.vision.find(gray, 'cooldown_clock')
        if cd_pos:
            self.battle_btn_pos = cd_pos

        if craft_avail and self.state != State.CRAFT:
            self._idle_frames = 0
            log.state_change(self.state.name, "CRAFT")
            self.state = State.CRAFT
            self.craft_round = 0

        elif (not craft_avail
              and battle_avail
              and self.state not in (State.CRAFT, State.BATTLE)):
            self._idle_frames = 0
            log.state_change(self.state.name, "BATTLE")
            self.state = State.BATTLE

        elif not craft_visible and not battle_visible:
            adv_visible = (
                self.vision.find(gray, 'adventure_btn',      cfg.THRESH_ADVENTURE_BTN) is not None or
                self.vision.find(gray, 'adventure_progress', cfg.THRESH_ADVENTURE_ALT) is not None or
                self.vision.find(gray, 'adventure_complete', cfg.THRESH_ADVENTURE_ALT) is not None
            )
            if not adv_visible:
                in_battle_game = self.vision.closest_fireball_x(color) is not None
                in_craft_game  = bool(self.vision.detect_arrows(gray))
                if in_battle_game or in_craft_game:
                    return

                back = self.vision.find(gray, 'back_arrow')
                if back:
                    log.warn("No activity buttons detected — navigating back")
                    self.ctrl.click(back[0], back[1])
                    time.sleep(cfg.BACK_ARROW_DELAY)
                return

        elif self.state == State.IDLE:
            self._idle_frames += 1
            if self._idle_frames >= cfg.IDLE_FRAMES_BEFORE_ADV:
                log.state_change("IDLE", "ADVENTURE")
                self.state = State.ADVENTURE
                self._idle_frames = 0
            return

        if self.state == State.CRAFT and self.vision.is_craft_on_cooldown(gray):
            log.cooldown("Craft")
            self.state = State.IDLE
            return

        if self.state == State.BATTLE and self.vision.is_battle_on_cooldown(gray):
            log.cooldown("Battle")
            self.state = State.IDLE
            return

        if self.state == State.ADVENTURE:
            self._adventure(gray)
        elif self.state == State.CRAFT:
            self._craft(gray)
        elif self.state == State.BATTLE:
            self._battle(gray, color)

    # ── Adventure ─────────────────────────────────────────────────────────

    def _adventure(self, gray):
        pos = (self.vision.find(gray, 'adventure_btn',      thresh=cfg.THRESH_ADVENTURE_BTN) or
               self.vision.find(gray, 'adventure_progress', thresh=cfg.THRESH_ADVENTURE_ALT) or
               self.vision.find(gray, 'adventure_complete', thresh=cfg.THRESH_ADVENTURE_ALT))
        if pos is None:
            return

        self.ctrl.grab_focus()
        self.ctrl.move(pos[0], pos[1])
        log.action("ADV", f"Engaging adventure at ({pos[0]}, {pos[1]})")

        frame_count = 0
        while not self._stop.is_set():
            self.ctrl.click(pos[0], pos[1])
            time.sleep(cfg.ADVENTURE_CLICK_INTERVAL)

            frame_count += 1
            if frame_count % cfg.ADVENTURE_CHECK_EVERY == 0:
                _, gray = self.vision.capture(self._hwnd)

                if self.vision.find(gray, 'out_of_resources'):
                    self._dismiss_out_of_resources(gray)
                    self.state = State.IDLE
                    self.ctrl.release_focus()
                    return

                if self.vision.is_craft_available(gray):
                    log.action("ADV", "Craft available — switching priority")
                    self.state = State.CRAFT
                    self.craft_round = 0
                    self.ctrl.release_focus()
                    return

                if self.vision.is_battle_available(gray):
                    log.action("ADV", "Battle available — switching priority")
                    self.state = State.BATTLE
                    self.ctrl.release_focus()
                    return

    # ── Craft ─────────────────────────────────────────────────────────────

    def _craft(self, gray):
        self.ctrl.grab_focus()

        # Enter craft game
        inside = self.vision.find(gray, 'craft_star_0', thresh=cfg.THRESH_CRAFT_STAR) is not None
        if not inside:
            craft_btn_pos = self.vision.find(gray, 'craft_btn', thresh=cfg.THRESH_CRAFT_BTN)
            if craft_btn_pos:
                log.action("CRAFT", "Entering craft game")
                self.ctrl.move(craft_btn_pos[0], craft_btn_pos[1])
                time.sleep(cfg.PRE_CLICK_DELAY)
                self.ctrl.click(craft_btn_pos[0], craft_btn_pos[1])
                time.sleep(cfg.CRAFT_LOAD_DELAY)
                _, gray = self.vision.capture(self._hwnd)

        log.info("CRAFT", "Craft loop active — awaiting arrows")

        while not self._stop.is_set():
            _, gray = self.vision.capture(self._hwnd)

            if self.vision.find(gray, 'craft_success', thresh=cfg.THRESH_CRAFT_SUCCESS):
                pos = self.vision.find(gray, 'continue_btn')
                if pos:
                    log.success("Craft complete — collecting reward")
                    self.ctrl.click(pos[0], pos[1])
                    self.craft_round = 0
                    time.sleep(cfg.POST_GAME_PAUSE)
                self.state = State.IDLE
                self.ctrl.release_focus()
                return

            if self.vision.is_craft_on_cooldown(gray):
                log.cooldown("Craft")
                self.state = State.IDLE
                self.ctrl.release_focus()
                return

            arrows = self.vision.detect_arrows(gray)
            if arrows:
                log.action("CRAFT", f"Round {self.craft_round + 1}/3 — sequence: {' '.join(arrows)}")
                for key in arrows:
                    self.ctrl.press_key(key)
                    time.sleep(cfg.CRAFT_ARROW_DELAY)
                    _, gray = self.vision.capture(self._hwnd)
                self.craft_round += 1
                time.sleep(cfg.CRAFT_ROUND_PAUSE)
            else:
                time.sleep(cfg.MAIN_LOOP_INTERVAL)

    # ── Out-of-resources dismissal ────────────────────────────────────────

    def _dismiss_out_of_resources(self, gray):
        log.obstacle("Obstacle detected — out of resources — circumventing")

        win_w, win_h = self._client_size()

        btn = self.vision.find(gray, 'out_of_resources_btn')
        if btn:
            log.info("OBSTACLE", "Dismiss button found — clicking")
            self.ctrl.click(btn[0], btn[1])
        else:
            log.info("OBSTACLE", "No dismiss button — clicking neutral area")
            self.ctrl.click(win_w // 4, win_h // 4)

        time.sleep(cfg.OOR_DISMISS_WAIT)

        _, gray = self.vision.capture(self._hwnd)

        if self.vision.find(gray, 'out_of_resources'):
            log.info("OBSTACLE", "Still visible — retrying with neutral click")
            self.ctrl.click(win_w // 4, win_h // 4)
            time.sleep(cfg.OOR_NEUTRAL_CLICK_WAIT)
            _, gray = self.vision.capture(self._hwnd)

        if self.vision.find(gray, 'out_of_resources'):
            log.info("OBSTACLE", "Fallback — sending Escape key")
            self.ctrl.press_key('esc')
            time.sleep(cfg.OOR_ESCAPE_WAIT)

        log.success("Obstacle cleared — resuming operations")

    # ── Battle ────────────────────────────────────────────────────────────

    def _battle(self, gray, color):
        self.ctrl.grab_focus()

        # Enter battle
        btn = self.vision.find(gray, 'battle_btn', thresh=cfg.THRESH_BATTLE_BTN)
        if btn:
            log.action("BATTLE", "Entering battle game")
            self.ctrl.move(btn[0], btn[1])
            time.sleep(cfg.PRE_CLICK_DELAY)
            self.ctrl.click(btn[0], btn[1])

            # Poll for the button to disappear (game loaded)
            poll_iters = int(cfg.BATTLE_LOAD_TIMEOUT / cfg.BATTLE_LOAD_POLL)
            for _ in range(poll_iters):
                time.sleep(cfg.BATTLE_LOAD_POLL)
                color, gray = self.vision.capture(self._hwnd)
                if self.vision.find(gray, 'battle_btn', thresh=cfg.THRESH_BATTLE_BTN) is None:
                    break

        # Inside the game
        platform_pos = self.vision.find(gray, 'battle_platform', thresh=cfg.THRESH_BATTLE_PLATFORM)
        win_w, win_h = self._client_size()
        platform_y = platform_pos[1] if platform_pos else int(win_h * cfg.PLATFORM_Y_FALLBACK)
        center_x   = win_w // 2
        frame_count = 0

        self.ctrl.move(center_x, platform_y)
        log.info("BATTLE", "Tracking active — intercepting fireballs")

        while not self._stop.is_set():
            color, gray = self.vision.capture(self._hwnd)

            fireball_x = self.vision.closest_fireball_x(color)
            target_x = fireball_x if fireball_x is not None else center_x
            self.ctrl.move(target_x, platform_y)

            frame_count += 1
            if frame_count % cfg.BATTLE_EXIT_CHECK_EVERY == 0:
                if self.vision.find(gray, 'out_of_resources'):
                    self._dismiss_out_of_resources(gray)
                    self.state = State.IDLE
                    self.ctrl.release_focus()
                    return

                if self.vision.find(gray, 'battle_success', thresh=cfg.THRESH_BATTLE_SUCCESS):
                    pos = (self.vision.find(gray, 'continue_btn')
                           or self.vision.find(gray, 'back_arrow'))
                    if pos:
                        log.success("Battle won — collecting reward")
                        self.ctrl.click(pos[0], pos[1])
                        time.sleep(cfg.POST_GAME_PAUSE)
                    self.state = State.IDLE
                    self.ctrl.release_focus()
                    return

                if self.vision.is_craft_available(gray):
                    log.action("BATTLE", "Craft available — switching priority")
                    self.state = State.CRAFT
                    self.craft_round = 0
                    self.ctrl.release_focus()
                    return

                if self.vision.is_battle_on_cooldown(gray):
                    log.cooldown("Battle")
                    self.state = State.IDLE
                    self.ctrl.release_focus()
                    return

            time.sleep(cfg.BATTLE_LOOP_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    Bot().run()
