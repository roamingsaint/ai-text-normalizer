from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional


LOGGER = logging.getLogger(__name__)


@dataclass
class RegisteredHotkey:
    hotkey: str
    handle: object


class KeyboardHotkeyBackend:
    def __init__(self) -> None:
        try:
            import keyboard  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("The 'keyboard' package is required on Windows.") from exc
        self._keyboard = keyboard
        self._registrations: list[RegisteredHotkey] = []

    def register(self, hotkey: str, callback: Callable[[], None]) -> None:
        handle = self._keyboard.add_hotkey(hotkey, callback, suppress=True, trigger_on_release=False)
        self._registrations.append(RegisteredHotkey(hotkey=hotkey, handle=handle))
        LOGGER.info("registered hotkey: %s", hotkey)

    def unregister_all(self) -> None:
        for registration in self._registrations:
            try:
                self._keyboard.remove_hotkey(registration.handle)
            except Exception:
                LOGGER.exception("failed to unregister hotkey: %s", registration.hotkey)
        self._registrations.clear()


class HotkeyService:
    def __init__(
        self,
        *,
        normalize_hotkey: str,
        preview_hotkey: str,
        on_normalize: Callable[[], None],
        on_preview: Callable[[], None],
    ) -> None:
        self._backend = KeyboardHotkeyBackend()
        self._normalize_hotkey = normalize_hotkey
        self._preview_hotkey = preview_hotkey
        self._on_normalize = on_normalize
        self._on_preview = on_preview
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._backend.register(self._normalize_hotkey, self._on_normalize)
        self._backend.register(self._preview_hotkey, self._on_preview)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._backend.unregister_all()
        self._started = False

    def restart(self, *, normalize_hotkey: str, preview_hotkey: str) -> None:
        if not self._started:
            self._normalize_hotkey = normalize_hotkey
            self._preview_hotkey = preview_hotkey
            return

        new_backend = KeyboardHotkeyBackend()
        try:
            new_backend.register(normalize_hotkey, self._on_normalize)
            new_backend.register(preview_hotkey, self._on_preview)
        except Exception:
            try:
                new_backend.unregister_all()
            except Exception:
                LOGGER.exception("failed to clean up temporary hotkeys")
            raise

        old_backend = self._backend
        self._backend = new_backend
        self._normalize_hotkey = normalize_hotkey
        self._preview_hotkey = preview_hotkey
        try:
            old_backend.unregister_all()
        except Exception:
            LOGGER.exception("failed to remove old hotkeys after reconfigure")
