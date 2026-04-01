"""
Meadow MMO Discord Bot — CDP Mode
===================================
Runs fully in the background via Chrome DevTools Protocol.
No cursor movement, no window focus required.
Works across virtual desktops, minimized, behind other windows.

Priority:  Craft (available) > Battle (available) > Adventure (fallback)
Press F at any time to stop the bot.

Requires Discord launched with:
  --remote-debugging-port=9222 --remote-allow-origins=*
"""

import time
import threading
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

        self._idle_frames = 0
        self._stop = threading.Event()

    # ── Stop key ─────────────────────────────────────────────────────────

    def _start_hotkey(self):
        def on_press(key):
            try:
                if hasattr(key, 'char') and key.char and key.char.lower() == 'f':
                    # Only stop on F5 or Ctrl+F to avoid accidental triggers
                    pass
            except AttributeError:
                pass
            # Use F6 as the kill key — unlikely to be pressed accidentally
            if key == pkb.Key.f6:
                log.separator()
                log.system("Kill signal received (F6) — shutting down")
                self._stop.set()
                return False
        pkb.Listener(on_press=on_press, daemon=True).start()

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        log.banner()
        log.separator()
        log.system("Initializing modules")
        log.info("SYS", f"Vision engine loaded — {len(self.vision.templates)} templates")
        log.info("SYS", f"Arrow templates — {len(self.vision.arrow_templates)}/4 loaded")
        log.info("SYS", "Controller ready (CDP mode — fully background)")
        log.separator()

        log.system(f"Starting in {cfg.STARTUP_DELAY}s — press F6 to stop")
        self._start_hotkey()
        time.sleep(cfg.STARTUP_DELAY)

        # Calibrate template scale
        log.system("Calibrating templates to screen")
        _, gray = self.vision.capture()
        self.vision.calibrate(gray)
        self._last_capture_size = gray.shape[:2]

        # Inject status overlay into Discord
        self.ctrl.inject_overlay()

        log.separator()
        log.system("Bot is now running")
        log.separator()

        while not self._stop.is_set():
            color, gray = self.vision.capture()

            # Re-calibrate if window was resized
            cur_size = gray.shape[:2]
            if cur_size != self._last_capture_size and cur_size[0] > 1:
                log.system(f"Window resized — recalibrating")
                self.vision.recalibrate(gray)
                self._last_capture_size = cur_size

            try:
                self._tick(gray, color)
            except Exception as e:
                log.error(f"Tick error: {e} — recovering")
                self.state = State.IDLE
                time.sleep(1)
            time.sleep(cfg.MAIN_LOOP_INTERVAL)

        self.ctrl.update_status('IDLE', 'stopped')
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

        if craft_avail and self.state != State.CRAFT:
            self._idle_frames = 0
            log.state_change(self.state.name, "CRAFT")
            self.state = State.CRAFT
            self.craft_round = 0
            self.ctrl.update_status('CRAFT', 'entering game')

        elif (not craft_avail
              and battle_avail
              and self.state not in (State.CRAFT, State.BATTLE)):
            self._idle_frames = 0
            log.state_change(self.state.name, "BATTLE")
            self.state = State.BATTLE
            self.ctrl.update_status('BATTLE', 'entering game')

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
                self.ctrl.update_status('ADVENTURE', 'clicking')
            return

        if self.state == State.CRAFT and self.vision.is_craft_on_cooldown(gray):
            log.cooldown("Craft")
            self.state = State.IDLE
            self.ctrl.update_status('IDLE', 'craft on cooldown')
            return

        if self.state == State.BATTLE and self.vision.is_battle_on_cooldown(gray):
            log.cooldown("Battle")
            self.state = State.IDLE
            self.ctrl.update_status('IDLE', 'battle on cooldown')
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

        log.action("ADV", f"Engaging adventure at ({pos[0]}, {pos[1]})")

        frame_count = 0
        while not self._stop.is_set():
            self.ctrl.click(pos[0], pos[1])
            time.sleep(cfg.ADVENTURE_CLICK_INTERVAL)

            frame_count += 1
            if frame_count % cfg.ADVENTURE_CHECK_EVERY == 0:
                _, gray = self.vision.capture()

                if self.vision.find(gray, 'out_of_resources'):
                    self._dismiss_out_of_resources(gray)
                    self.state = State.IDLE
                    return

                if self.vision.is_craft_available(gray):
                    log.action("ADV", "Craft available — switching priority")
                    self.state = State.CRAFT
                    self.craft_round = 0
                    self.ctrl.update_status('CRAFT', 'entering game')
                    return

                if self.vision.is_battle_available(gray):
                    log.action("ADV", "Battle available — switching priority")
                    self.state = State.BATTLE
                    self.ctrl.update_status('BATTLE', 'entering game')
                    return

    # ── Craft ─────────────────────────────────────────────────────────────

    def _craft(self, gray):
        # Enter craft game
        inside = self.vision.find(gray, 'craft_star_0', thresh=cfg.THRESH_CRAFT_STAR) is not None
        if not inside:
            craft_btn_pos = self.vision.find(gray, 'craft_btn', thresh=cfg.THRESH_CRAFT_BTN)
            if craft_btn_pos:
                log.action("CRAFT", "Entering craft game")
                self.ctrl.click(craft_btn_pos[0], craft_btn_pos[1])
                time.sleep(cfg.CRAFT_LOAD_DELAY)
                _, gray = self.vision.capture()

        log.info("CRAFT", "Craft loop active — awaiting arrows")

        while not self._stop.is_set():
            _, gray = self.vision.capture()

            if self.vision.find(gray, 'craft_success', thresh=cfg.THRESH_CRAFT_SUCCESS):
                pos = self.vision.find(gray, 'continue_btn')
                if pos:
                    log.success("Craft complete — collecting reward")
                    self.ctrl.update_status('CRAFT', 'complete!')
                    self.ctrl.click(pos[0], pos[1])
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
                self.ctrl.update_status('CRAFT', f'round {self.craft_round + 1}/3')
                for key in arrows:
                    self.ctrl.press_key(key)
                    time.sleep(cfg.CRAFT_ARROW_DELAY)
                    _, gray = self.vision.capture()
                self.craft_round += 1
                time.sleep(cfg.CRAFT_ROUND_PAUSE)
            else:
                time.sleep(cfg.MAIN_LOOP_INTERVAL)

    # ── Out-of-resources dismissal ────────────────────────────────────────

    def _dismiss_out_of_resources(self, gray):
        log.obstacle("Obstacle detected — out of resources — circumventing")
        self.ctrl.update_status('OBSTACLE', 'out of resources')

        btn = self.vision.find(gray, 'out_of_resources_btn')
        if btn:
            log.info("OBSTACLE", "Dismiss button found — clicking")
            self.ctrl.click(btn[0], btn[1])
        else:
            log.info("OBSTACLE", "No dismiss button — clicking neutral area")
            # Use a neutral spot based on last capture size
            h, w = gray.shape[:2]
            self.ctrl.click(w // 4, h // 4)

        time.sleep(cfg.OOR_DISMISS_WAIT)

        _, gray = self.vision.capture()

        if self.vision.find(gray, 'out_of_resources'):
            log.info("OBSTACLE", "Still visible — retrying with neutral click")
            h, w = gray.shape[:2]
            self.ctrl.click(w // 4, h // 4)
            time.sleep(cfg.OOR_NEUTRAL_CLICK_WAIT)
            _, gray = self.vision.capture()

        if self.vision.find(gray, 'out_of_resources'):
            log.info("OBSTACLE", "Fallback — sending Escape key")
            self.ctrl.press_key('esc')
            time.sleep(cfg.OOR_ESCAPE_WAIT)

        log.success("Obstacle cleared — resuming operations")

    # ── Battle ────────────────────────────────────────────────────────────

    def _battle(self, gray, color):
        # Enter battle
        btn = self.vision.find(gray, 'battle_btn', thresh=cfg.THRESH_BATTLE_BTN)
        if btn:
            log.action("BATTLE", "Entering battle game")
            self.ctrl.click(btn[0], btn[1])

            # Poll for the button to disappear (game loaded)
            poll_iters = int(cfg.BATTLE_LOAD_TIMEOUT / cfg.BATTLE_LOAD_POLL)
            for _ in range(poll_iters):
                time.sleep(cfg.BATTLE_LOAD_POLL)
                color, gray = self.vision.capture()
                if self.vision.find(gray, 'battle_btn', thresh=cfg.THRESH_BATTLE_BTN) is None:
                    break

        # Inside the game
        platform_pos = self.vision.find(gray, 'battle_platform', thresh=cfg.THRESH_BATTLE_PLATFORM)
        h, w = gray.shape[:2]
        platform_y = platform_pos[1] if platform_pos else int(h * cfg.PLATFORM_Y_FALLBACK)
        center_x   = w // 2
        frame_count = 0

        self.ctrl.move(center_x, platform_y)
        log.info("BATTLE", "Tracking active — intercepting fireballs")
        self.ctrl.update_status('BATTLE', 'tracking fireballs')

        while not self._stop.is_set():
            color, gray = self.vision.capture()

            fireball_x = self.vision.closest_fireball_x(color)
            target_x = fireball_x if fireball_x is not None else center_x
            self.ctrl.move(target_x, platform_y)

            frame_count += 1
            if frame_count % cfg.BATTLE_EXIT_CHECK_EVERY == 0:
                if self.vision.find(gray, 'out_of_resources'):
                    self._dismiss_out_of_resources(gray)
                    self.state = State.IDLE
                    return

                if self.vision.find(gray, 'battle_success', thresh=cfg.THRESH_BATTLE_SUCCESS):
                    pos = (self.vision.find(gray, 'continue_btn')
                           or self.vision.find(gray, 'back_arrow'))
                    if pos:
                        log.success("Battle won — collecting reward")
                        self.ctrl.update_status('BATTLE', 'won!')
                        self.ctrl.click(pos[0], pos[1])
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
