from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    normalize_hotkey: str
    preview_hotkey: str
    preview_default: bool
    play_sound_on_success: bool

    @classmethod
    def default(cls, normalize_hotkey: str, preview_hotkey: str) -> "AppSettings":
        return cls(
            normalize_hotkey=normalize_hotkey,
            preview_hotkey=preview_hotkey,
            preview_default=False,
            play_sound_on_success=False,
        )


def _to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def load_settings(path: Path, default: AppSettings) -> AppSettings:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default

    if not isinstance(payload, dict):
        return default

    normalize_hotkey = payload.get("normalize_hotkey", default.normalize_hotkey)
    preview_hotkey = payload.get("preview_hotkey", default.preview_hotkey)
    preview_default = _to_bool(payload.get("preview_default"), default.preview_default)
    play_sound_on_success = _to_bool(
        payload.get("play_sound_on_success"),
        default.play_sound_on_success,
    )

    if not isinstance(normalize_hotkey, str):
        normalize_hotkey = default.normalize_hotkey
    if not isinstance(preview_hotkey, str):
        preview_hotkey = default.preview_hotkey

    return AppSettings(
        normalize_hotkey=normalize_hotkey,
        preview_hotkey=preview_hotkey,
        preview_default=preview_default,
        play_sound_on_success=play_sound_on_success,
    )


def save_settings(path: Path, settings: AppSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "normalize_hotkey": settings.normalize_hotkey,
        "preview_hotkey": settings.preview_hotkey,
        "preview_default": settings.preview_default,
        "play_sound_on_success": settings.play_sound_on_success,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
