# Meadow MMO Auto Bot

An automation bot for the Meadow MMO Discord game. It plays the three mini-games for you on repeat so you can sit back and touch grass.

## What It Does

The bot watches your screen and plays the games in priority order:

1. **Craft** — Detects the arrow key sequence and presses them automatically (3 rounds per game)
2. **Battle** — Moves your platform to intercept falling green fireballs in real time
3. **Adventure** — Rapid-clicks the adventure button while waiting for craft/battle to come off cooldown

It also handles:
- Cooldown tracking for craft and battle (auto-switches to adventure while waiting)
- Out-of-resources popups (auto-dismisses them)
- Navigation recovery (clicks the back arrow if it gets lost on the wrong screen)
- Live status overlay injected into Discord showing current activity
- Press **F6** to stop the bot

## How It Works

The bot connects to Discord via the **Chrome DevTools Protocol (CDP)**. This means:
- No real mouse movement — your cursor stays free
- No window focus needed — Discord can be behind other windows
- Works across virtual desktops
- Screenshots and input go directly through Chromium's internals

## Requirements

- Python 3.10+
- Windows 10/11
- Discord desktop app (not browser)

## Install

```bash
pip install opencv-python numpy websocket-client requests pynput colorama
```

## Setup

Discord needs to be launched with CDP enabled. You only need to do this once — edit your Discord shortcut:

1. Right-click your Discord shortcut → **Properties**
2. In the **Target** field, add these flags at the end:
   ```
   --remote-debugging-port=9222 --remote-allow-origins=*
   ```
   So it looks like:
   ```
   "C:\Users\YOU\AppData\Local\Discord\app-1.0.xxxx\Discord.exe" --remote-debugging-port=9222 --remote-allow-origins=*
   ```
3. Click OK and launch Discord from that shortcut

Or launch from PowerShell:
```powershell
& "$env:LOCALAPPDATA\Discord\app-1.0.9230\Discord.exe" --remote-debugging-port=9222 --remote-allow-origins=*
```

> **Note:** Replace the version number (`1.0.9230`) with whatever version you have installed.

## Usage

1. Launch Discord with CDP flags (see Setup above)
2. Navigate to the Meadow MMO game so the buttons are visible
3. Run the bot:

```bash
python bot.py
```

4. The bot will connect to Discord automatically — no need to switch windows
5. Press **F6** to stop at any time

## Important Notes

- **Don't make the Discord window too small.** The bot uses template matching to detect buttons and game elements. If the window is too small, the templates can't match and the bot won't detect anything. Keep Discord at a medium or larger size.
- **Don't minimize Discord.** CDP screenshots work when Discord is behind other windows or on another virtual desktop, but not when minimized.
- **Option 3 is recommended:** Keep Discord open on the same desktop behind your other windows. This usually works.***
- **Virtual desktops work.** Since the bot communicates with Discord through CDP (Chrome DevTools Protocol), you can put both Discord and the bot on a separate virtual desktop and switch away. CDP connects directly to Chromium's internals — it doesn't care about window visibility or focus.

## Config

All timings, thresholds, and detection settings can be tweaked in `config.py`. The defaults are already tuned and recommended — only change them if something isn't working for your setup.

## Project Structure

```
bot.py          Main bot logic and state machine
vision.py       Screen capture via CDP screenshots + template matching
controller.py   Mouse and keyboard input via CDP/JavaScript
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
