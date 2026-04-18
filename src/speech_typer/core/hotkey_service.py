from __future__ import annotations

import threading
from typing import Callable

from pynput import keyboard


class GlobalHotkeyService:
    def __init__(self, hotkey: str, on_state_change: Callable[[bool], None]) -> None:
        self.hotkey = hotkey
        self.on_state_change = on_state_change
        self.listener: keyboard.Listener | None = None
        self.lock = threading.Lock()
        self.required_tokens = self._parse_hotkey(hotkey)
        self.pressed_tokens: set[str] = set()
        self.active = False

    def start(self) -> None:
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None

    def update_hotkey(self, hotkey: str) -> None:
        with self.lock:
            self.hotkey = hotkey
            self.required_tokens = self._parse_hotkey(hotkey)
            self.pressed_tokens.clear()
            self.active = False

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        token = self._normalize_key(key)
        if not token:
            return
        with self.lock:
            self.pressed_tokens.add(token)
            should_activate = self.required_tokens.issubset(self.pressed_tokens)
            if should_activate and not self.active:
                self.active = True
                self.on_state_change(True)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        token = self._normalize_key(key)
        if not token:
            return
        with self.lock:
            self.pressed_tokens.discard(token)
            still_active = self.required_tokens.issubset(self.pressed_tokens)
            if self.active and not still_active:
                self.active = False
                self.on_state_change(False)

    def _parse_hotkey(self, hotkey: str) -> set[str]:
        tokens = {part.strip().lower() for part in hotkey.split("+") if part.strip()}
        aliases = {
            "control": "ctrl",
            "return": "enter",
            "escape": "esc",
            "option": "alt",
        }
        return {aliases.get(token, token) for token in tokens} or {"alt"}

    def _normalize_key(self, key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(key, keyboard.KeyCode):
            if key.char:
                return key.char.lower()
            return None

        mapping = {
            keyboard.Key.alt: "alt",
            keyboard.Key.alt_l: "alt",
            keyboard.Key.alt_r: "alt",
            keyboard.Key.ctrl: "ctrl",
            keyboard.Key.ctrl_l: "ctrl",
            keyboard.Key.ctrl_r: "ctrl",
            keyboard.Key.shift: "shift",
            keyboard.Key.shift_l: "shift",
            keyboard.Key.shift_r: "shift",
            keyboard.Key.space: "space",
            keyboard.Key.enter: "enter",
            keyboard.Key.esc: "esc",
            keyboard.Key.cmd: "win",
            keyboard.Key.cmd_l: "win",
            keyboard.Key.cmd_r: "win",
        }
        return mapping.get(key)
