"""
Meadow MMO Discord Bot
======================
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
        self.ctrl   = GameController()
        self.state  = State.IDLE

        self.craft_round    = 0
        self.battle_btn_pos: tuple | None = None

        self._idle_frames = 0
        self._stop = threading.Event()
        self._hwnd: int | None = None
        self._rect: tuple | None = None

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
            if win32gui.IsWindowVisible(hwnd) and 'Discord' in win32gui.GetWindowText(hwnd):
                found.append(hwnd)
        win32gui.EnumWindows(cb, None)
        if found:
            self._hwnd = found[0]
            win32gui.SetForegroundWindow(self._hwnd)
            self._rect = win32gui.GetWindowRect(self._hwnd)

    def _get_rect(self) -> tuple | None:
        if self._hwnd is None:
            self._refresh_window()
        elif self._rect:
            self._rect = win32gui.GetWindowRect(self._hwnd)
        return self._rect

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        log.banner()
        log.separator()
        log.system("Initializing modules")
        log.info("SYS", f"Vision engine loaded — {len(self.vision.templates)} templates")
        log.info("SYS", f"Arrow templates — {len(self.vision.arrow_templates)}/4 loaded")
        log.info("SYS", f"Controller ready")
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

        log.separator()
        log.system("Bot is now running")
        log.separator()

        while not self._stop.is_set():
            rect = self._get_rect()
            if not rect:
                log.warn("Discord window lost — retrying")
                time.sleep(cfg.WINDOW_RETRY_DELAY)
                self._refresh_window()
                continue

            color, gray = self.vision.capture(rect)
            self._tick(gray, color, rect)
            time.sleep(cfg.MAIN_LOOP_INTERVAL)

        log.separator()
        log.system("Bot stopped — session ended")
        log.separator()

    # ── State machine ─────────────────────────────────────────────────────

    def _tick(self, gray, color, rect):
        # Global out-of-resources check
        if self.vision.find(gray, 'out_of_resources'):
            self._dismiss_out_of_resources(gray, rect)
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
                    self.ctrl.click(rect[0] + back[0], rect[1] + back[1])
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
            self._adventure(gray, rect)
        elif self.state == State.CRAFT:
            self._craft(gray, rect)
        elif self.state == State.BATTLE:
            self._battle(gray, color, rect)

    # ── Adventure ─────────────────────────────────────────────────────────

    def _adventure(self, gray, rect):
        pos = (self.vision.find(gray, 'adventure_btn',      thresh=cfg.THRESH_ADVENTURE_BTN) or
               self.vision.find(gray, 'adventure_progress', thresh=cfg.THRESH_ADVENTURE_ALT) or
               self.vision.find(gray, 'adventure_complete', thresh=cfg.THRESH_ADVENTURE_ALT))
        if pos is None:
            return

        abs_x = rect[0] + pos[0]
        abs_y = rect[1] + pos[1]

        self.ctrl.move(abs_x, abs_y)
        log.action("ADV", f"Engaging adventure at ({abs_x}, {abs_y})")

        frame_count = 0
        while not self._stop.is_set():
            self.ctrl.click(abs_x, abs_y)
            time.sleep(cfg.ADVENTURE_CLICK_INTERVAL)

            frame_count += 1
            if frame_count % cfg.ADVENTURE_CHECK_EVERY == 0:
                if self._hwnd:
                    rect = win32gui.GetWindowRect(self._hwnd)
                _, gray = self.vision.capture(rect)

                if self.vision.find(gray, 'out_of_resources'):
                    self._dismiss_out_of_resources(gray, rect)
                    self.state = State.IDLE
                    return

                if self.vision.is_craft_available(gray):
                    log.action("ADV", "Craft available — switching priority")
                    self.state = State.CRAFT
                    self.craft_round = 0
                    return

                if self.vision.is_battle_available(gray):
                    log.action("ADV", "Battle available — switching priority")
                    self.state = State.BATTLE
                    return

    # ── Craft ─────────────────────────────────────────────────────────────

    def _craft(self, gray, rect):
        def get_rect():
            return win32gui.GetWindowRect(self._hwnd) if self._hwnd else rect

        def abs_click(pos, r):
            self.ctrl.click(r[0] + pos[0], r[1] + pos[1])

        inside = self.vision.find(gray, 'craft_star_0', thresh=cfg.THRESH_CRAFT_STAR) is not None
        if not inside:
            craft_btn_pos = self.vision.find(gray, 'craft_btn', thresh=cfg.THRESH_CRAFT_BTN)
            if craft_btn_pos:
                if self._hwnd:
                    win32gui.SetForegroundWindow(self._hwnd)
                    time.sleep(cfg.BUTTON_FOCUS_DELAY)
                log.action("CRAFT", "Entering craft game")
                self.ctrl.move(rect[0] + craft_btn_pos[0], rect[1] + craft_btn_pos[1])
                time.sleep(cfg.PRE_CLICK_DELAY)
                self.ctrl.click(rect[0] + craft_btn_pos[0], rect[1] + craft_btn_pos[1])
                time.sleep(cfg.CRAFT_LOAD_DELAY)
                rect = get_rect()
                _, gray = self.vision.capture(rect)

        log.info("CRAFT", "Craft loop active — awaiting arrows")

        while not self._stop.is_set():
            rect = get_rect()
            _, gray = self.vision.capture(rect)

            if self.vision.find(gray, 'craft_success', thresh=cfg.THRESH_CRAFT_SUCCESS):
                pos = self.vision.find(gray, 'continue_btn')
                if pos:
                    log.success("Craft complete — collecting reward")
                    abs_click(pos, rect)
                    self.craft_round = 0
                    time.sleep(cfg.POST_GAME_PAUSE)
                self.state = State.IDLE
                return

            if self.vision.is_craft_on_cooldown(gray):
                log.cooldown("Craft")
                self.state = State.IDLE
                return

            arrows = self.vision.detect_arrows(gray)
            if arrows:
                log.action("CRAFT", f"Round {self.craft_round + 1}/3 — sequence: {' '.join(arrows)}")
                for key in arrows:
                    self.ctrl.press_key(key)
                    time.sleep(cfg.CRAFT_ARROW_DELAY)
                    rect = get_rect()
                    _, gray = self.vision.capture(rect)
                self.craft_round += 1
                time.sleep(cfg.CRAFT_ROUND_PAUSE)
            else:
                time.sleep(cfg.MAIN_LOOP_INTERVAL)

    # ── Out-of-resources dismissal ────────────────────────────────────────

    def _dismiss_out_of_resources(self, gray, rect):
        log.obstacle("Obstacle detected — out of resources — circumventing")

        win_w = rect[2] - rect[0]
        win_h = rect[3] - rect[1]

        btn = self.vision.find(gray, 'out_of_resources_btn')
        if btn:
            log.info("OBSTACLE", "Dismiss button found — clicking")
            self.ctrl.click(rect[0] + btn[0], rect[1] + btn[1])
        else:
            log.info("OBSTACLE", "No dismiss button — clicking neutral area")
            self.ctrl.click(rect[0] + win_w // 4, rect[1] + win_h // 4)

        time.sleep(cfg.OOR_DISMISS_WAIT)

        if self._hwnd:
            rect = win32gui.GetWindowRect(self._hwnd)
        _, gray = self.vision.capture(rect)

        if self.vision.find(gray, 'out_of_resources'):
            log.info("OBSTACLE", "Still visible — retrying with neutral click")
            self.ctrl.click(rect[0] + win_w // 4, rect[1] + win_h // 4)
            time.sleep(cfg.OOR_NEUTRAL_CLICK_WAIT)
            _, gray = self.vision.capture(rect)

        if self.vision.find(gray, 'out_of_resources'):
            log.info("OBSTACLE", "Fallback — sending Escape key")
            kb = pkb.Controller()
            kb.press(pkb.Key.esc)
            kb.release(pkb.Key.esc)
            time.sleep(cfg.OOR_ESCAPE_WAIT)

        log.success("Obstacle cleared — resuming operations")

    # ── Battle ────────────────────────────────────────────────────────────

    def _battle(self, gray, color, rect):
        def abs_click(pos):
            self.ctrl.click(rect[0] + pos[0], rect[1] + pos[1])

        btn = self.vision.find(gray, 'battle_btn', thresh=cfg.THRESH_BATTLE_BTN)
        if btn:
            if self._hwnd:
                win32gui.SetForegroundWindow(self._hwnd)
                time.sleep(cfg.BUTTON_FOCUS_DELAY)
            log.action("BATTLE", "Entering battle game")
            self.ctrl.move(rect[0] + btn[0], rect[1] + btn[1])
            time.sleep(cfg.PRE_CLICK_DELAY)
            abs_click(btn)

            poll_iters = int(cfg.BATTLE_LOAD_TIMEOUT / cfg.BATTLE_LOAD_POLL)
            for _ in range(poll_iters):
                time.sleep(cfg.BATTLE_LOAD_POLL)
                if self._hwnd:
                    rect = win32gui.GetWindowRect(self._hwnd)
                color, gray = self.vision.capture(rect)
                if self.vision.find(gray, 'battle_btn', thresh=cfg.THRESH_BATTLE_BTN) is None:
                    break

        platform_pos = self.vision.find(gray, 'battle_platform', thresh=cfg.THRESH_BATTLE_PLATFORM)
        win_w = rect[2] - rect[0]
        win_h = rect[3] - rect[1]
        platform_y = platform_pos[1] if platform_pos else int(win_h * cfg.PLATFORM_Y_FALLBACK)
        center_x   = rect[0] + win_w // 2
        frame_count = 0

        self.ctrl.move(center_x, rect[1] + platform_y)
        log.info("BATTLE", "Tracking active — intercepting fireballs")

        while not self._stop.is_set():
            if self._hwnd:
                rect = win32gui.GetWindowRect(self._hwnd)

            color, gray = self.vision.capture(rect)

            fireball_x = self.vision.closest_fireball_x(color)
            target_x = (rect[0] + fireball_x) if fireball_x is not None else center_x
            self.ctrl.move(target_x, rect[1] + platform_y)

            frame_count += 1
            if frame_count % cfg.BATTLE_EXIT_CHECK_EVERY == 0:
                if self.vision.find(gray, 'out_of_resources'):
                    self._dismiss_out_of_resources(gray, rect)
                    self.state = State.IDLE
                    return

                if self.vision.find(gray, 'battle_success', thresh=cfg.THRESH_BATTLE_SUCCESS):
                    pos = (self.vision.find(gray, 'continue_btn')
                           or self.vision.find(gray, 'back_arrow'))
                    if pos:
                        log.success("Battle won — collecting reward")
                        abs_click(pos)
                        time.sleep(cfg.POST_GAME_PAUSE)
                    self.state = State.IDLE
                    return

                if self.vision.is_craft_available(gray):
                    log.action("BATTLE", "Craft available — switching priority")
                    self.state = State.CRAFT
                    self.craft_round = 0
                    return

                if self.vision.is_battle_on_cooldown(gray):
                    log.cooldown("Battle")
                    self.state = State.IDLE
                    return

            time.sleep(cfg.BATTLE_LOOP_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    Bot().run()
