from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "AI Text Normalizer"
GITHUB_REPO = "roamingsaint/ai-text-normalizer"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DEFAULT_NORMALIZE_HOTKEY = "ctrl+shift+q"
DEFAULT_PREVIEW_HOTKEY = "ctrl+shift+n"

COPY_TIMEOUT_SECONDS = 0.75
CLIPBOARD_POLL_INTERVAL_SECONDS = 0.02
CLIPBOARD_SETTLE_DELAY_SECONDS = 0.04
POST_PASTE_RESTORE_DELAY_SECONDS = 0.12
INPUT_GUARD_TIMEOUT_SECONDS = 1.25

PREVIEW_WINDOW_GEOMETRY = "980x560"
PREVIEW_MIN_SIZE = (760, 420)


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_runtime_dir() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_resource_dir() -> Path:
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", get_runtime_dir()))
    return get_runtime_dir()


def get_rules_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME / "rules.json"
    return Path.home() / f".{APP_NAME.lower()}" / "rules.json"


def get_rules_dir() -> Path:
    return get_rules_path().parent


def get_log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME / "logs"
    return Path.home() / f".{APP_NAME.lower()}" / "logs"


def get_log_file() -> Path:
    return get_log_dir() / "ai-text-normalizer.log"


def get_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME / "settings.json"
    return Path.home() / f".{APP_NAME.lower()}" / "settings.json"


def ensure_runtime_paths() -> None:
    get_log_dir().mkdir(parents=True, exist_ok=True)
    get_settings_path().parent.mkdir(parents=True, exist_ok=True)


def ensure_rules_file() -> Path:
    from normalizer import load_rules_payload, stamp_live_rules_payload, write_rules_payload

    runtime_rules = get_rules_path()
    bundled_rules = get_resource_dir() / "rules.json"
    if runtime_rules.exists():
        if bundled_rules.exists():
            try:
                runtime_payload = load_rules_payload(runtime_rules)
                bundled_payload = load_rules_payload(bundled_rules)
                if (
                    not runtime_payload.get("base_rules_digest")
                    and runtime_payload.get("rules_version") == bundled_payload.get("rules_version")
                ):
                    write_rules_payload(runtime_rules, stamp_live_rules_payload(runtime_payload))
            except Exception:
                pass
        return runtime_rules

    if bundled_rules.exists():
        runtime_payload = load_rules_payload(bundled_rules)
        write_rules_payload(runtime_rules, stamp_live_rules_payload(runtime_payload))
    return runtime_rules


