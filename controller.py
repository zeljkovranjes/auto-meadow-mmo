"""
Game Controller — CDP (Chrome DevTools Protocol)
=================================================
Uses JavaScript DOM clicks and CDP keyboard input.
No real cursor movement. Works fully in background.
Requires Discord launched with: --remote-debugging-port=9222 --remote-allow-origins=*
"""

import json
import time
import requests
import websocket
import logger as log

_CDP_PORT = 9222

_KEY_MAP = {
    'up':    {'key': 'ArrowUp',    'code': 'ArrowUp',    'vk': 38},
    'down':  {'key': 'ArrowDown',  'code': 'ArrowDown',  'vk': 40},
    'left':  {'key': 'ArrowLeft',  'code': 'ArrowLeft',  'vk': 37},
    'right': {'key': 'ArrowRight', 'code': 'ArrowRight', 'vk': 39},
    'esc':   {'key': 'Escape',     'code': 'Escape',     'vk': 27},
}


class GameController:
    def __init__(self):
        self.ws = None
        self._msg_id = 0
        self._connect()

    def _connect(self):
        """Connect to Discord's CDP websocket."""
        try:
            r = requests.get(f'http://localhost:{_CDP_PORT}/json', timeout=5)
            pages = r.json()
            page = next(p for p in pages if p.get('type') == 'page')
            self._cdp_ws_url = page['webSocketDebuggerUrl']
            self.ws = websocket.create_connection(self._cdp_ws_url)
            log.success(f"CDP connected to: {page.get('title', 'Discord')}")
        except Exception as e:
            log.error(f"CDP connection failed: {e}")
            log.warn("Launch Discord with: --remote-debugging-port=9222 --remote-allow-origins=*")
            self.ws = None

    def _send(self, method: str, params: dict = None):
        if not self.ws:
            self._connect()
        if not self.ws:
            return None
        self._msg_id += 1
        msg_id = self._msg_id
        msg = {'id': msg_id, 'method': method, 'params': params or {}}
        try:
            self.ws.settimeout(5)
            self.ws.send(json.dumps(msg))
            # Loop until we get OUR response (skip async CDP events)
            for _ in range(50):
                data = json.loads(self.ws.recv())
                if data.get('id') == msg_id:
                    return data
                # else it's an event — discard and keep reading
            return None
        except Exception:
            log.warn("CDP controller connection lost -- reconnecting")
            self.ws = None
            self._connect()
            return None

    def _js(self, expression: str):
        """Execute JavaScript in Discord's page context."""
        return self._send('Runtime.evaluate', {'expression': expression})

    def click(self, x: int, y: int):
        """Click via JS elementFromPoint — works even without focus."""
        self._js(f'''
            (function() {{
                var el = document.elementFromPoint({int(x)}, {int(y)});
                if (el) {{
                    el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true, clientX: {int(x)}, clientY: {int(y)}}}));
                    el.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, button: 0, clientX: {int(x)}, clientY: {int(y)}}}));
                    el.dispatchEvent(new MouseEvent('mouseup',   {{bubbles: true, button: 0, clientX: {int(x)}, clientY: {int(y)}}}));
                    el.dispatchEvent(new MouseEvent('click',     {{bubbles: true, button: 0, clientX: {int(x)}, clientY: {int(y)}}}));
                }}
            }})()
        ''')

    def move(self, x: int, y: int):
        """Move via JS mousemove event — for battle tracking."""
        self._js(f'''
            (function() {{
                var el = document.elementFromPoint({int(x)}, {int(y)});
                if (el) {{
                    el.dispatchEvent(new MouseEvent('mousemove', {{bubbles: true, clientX: {int(x)}, clientY: {int(y)}}}));
                }}
            }})()
        ''')

    def press_key(self, key_name: str):
        """Key press via CDP Input.dispatchKeyEvent."""
        info = _KEY_MAP.get(key_name)
        if not info:
            return
        self._send('Input.dispatchKeyEvent', {
            'type': 'keyDown',
            'key': info['key'],
            'code': info['code'],
            'windowsVirtualKeyCode': info['vk'],
        })
        time.sleep(0.01)
        self._send('Input.dispatchKeyEvent', {
            'type': 'keyUp',
            'key': info['key'],
            'code': info['code'],
            'windowsVirtualKeyCode': info['vk'],
        })

    def grab_focus(self):
        pass

    def release_focus(self):
        pass

    # ── Status overlay ───────────────────────────────────────────────────

    def inject_overlay(self):
        """Create a status overlay in Discord's DOM."""
        self._js('''
            (function() {
                if (document.getElementById('bot-overlay')) return;
                var d = document.createElement('div');
                d.id = 'bot-overlay';
                d.style.cssText = 'position:fixed;top:10px;left:10px;z-index:99999;'
                    + 'background:rgba(0,0,0,0.75);color:#00ff88;padding:8px 14px;'
                    + 'border-radius:6px;font-family:monospace;font-size:12px;'
                    + 'pointer-events:none;border:1px solid #00ff8844;'
                    + 'text-shadow:0 0 4px #00ff8866;';
                d.innerHTML = '<span style="color:#00ff88">BOT</span> <span id="bot-status" style="color:#aaa">starting...</span>';
                document.body.appendChild(d);
            })()
        ''')

    def update_status(self, state: str, detail: str = ''):
        """Update the overlay text."""
        colors = {
            'IDLE': '#888888',
            'ADVENTURE': '#ffaa00',
            'CRAFT': '#00aaff',
            'BATTLE': '#ff4444',
            'OBSTACLE': '#ff00ff',
        }
        color = colors.get(state, '#00ff88')
        text = f'{state}' + (f' - {detail}' if detail else '')
        # Escape quotes for JS
        text = text.replace("'", "\\'")
        self._js(f'''
            (function() {{
                var el = document.getElementById('bot-status');
                if (el) {{
                    el.style.color = '{color}';
                    el.textContent = '{text}';
                }}
            }})()
        ''')
