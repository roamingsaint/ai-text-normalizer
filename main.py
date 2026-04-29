from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from clipboard_utils import (
    ClipboardSnapshot,
    ClipboardError,
    capture_selected_text,
    get_foreground_window,
    replace_selection_with_text,
    restore_text,
)
from config import (
    APP_NAME,
    CLIPBOARD_SETTLE_DELAY_SECONDS,
    COPY_TIMEOUT_SECONDS,
    DEFAULT_NORMALIZE_HOTKEY,
    DEFAULT_PREVIEW_HOTKEY,
    CLIPBOARD_POLL_INTERVAL_SECONDS,
    POST_PASTE_RESTORE_DELAY_SECONDS,
    INPUT_GUARD_TIMEOUT_SECONDS,
    ensure_rules_file,
    ensure_runtime_paths,
    get_log_file,
    get_resource_dir,
    get_rules_path,
    get_settings_path,
)
from hotkeys import HotkeyService
from normalizer import (
    NormalizationRules,
    infer_legacy_rules_version,
    load_rules,
    load_rules_payload,
    normalize_text,
    stamp_live_rules_payload,
    write_rules_payload,
)
from tray import TrayApp
from settings_store import AppSettings, load_settings, normalize_base_hotkey, save_settings, to_preview_hotkey
from settings_ui import RulesVersionStatus, SettingsDialog
from updater import UpdateCheckError, fetch_latest_release
from version import APP_VERSION

try:
    import winsound  # type: ignore
except Exception:  # pragma: no cover - Windows-only import
    winsound = None


@dataclass(frozen=True)
class RulesRuntimeStatus:
    headline: str
    detail: str = ""
    can_update: bool = False
    is_customized: bool = False


