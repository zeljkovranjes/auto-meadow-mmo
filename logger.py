"""
Logging Module
==============
Centralized, color-coded logging with timestamps.
"""

from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

# ── Theme ────────────────────────────────────────────────────────────────────

_COLORS = {
    'system':    Fore.CYAN,
    'success':   Fore.GREEN,
    'action':    Fore.YELLOW,
    'warn':      Fore.MAGENTA,
    'error':     Fore.RED,
    'info':      Fore.WHITE,
    'dim':       Style.DIM + Fore.WHITE,
}

_ICONS = {
    'system':    '*',
    'success':   '+',
    'action':    '>',
    'warn':      '!',
    'error':     'x',
    'info':      '|',
}

_BRIGHT = Style.BRIGHT
_RESET  = Style.RESET_ALL


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _log(level: str, tag: str, msg: str):
    color = _COLORS.get(level, Fore.WHITE)
    icon  = _ICONS.get(level, ' ')
    ts    = f"{Style.DIM}{Fore.WHITE}{_ts()}{_RESET}"
    label = f"{color}{_BRIGHT}[{tag}]{_RESET}"
    print(f"  {ts}  {color}{icon}{_RESET} {label} {color}{msg}{_RESET}")


# ── Public API ───────────────────────────────────────────────────────────────

def banner():
    b = f"""{Fore.CYAN}{_BRIGHT}
    +==========================================+
    |         MEADOW MMO  -  AUTO BOT         |
    |------------------------------------------|
    |  Craft  >  Battle  >  Adventure         |
    |  Press F6 to stop                        |
    +==========================================+{_RESET}"""
    print(b)


def system(msg: str):
    _log('system', 'SYS', msg)

def success(msg: str):
    _log('success', 'OK', msg)

def action(tag: str, msg: str):
    _log('action', tag, msg)

def warn(msg: str):
    _log('warn', 'WARN', msg)

def error(msg: str):
    _log('error', 'ERR', msg)

def info(tag: str, msg: str):
    _log('info', tag, msg)

def state_change(from_state: str, to_state: str):
    _log('action', 'STATE', f"{from_state} → {to_state}")

def obstacle(msg: str):
    _log('warn', 'OBSTACLE', msg)

def cooldown(game: str):
    _log('dim', 'CD', f"{game} on cooldown — skipping")

def separator():
    print(f"  {Style.DIM}{Fore.CYAN}{'-' * 50}{_RESET}")
