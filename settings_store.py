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
        normalize = normalize_base_hotkey(normalize_hotkey)
        if not normalize:
            normalize = "ctrl+shift+q"
        return cls(
            normalize_hotkey=normalize,
            preview_hotkey=to_preview_hotkey(normalize),
            preview_default=False,
            play_sound_on_success=False,
        )


def _to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def normalize_base_hotkey(value: str) -> str:
    parts = [part.strip().lower() for part in value.split("+") if part and part.strip()]
    if not parts:
        return ""
    mods = {part for part in parts if part in {"ctrl", "shift", "alt"}}
    key = next((part for part in reversed(parts) if part not in {"ctrl", "shift", "alt"}), "")
    ordered: list[str] = []
    if "ctrl" in mods:
        ordered.append("ctrl")
    if "shift" in mods:
        ordered.append("shift")
    if key:
        ordered.append(key)
    return "+".join(ordered)


def to_preview_hotkey(normalize_hotkey: str) -> str:
    base = normalize_base_hotkey(normalize_hotkey)
    if not base:
        return "alt"
    parts = base.split("+")
    mods = {part for part in parts if part in {"ctrl", "shift"}}
    key = parts[-1] if parts else ""
    ordered: list[str] = []
    if "ctrl" in mods:
        ordered.append("ctrl")
    ordered.append("alt")
    if "shift" in mods:
        ordered.append("shift")
    if key and key not in {"ctrl", "shift"}:
        ordered.append(key)
    return "+".join(ordered)


def load_settings(path: Path, default: AppSettings) -> AppSettings:
    default_normalize = normalize_base_hotkey(default.normalize_hotkey) or "ctrl+shift+q"

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AppSettings(
            normalize_hotkey=default_normalize,
            preview_hotkey=to_preview_hotkey(default_normalize),
            preview_default=default.preview_default,
            play_sound_on_success=default.play_sound_on_success,
        )
    except json.JSONDecodeError:
        return AppSettings(
            normalize_hotkey=default_normalize,
            preview_hotkey=to_preview_hotkey(default_normalize),
            preview_default=default.preview_default,
            play_sound_on_success=default.play_sound_on_success,
        )

    if not isinstance(payload, dict):
        return AppSettings(
            normalize_hotkey=default_normalize,
            preview_hotkey=to_preview_hotkey(default_normalize),
            preview_default=default.preview_default,
            play_sound_on_success=default.play_sound_on_success,
        )

    normalize_hotkey = payload.get("normalize_hotkey", default_normalize)
    preview_default = _to_bool(payload.get("preview_default"), default.preview_default)
    play_sound_on_success = _to_bool(
        payload.get("play_sound_on_success"),
        default.play_sound_on_success,
    )

    if not isinstance(normalize_hotkey, str):
        normalize_hotkey = default_normalize

    normalize_hotkey = normalize_base_hotkey(normalize_hotkey) or default_normalize

    return AppSettings(
        normalize_hotkey=normalize_hotkey,
        preview_hotkey=to_preview_hotkey(normalize_hotkey),
        preview_default=preview_default,
        play_sound_on_success=play_sound_on_success,
    )


def save_settings(path: Path, settings: AppSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalize = normalize_base_hotkey(settings.normalize_hotkey)
    payload = {
        "normalize_hotkey": normalize,
        "preview_hotkey": to_preview_hotkey(normalize),
        "preview_default": settings.preview_default,
        "play_sound_on_success": settings.play_sound_on_success,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