def _parse_version_parts(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in value.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            digits = "".join(ch for ch in part if ch.isdigit())
            if digits:
                parts.append(int(digits))
    return tuple(parts) if parts else (0,)


class AppController:
    def __init__(self, root: tk.Tk, rules: NormalizationRules, settings: AppSettings) -> None:
        self._root = root
        self._rules = rules
        self._settings = settings
        self._tray: TrayApp | None = None
        self._hotkeys: HotkeyService | None = None
        self._busy_lock = threading.Lock()
        self._settings_dialog_open = False
        self._active_settings_dialog: SettingsDialog | None = None
        self._shutdown_event = threading.Event()

    def set_tray(self, tray: TrayApp) -> None:
        self._tray = tray

    def set_hotkeys(self, hotkeys: HotkeyService) -> None:
        self._hotkeys = hotkeys

    def preview_enabled(self) -> bool:
        return self._settings.preview_default

    def toggle_preview(self) -> None:
        updated = AppSettings(
            normalize_hotkey=self._settings.normalize_hotkey,
            preview_hotkey=self._settings.preview_hotkey,
            preview_default=not self._settings.preview_default,
            play_sound_on_success=self._settings.play_sound_on_success,
        )
        self.apply_settings(updated, persist=True, notify=True)

    def normalize_now(self) -> None:
        self.request_normalize(preview=self._settings.preview_default, source="tray")

    def preview_now(self) -> None:
        self.request_normalize(preview=True, source="hotkey")

    def check_for_updates(self) -> None:
        thread = threading.Thread(target=self._check_for_updates_worker, daemon=True)
        thread.start()

    def open_settings(self) -> None:
        if self._settings_dialog_open:
            if self._active_settings_dialog is not None and self._tray is not None:
                self._tray.schedule_on_ui(self._active_settings_dialog.focus)
            return
        if self._tray is None:
            return

        def _on_save(new_settings: AppSettings) -> bool:
            return self.apply_settings(new_settings, persist=True, notify=True)

        def _on_close() -> None:
            self._settings_dialog_open = False
            self._active_settings_dialog = None

        def _open() -> None:
            try:
                rules_status = self._get_rules_runtime_status()
                self._settings_dialog_open = True
                self._active_settings_dialog = SettingsDialog(
                    self._root,
                    self._settings,
                    APP_VERSION,
                    _on_save,
                    self.check_for_updates,
                    self.open_rules,
                    self.open_default_rules,
                    self.open_rules_guide,
                    self.open_readme,
                    self.reset_rules_to_default,
                    self.open_update_download,
                    _on_close,
                )
                self._active_settings_dialog.set_rules_status(
                    RulesVersionStatus(
                        headline=rules_status.headline,
                        detail=rules_status.detail,
                        can_update=rules_status.can_update,
                        is_customized=rules_status.is_customized,
                    )
                )
                self._active_settings_dialog.set_update_checking()
                self.check_for_updates()
            except Exception:
                self._settings_dialog_open = False
                self._active_settings_dialog = None
                logging.exception("failed to open settings dialog")
                self._notify("Could not open settings.")

        self._tray.schedule_on_ui(_open)

    def _check_for_updates_worker(self) -> None:
        try:
            status = fetch_latest_release(APP_VERSION)
        except UpdateCheckError as exc:
            logging.exception("update check failed")

            def _show_error() -> None:
                if self._active_settings_dialog is not None:
                    self._active_settings_dialog.set_update_error(f"Update check failed: {exc}")

            if self._tray is not None:
                self._tray.schedule_on_ui(_show_error)
            return

        def _show_result() -> None:
            if self._active_settings_dialog is None:
                return
            if status.update_available:
                self._active_settings_dialog.set_update_available(status)
            else:
                self._active_settings_dialog.set_up_to_date(status.current_version)

        if self._tray is not None:
            self._tray.schedule_on_ui(_show_result)

    def open_update_download(self, url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception:
            logging.exception("failed to open update download url")
            self._notify("Could not open the update download page.")

    def request_normalize(self, *, preview: bool, source: str) -> None:
        if not self._busy_lock.acquire(blocking=False):
            self._notify("AI Text Normalizer is already processing a selection.")
            return
        if self._tray is not None:
            self._tray.show_processing()
        thread = threading.Thread(
            target=self._normalize_worker,
            kwargs={"preview": preview, "source": source},
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            self._busy_lock.release()
            raise

    def _normalize_worker(self, *, preview: bool, source: str) -> None:
        snapshot: ClipboardSnapshot | None = None
        target_window = get_foreground_window()
        guard_active = False
        try:
            logging.info("normalize requested from %s", source)
            self._rules = load_rules(get_rules_path())
            guard_active = self._activate_input_guard()
            captured = capture_selected_text(
                copy_timeout=COPY_TIMEOUT_SECONDS,
                poll_interval=CLIPBOARD_POLL_INTERVAL_SECONDS,
                settle_delay=CLIPBOARD_SETTLE_DELAY_SECONDS,
            )
            if captured is None:
                self._notify("No selectable text was captured.")
                return

            snapshot, original_text = captured
            normalized_text = normalize_text(original_text, self._rules)

            if normalized_text == original_text:
                self._notify("Text is already normalized.")
                return

            if preview:
                if guard_active:
                    self._release_input_guard()
                    guard_active = False
                replace = self._prompt_preview(original_text, normalized_text)
                if not replace:
                    restore_text(snapshot)
                    self._notify("Normalization cancelled.")
                    return
                if target_window and get_foreground_window() != target_window:
                    restore_text(snapshot)
                    self._notify("Target window changed. Paste cancelled.")
                    return
                guard_active = self._activate_input_guard()

            if target_window and get_foreground_window() != target_window:
                restore_text(snapshot)
                self._notify("Target window changed. Paste cancelled.")
                return

            replace_selection_with_text(
                normalized_text,
                snapshot,
                restore_delay=POST_PASTE_RESTORE_DELAY_SECONDS,
            )
            self._play_success_sound()
        except ClipboardError as exc:
            logging.exception("clipboard path failed")
            if snapshot is not None:
                restore_text(snapshot)
            self._notify(f"Clipboard/paste failed: {exc}")
        except Exception:
            logging.exception("normalization failed")
            if snapshot is not None:
                restore_text(snapshot)
            self._notify("Normalization failed. Check the log.")
        finally:
            if guard_active:
                self._release_input_guard()
            if self._tray is not None:
                self._tray.hide_processing()
            self._busy_lock.release()

    def _activate_input_guard(self) -> bool:
        if self._tray is None:
            return False
        return self._tray.activate_input_guard(INPUT_GUARD_TIMEOUT_SECONDS)

    def _release_input_guard(self) -> None:
        if self._tray is None:
            return
        self._tray.release_input_guard()

    def apply_settings(self, new_settings: AppSettings, *, persist: bool, notify: bool) -> bool:
        if self._hotkeys is not None:
            try:
                self._hotkeys.restart(
                    normalize_hotkey=normalize_base_hotkey(new_settings.normalize_hotkey),
                    preview_hotkey=to_preview_hotkey(new_settings.normalize_hotkey),
                )
            except Exception:
                logging.exception("failed to reconfigure hotkeys")
                self._notify("Invalid hotkey in settings.")
                return False
        self._settings = new_settings
        if persist:
            save_settings(get_settings_path(), new_settings)
        if notify:
            self._notify("Settings saved.")
        return True

    def _prompt_preview(self, original_text: str, normalized_text: str) -> bool:
        decision = threading.Event()
        result = {"replace": False}

        def on_replace() -> None:
            result["replace"] = True
            decision.set()

        def on_cancel() -> None:
            result["replace"] = False
            decision.set()

        if self._tray is None:
            return False

        self._tray.schedule_on_ui(
            lambda: self._tray.show_preview_dialog(original_text, normalized_text, on_replace, on_cancel)
        )

        decision.wait()
        return result["replace"]

    def open_default_rules(self) -> None:
        bundled_path = get_resource_dir() / "rules.json"
        if not bundled_path.exists():
            self._notify("Bundled default rules are missing.")
            return

        def _open() -> None:
            try:
                view_path = Path(tempfile.gettempdir()) / "ai-text-normalizer-default-rules.json"
                shutil.copyfile(bundled_path, view_path)
                try:
                    os.startfile(str(view_path))
                except Exception:
                    subprocess.Popen(["notepad.exe", str(view_path)])
            except Exception:
                logging.exception("failed to open bundled default rules")
                self._notify("Could not open bundled default rules.")

        if self._tray is not None:
            self._tray.schedule_on_ui(_open)

    def reset_rules_to_default(self) -> None:
        try:
            bundled_path = get_resource_dir() / "rules.json"
            runtime_path = ensure_rules_file()
            if not bundled_path.exists():
                self._notify("Bundled default rules are missing.")
                return
            bundled_payload = load_rules_payload(bundled_path)
            write_rules_payload(runtime_path, stamp_live_rules_payload(bundled_payload))
            self._rules = load_rules(runtime_path)
            if self._active_settings_dialog is not None:
                rules_status = self._get_rules_runtime_status()
                self._active_settings_dialog.set_rules_status(
                    RulesVersionStatus(
                        headline=rules_status.headline,
                        detail=rules_status.detail,
                        can_update=rules_status.can_update,
                        is_customized=rules_status.is_customized,
                    )
                )
            self._notify("Live rules reset to bundled defaults.")
        except Exception:
            logging.exception("failed to reset rules file")
            self._notify("Could not reset rules to defaults.")

    def _open_local_file(self, path: Path, *, error_message: str) -> None:
        if self._tray is None:
            return

        def _open() -> None:
            try:
                if not path.exists():
                    self._notify(error_message)
                    return
                try:
                    os.startfile(str(path))
                except Exception:
                    subprocess.Popen(["notepad.exe", str(path)])
            except Exception:
                logging.exception("failed to open local file: %s", path)
                self._notify(error_message)

        self._tray.schedule_on_ui(_open)

    def _get_rules_runtime_status(self) -> RulesRuntimeStatus:
        bundled_path = get_resource_dir() / "rules.json"
        live_path = get_rules_path()
        try:
            bundled_rules = load_rules(bundled_path)
        except Exception:
            logging.exception("failed to load bundled default rules")
            return RulesRuntimeStatus("Bundled defaults could not be read.")
        try:
            live_rules = load_rules(live_path)
        except Exception:
            logging.exception("failed to load live rules")
            return RulesRuntimeStatus("Live rules could not be read.")

        bundled_version = bundled_rules.rules_version or "unknown"
        live_version = (
            live_rules.based_on_rules_version
            or live_rules.rules_version
            or infer_legacy_rules_version(live_rules)
            or "unknown"
        )

        if live_rules.current_rules_digest == bundled_rules.current_rules_digest:
            detail = f"Live rules match bundled defaults v{bundled_version}."
            if live_rules.base_rules_digest and live_rules.is_customized():
                detail = f"Live rules are customized and already based on v{bundled_version}."
            return RulesRuntimeStatus(
                headline=f"Up to date (v{bundled_version})",
                detail=detail,
                is_customized=bool(live_rules.base_rules_digest and live_rules.is_customized()),
            )

        live_is_customized = live_rules.is_customized()
        if not live_rules.base_rules_digest and infer_legacy_rules_version(live_rules):
            live_is_customized = False

        if _parse_version_parts(live_version) < _parse_version_parts(bundled_version):
            if live_is_customized:
                return RulesRuntimeStatus(
                    headline=f"New defaults available (v{bundled_version})",
                    detail=(
                        f"Your live rules are customized and still based on v{live_version}. "
                        "Review the new defaults if you want to copy any changes."
                    ),
                    is_customized=True,
                )
            return RulesRuntimeStatus(
                headline=f"Update available ({live_version} -> {bundled_version})",
                detail="Your live rules still match an older default set.",
                can_update=True,
            )

        if live_is_customized:
            return RulesRuntimeStatus(
                headline=f"Customized (based on v{live_version})",
                detail="Your live rules differ from the bundled defaults and were kept unchanged.",
                is_customized=True,
            )

        return RulesRuntimeStatus(
            headline=f"Review recommended (bundled v{bundled_version})",
            detail=(
                "This live rules file predates rules version tracking or differs from the bundled defaults. "
                "Review it before resetting to new defaults."
            ),
            is_customized=True,
        )

    def open_rules(self) -> None:
        try:
            rules_path = ensure_rules_file()
            rules_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            logging.exception("failed to prepare rules file")
            self._notify("Could not open rules.json.")
            return
        self._open_local_file(rules_path, error_message="Could not open rules.json.")

    def open_readme(self) -> None:
        self._open_local_file(get_resource_dir() / "README.md", error_message="Could not open README.md.")

    def open_rules_guide(self) -> None:
        self._open_local_file(get_resource_dir() / "RULES.md", error_message="Could not open RULES.md.")

    def shutdown(self) -> None:
        self._shutdown_event.set()
        if self._hotkeys is not None:
            self._hotkeys.stop()
        if self._tray is not None:
            self._tray.stop()
        self._root.after(0, self._root.quit)

    def _notify(self, message: str) -> None:
        if self._tray is not None:
            self._tray.notify(message, title=APP_NAME)

    def _play_success_sound(self) -> None:
        if not self._settings.play_sound_on_success:
            return
        if winsound is None:
            return
        try:
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            logging.exception("failed to play notification sound")


def _setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    ensure_runtime_paths()
    ensure_rules_file()
    _setup_logging(get_log_file())

    root = tk.Tk()
    root.withdraw()
    root.title(APP_NAME)

    rules = load_rules(get_rules_path())
    default_settings = AppSettings.default(DEFAULT_NORMALIZE_HOTKEY, DEFAULT_PREVIEW_HOTKEY)
    settings = load_settings(get_settings_path(), default_settings)
    controller = AppController(root, rules, settings)

    tray = TrayApp(
        root,
        on_normalize_now=controller.normalize_now,
        on_toggle_preview=controller.toggle_preview,
        on_open_settings=controller.open_settings,
        on_exit=controller.shutdown,
        preview_state_getter=controller.preview_enabled,
    )
    controller.set_tray(tray)

    hotkeys = HotkeyService(
        normalize_hotkey=normalize_base_hotkey(settings.normalize_hotkey),
        preview_hotkey=to_preview_hotkey(settings.normalize_hotkey),
        on_normalize=controller.normalize_now,
        on_preview=controller.preview_now,
    )
    controller.set_hotkeys(hotkeys)

    hotkeys.start()
    tray.start()

    def _pump_ui() -> None:
        tray.process_pending_ui()
        root.after(50, _pump_ui)

    def _on_close() -> None:
        controller.shutdown()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.after(50, _pump_ui)
    logging.info("%s started", APP_NAME)
    root.mainloop()


if __name__ == "__main__":
    main()











