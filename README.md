# Meadow MMO Auto Bot

An automation bot for the Meadow MMO Discord game. It plays the three mini-games for you on repeat so you can sit back and collect rewards.

## What It Does

The bot watches your screen and plays the games in priority order:

1. **Craft** — Detects the arrow key sequence and presses them automatically (3 rounds per game)
2. **Battle** — Moves your platform to intercept falling green fireballs in real time
3. **Adventure** — Rapid-clicks the adventure button while waiting for craft/battle to come off cooldown

It also handles:
- Cooldown tracking for craft and battle (auto-switches to adventure while waiting)
- Out-of-resources popups (auto-dismisses them)
- Navigation recovery (clicks the back arrow if it gets lost on the wrong screen)
- Press **F** at any time to stop the bot

## Requirements

- Python 3.10+
- Windows 10/11
- Discord desktop app (not browser)

## Install

```bash
pip install opencv-python numpy mss pywin32 pynput colorama
```

## Usage

1. Open Discord and navigate to the Meadow MMO game
2. Make sure the craft, battle, and adventure buttons are visible on screen
3. Run the bot:

```bash
python bot.py
```

4. You have 3 seconds to switch back to the Discord window
5. Press **F** to stop at any time

## Config

All timings, thresholds, and detection settings can be tweaked in `config.py`. The defaults are already tuned and recommended — only change them if something isn't working for your setup.

## Project Structure

```
bot.py          Main bot logic and state machine
vision.py       Screen capture and template matching
controller.py   Mouse and keyboard input
config.py       All adjustable settings
logger.py       Colored terminal output

assets/
  adv/          Adventure button templates
  battle/       Battle button, platform, success screen
  craft/        Craft button, arrows, stars, success screen
  ui/           Shared UI (clock, continue, back arrow, popups)
```

---

*The reason you will be touching grass today.*
