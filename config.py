"""
Adjustable Configuration
========================
Tweak these values to fine-tune bot behaviour.
Defaults shown are the recommended settings.
"""

# ─── Timing (seconds) ────────────────────────────────────────────────────────

# Main loop interval — how often the bot checks for state changes
MAIN_LOOP_INTERVAL       = 0.05       # 50 ms  (recommended)

# Battle inner-loop interval — lower = smoother tracking, higher = less CPU
BATTLE_LOOP_INTERVAL     = 0.003      # 3 ms   (recommended)

# Adventure click interval — time between each auto-click
ADVENTURE_CLICK_INTERVAL = 0.045      # 45 ms  (recommended)

# Craft arrow key delay — time between pressing each arrow key
CRAFT_ARROW_DELAY        = 0.75       # 750 ms (recommended)

# Pause after completing a craft/battle round (lets cooldown appear)
POST_GAME_PAUSE          = 1.0        # 1.0 s  (recommended)

# Delay after clicking a game button (window focus settle time)
BUTTON_FOCUS_DELAY       = 0.2        # 200 ms (recommended)

# Delay before clicking a button (mouse moves first, then clicks)
PRE_CLICK_DELAY          = 0.3        # 300 ms (recommended)

# Delay after clicking craft button (wait for game to load)
CRAFT_LOAD_DELAY         = 1.0        # 1.0 s  (recommended)

# Pause after finishing a craft arrow sequence round
CRAFT_ROUND_PAUSE        = 0.5        # 500 ms (recommended)

# Back arrow retry delay when no buttons are visible
BACK_ARROW_DELAY         = 0.5        # 500 ms (recommended)

# Startup delay before the bot begins
STARTUP_DELAY            = 3          # 3 s    (recommended)

# Discord window settle time after initial focus
WINDOW_SETTLE_DELAY      = 0.5        # 500 ms (recommended)

# Retry delay when Discord window is not found
WINDOW_RETRY_DELAY       = 1          # 1 s    (recommended)

# ─── Out-of-Resources Popup ──────────────────────────────────────────────────

# Wait time after clicking dismiss button before re-checking
OOR_DISMISS_WAIT         = 1.0        # 1.0 s  (recommended)

# Wait after neutral-area click fallback
OOR_NEUTRAL_CLICK_WAIT   = 0.5        # 500 ms (recommended)

# Wait after Escape fallback
OOR_ESCAPE_WAIT          = 0.5        # 500 ms (recommended)

# ─── Battle Entry ────────────────────────────────────────────────────────────

# Max time to wait for battle game to load (polls every 100 ms)
BATTLE_LOAD_TIMEOUT      = 5.0        # 5.0 s  (recommended)

# Poll interval while waiting for battle to load
BATTLE_LOAD_POLL         = 0.1        # 100 ms (recommended)

# Platform Y fallback — percentage of window height (used when platform
# template is not detected)
PLATFORM_Y_FALLBACK      = 0.87       # 87%    (recommended)

# ─── State Machine ───────────────────────────────────────────────────────────

# Consecutive idle frames required before falling back to adventure
IDLE_FRAMES_BEFORE_ADV   = 3          # frames (recommended)

# In battle, run expensive exit-condition checks every N frames
BATTLE_EXIT_CHECK_EVERY  = 8          # frames (recommended)

# In adventure, check craft/battle availability every N clicks
ADVENTURE_CHECK_EVERY    = 4          # clicks (recommended)

# ─── Template Matching Thresholds ────────────────────────────────────────────
# Higher = stricter matching (fewer false positives, may miss real matches)
# Lower  = looser matching  (more detections, but more false positives)

THRESH_CRAFT_BTN         = 0.65       # craft button detection
THRESH_BATTLE_BTN        = 0.75       # battle button detection
THRESH_ADVENTURE_BTN     = 0.72       # adventure button detection
THRESH_ADVENTURE_ALT     = 0.65       # adventure progress / complete indicator
THRESH_CRAFT_SUCCESS     = 0.72       # craft success screen
THRESH_CRAFT_STAR        = 0.55       # craft star (entry guard)
THRESH_BATTLE_SUCCESS    = 0.72       # battle success screen
THRESH_BATTLE_PLATFORM   = 0.60       # battle platform (UFO) detection
THRESH_CLOCK             = 0.80       # cooldown clock icon
THRESH_ARROWS            = 0.65       # craft arrow key detection

# ─── Multi-Scale Matching ────────────────────────────────────────────────────
# Scales to try when matching templates — covers smaller and larger screens
# 1.0 = original size. Range goes from 50% to 150% of the template size.
MATCH_SCALES             = [1.0, 0.9, 1.1, 0.8, 1.2, 0.7, 1.3, 0.6, 1.4, 0.5, 1.5, 0.4, 0.3]

# ─── Vision / Detection ─────────────────────────────────────────────────────

# Green fireball HSV colour range  [H, S, V]
FIREBALL_HSV_LOW         = (35, 80, 80)
FIREBALL_HSV_HIGH        = (85, 255, 255)

# Minimum contour area (px²) to count as a fireball — filters noise
FIREBALL_MIN_AREA        = 200        # px²    (recommended)

# Clock icon search radius around a button position
CLOCK_SEARCH_RADIUS      = 150        # px     (recommended)

# Arrow detection: merge hits within this distance into one cluster
ARROW_MERGE_DIST         = 80         # px     (recommended)

# Minimum arrow clusters before accepting a detection
ARROW_MIN_CLUSTERS       = 7          # count  (recommended — 7 arrows per round)

# Minimum template hits before attempting row detection
ARROW_MIN_HITS           = 3          # count  (recommended)
