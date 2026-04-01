import os
import cv2
import numpy as np
import json
import base64
import requests
import websocket
import config as cfg
import logger as log

_CDP_PORT = 9222

class GameVision:
    _TEMPLATES = {
        # Adventure
        'adventure_btn':        'assets/adv/btn.png',
        'adventure_progress':   'assets/adv/btn_progress.png',
        'adventure_complete':   'assets/adv/btn_complete.png',
        # Craft
        'craft_btn':            'assets/craft/btn.png',
        'craft_success':        'assets/craft/success.png',
        'craft_star_0':         'assets/craft/star_0.png',
        'craft_star_1':         'assets/craft/star_1.png',
        'craft_star_2':         'assets/craft/star_2.png',
        # Battle
        'battle_btn':           'assets/battle/btn.png',
        'battle_success':       'assets/battle/success.png',
        'battle_platform':      'assets/battle/platform.png',
        # Shared UI
        'cooldown_clock':       'assets/ui/clock.png',
        'continue_btn':         'assets/ui/continue.png',
        'back_arrow':           'assets/ui/back.png',
        'out_of_resources':     'assets/ui/no_resources.png',
        'out_of_resources_btn': 'assets/ui/no_resources_btn.png',
    }

    # HSV range for the green fireballs
    _GREEN_LOW  = np.array(cfg.FIREBALL_HSV_LOW,  dtype=np.uint8)
    _GREEN_HIGH = np.array(cfg.FIREBALL_HSV_HIGH, dtype=np.uint8)

    def __init__(self):
        self.templates: dict[str, np.ndarray] = {}
        self.arrow_templates: dict[str, np.ndarray] = {}
        self._scale = 1.0
        self._cdp_ws = None
        self._cdp_id = 0
        self._connect_cdp()
        self._load_templates()
        self._extract_arrow_templates()

    # ── Template loading ──────────────────────────────────────────────────

    def _load_templates(self):
        for key, fname in self._TEMPLATES.items():
            if os.path.exists(fname):
                img = cv2.imread(fname, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[key] = img
            else:
                if key != 'battle_btn':
                    log.warn(f"Missing template: {fname}")

    def _extract_arrow_templates(self):
        """Load individual arrow direction templates from live-game screenshots."""
        arrow_files = {
            'right': 'assets/craft/arrow_right.png',
            'left':  'assets/craft/arrow_left.png',
            'down':  'assets/craft/arrow_down.png',
            'up':    'assets/craft/arrow_up.png',
        }
        for direction, fname in arrow_files.items():
            if os.path.exists(fname):
                img = cv2.imread(fname, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.arrow_templates[direction] = img
                else:
                    log.warn(f"Could not load arrow template: {fname}")
            else:
                log.warn(f"Missing arrow template: {fname}")
        if len(self.arrow_templates) < 4:
            log.warn("Not all arrow templates loaded — craft detection may fail")

    # ── Calibration ────────────────────────────────────────────────────────

    def recalibrate(self, gray: np.ndarray):
        """Reload original templates from disk and re-run calibration."""
        self._load_templates()
        self._extract_arrow_templates()
        self.calibrate(gray)

    def calibrate(self, gray: np.ndarray):
        """Try all scales against a few key templates, lock in the best one."""
        test_keys = [k for k in ('craft_btn', 'battle_btn', 'adventure_btn',
                                  'cooldown_clock', 'back_arrow')
                     if k in self.templates]
        if not test_keys:
            return

        best_scale, best_val = 1.0, -1
        for scale in cfg.MATCH_SCALES:
            total = 0
            for key in test_keys:
                tmpl = self.templates[key]
                scaled = self._resize(tmpl, scale)
                if scaled is None:
                    continue
                th, tw = scaled.shape[:2]
                if gray.shape[0] < th or gray.shape[1] < tw:
                    continue
                res = cv2.matchTemplate(gray, scaled, cv2.TM_CCOEFF_NORMED)
                _, val, _, _ = cv2.minMaxLoc(res)
                total += val
            log.info("CAL", f"Scale {scale:.1f}x — score: {total:.3f}")
            if total > best_val:
                best_val = total
                best_scale = scale

        self._scale = best_scale
        avg_score = best_val / len(test_keys) if test_keys else 0
        log.system(f"Calibrated scale: {best_scale:.1f}x (avg match: {avg_score:.3f})")

        # Pre-scale all templates so every future match is single-pass
        if best_scale != 1.0:
            for key, tmpl in self.templates.items():
                scaled = self._resize(tmpl, best_scale)
                if scaled is not None:
                    self.templates[key] = scaled
            for direction, tmpl in self.arrow_templates.items():
                scaled = self._resize(tmpl, best_scale)
                if scaled is not None:
                    self.arrow_templates[direction] = scaled

    def _resize(self, tmpl: np.ndarray, scale: float) -> np.ndarray | None:
        if scale == 1.0:
            return tmpl
        h, w = tmpl.shape[:2]
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w < 4 or new_h < 4:
            return None
        return cv2.resize(tmpl, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # ── CDP connection ──────────────────────────────────────────────────

    def _connect_cdp(self):
        try:
            r = requests.get(f'http://localhost:{_CDP_PORT}/json', timeout=5)
            pages = r.json()
            page = next(p for p in pages if p.get('type') == 'page')
            self._cdp_ws = websocket.create_connection(page['webSocketDebuggerUrl'])
        except Exception:
            self._cdp_ws = None

    def _cdp_send(self, method: str, params: dict = None):
        if not self._cdp_ws:
            self._connect_cdp()
        if not self._cdp_ws:
            return None
        self._cdp_id += 1
        msg_id = self._cdp_id
        msg = {'id': msg_id, 'method': method, 'params': params or {}}
        try:
            self._cdp_ws.settimeout(5)
            self._cdp_ws.send(json.dumps(msg))
            # Loop until we get OUR response (skip async CDP events)
            for _ in range(50):
                data = json.loads(self._cdp_ws.recv())
                if data.get('id') == msg_id:
                    return data
                # else it's an event — discard and keep reading
            return None
        except Exception:
            log.warn("CDP vision connection lost -- reconnecting")
            self._cdp_ws = None
            self._connect_cdp()
            return None

    # ── Capture (CDP screenshot — fully background) ──────────────────

    def capture(self, _hwnd=None) -> tuple[np.ndarray, np.ndarray]:
        """Capture Discord via CDP screenshot. Works on any desktop,
        minimized, or behind other windows."""
        result = self._cdp_send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 80})
        if not result or 'result' not in result:
            empty = np.zeros((1, 1, 3), dtype=np.uint8)
            return empty, empty[:, :, 0]

        data = result['result'].get('data', '')
        img_bytes = base64.b64decode(data)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        color = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
        return color, gray

    # ── Template matching (single-pass, uses pre-scaled templates) ────────

    def find(self, gray: np.ndarray, key: str, thresh: float = 0.75):
        """Brightness-invariant match (TM_CCOEFF_NORMED)."""
        tmpl = self.templates.get(key)
        if tmpl is None or gray is None:
            return None
        th, tw = tmpl.shape[:2]
        if gray.shape[0] < th or gray.shape[1] < tw:
            return None
        res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        if val >= thresh:
            return (loc[0] + tw // 2, loc[1] + th // 2)
        return None

    def find_all(self, gray: np.ndarray, key: str, thresh: float = 0.75):
        """Return list of all (cx, cy) matches above threshold."""
        tmpl = self.templates.get(key)
        if tmpl is None or gray is None:
            return []
        th, tw = tmpl.shape[:2]
        if gray.shape[0] < th or gray.shape[1] < tw:
            return []
        res  = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        locs = np.where(res >= thresh)
        return [(int(x) + tw // 2, int(y) + th // 2)
                for y, x in zip(*locs)]

    # ── Availability helpers ──────────────────────────────────────────────

    def _clock_near(self, gray: np.ndarray, btn_pos: tuple, radius: int = None) -> bool:
        """Return True if the clock icon is found within 'radius' px of btn_pos."""
        if radius is None:
            radius = cfg.CLOCK_SEARCH_RADIUS
        tmpl = self.templates.get('cooldown_clock')
        if tmpl is None or btn_pos is None:
            return False
        cx, cy = btn_pos
        th, tw = tmpl.shape[:2]
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(gray.shape[1], cx + radius)
        y2 = min(gray.shape[0], cy + radius)
        region = gray[y1:y2, x1:x2]
        if region.shape[0] < th or region.shape[1] < tw:
            return False
        res = cv2.matchTemplate(region, tmpl, cv2.TM_CCOEFF_NORMED)
        _, val, _, _ = cv2.minMaxLoc(res)
        return val >= cfg.THRESH_CLOCK

    def is_craft_available(self, gray: np.ndarray) -> bool:
        pos = self.find(gray, 'craft_btn', cfg.THRESH_CRAFT_BTN)
        return pos is not None and not self._clock_near(gray, pos)

    def is_craft_on_cooldown(self, gray: np.ndarray) -> bool:
        pos = self.find(gray, 'craft_btn', cfg.THRESH_CRAFT_BTN)
        return pos is not None and self._clock_near(gray, pos)

    def is_battle_available(self, gray: np.ndarray) -> bool:
        pos = self.find(gray, 'battle_btn', cfg.THRESH_BATTLE_BTN)
        return pos is not None and not self._clock_near(gray, pos)

    def is_battle_on_cooldown(self, gray: np.ndarray) -> bool:
        pos = self.find(gray, 'battle_btn', cfg.THRESH_BATTLE_BTN)
        return pos is not None and self._clock_near(gray, pos)

    def craft_star_count(self, gray: np.ndarray) -> int:
        """Return how many stars are currently filled (0, 1, or 2)."""
        if self.find(gray, 'craft_star_2', cfg.THRESH_CRAFT_STAR):
            return 2
        if self.find(gray, 'craft_star_1', cfg.THRESH_CRAFT_STAR):
            return 1
        return 0

    # ── Craft arrow detection ─────────────────────────────────────────────

    def detect_arrows(self, gray: np.ndarray) -> list[str] | None:
        """
        Find the 7-arrow row and return directions e.g. ['right','down','left',...].
        Returns None if the arrow row is not visible.
        """
        if not self.arrow_templates:
            return None

        avg_h = int(np.mean([t.shape[0] for t in self.arrow_templates.values()]))

        # Collect all hits with score: (x, y, direction, score)
        hits = []
        for direction, tmpl in self.arrow_templates.items():
            th, tw = tmpl.shape[:2]
            if gray.shape[0] < th or gray.shape[1] < tw:
                continue
            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= cfg.THRESH_ARROWS)
            for y, x in zip(*locs):
                hits.append((int(x) + tw // 2, int(y) + th // 2,
                              direction, float(res[y, x])))

        if len(hits) < cfg.ARROW_MIN_HITS:
            return None

        # Find arrow row by Y clustering
        ys = np.array([h[1] for h in hits])
        median_y = int(np.median(ys))
        row_hits = [h for h in hits if abs(h[1] - median_y) < avg_h]

        if not row_hits:
            return None

        row_hits.sort(key=lambda h: h[0])

        # Cluster by X — live arrows are larger than templates so one arrow
        # generates many hits. Merge hits within ARROW_MERGE_DIST into one cluster.
        clusters: list[list] = []
        for h in row_hits:
            if not clusters or h[0] - clusters[-1][-1][0] > cfg.ARROW_MERGE_DIST:
                clusters.append([h])
            else:
                clusters[-1].append(h)

        if len(clusters) < cfg.ARROW_MIN_CLUSTERS:
            return None

        # Take first 7 clusters sorted by X, pick best-scoring hit per cluster
        clusters = sorted(clusters, key=lambda c: c[0][0])[:cfg.ARROW_MIN_CLUSTERS]
        directions = [max(c, key=lambda h: h[3])[2] for c in clusters]
        return directions

    # ── Dragon / Battle game ──────────────────────────────────────────────

    def closest_fireball_x(self, color: np.ndarray) -> int | None:
        """
        Detect all green fireballs. Uses a weighted score that prioritizes
        fireballs closest to the bottom (most urgent) but also considers
        fireballs that are slightly higher if they're more centered.
        Returns X of the most urgent fireball, or None.
        """
        hsv  = cv2.cvtColor(color, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._GREEN_LOW, self._GREEN_HIGH)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        fireballs = []
        for cnt in contours:
            if cv2.contourArea(cnt) < cfg.FIREBALL_MIN_AREA:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            fireballs.append((x + w // 2, y + h))  # (center_x, bottom_y)

        if not fireballs:
            return None

        # Sort by bottom Y descending — most urgent first
        fireballs.sort(key=lambda f: f[1], reverse=True)

        # If top fireball is in the bottom 40% of the screen, it's urgent
        img_h = color.shape[0]
        urgent_zone = img_h * 0.6

        # Return the lowest fireball, but if there's one very close behind
        # (within 15% of screen height), prefer the one more to the side
        # we're already near (reduces back-and-forth)
        return fireballs[0][0]
