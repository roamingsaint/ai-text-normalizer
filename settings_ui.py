from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable

from config import APP_NAME
from settings_store import AppSettings, normalize_base_hotkey, to_preview_hotkey
from updater import UpdateStatus

SHIFT_MASK = 0x0001
CONTROL_MASK = 0x0004
MODIFIER_KEYSYMS = {
    "Shift_L",
    "Shift_R",
    "Control_L",
    "Control_R",
    "Alt_L",
    "Alt_R",
    "Meta_L",
    "Meta_R",
}
KEY_ALIASES = {
    "space": "space",
    "minus": "-",
    "equal": "=",
    "comma": ",",
    "period": ".",
    "slash": "/",
    "backslash": "\\",
    "semicolon": ";",
    "apostrophe": "'",
    "bracketleft": "[",
    "bracketright": "]",
    "grave": "`",
    "Return": "enter",
    "Escape": "esc",
    "BackSpace": "backspace",
    "Delete": "delete",
    "Insert": "insert",
    "Home": "home",
    "End": "end",
    "Prior": "page up",
    "Next": "page down",
    "Tab": "tab",
}


class HotkeyCapture(ttk.Entry):
    def __init__(self, parent: ttk.Frame, *, initial_value: str, on_changed: Callable[[str], None]) -> None:
        self._value = tk.StringVar(value=initial_value)
        self._on_changed = on_changed
        super().__init__(parent, textvariable=self._value, width=28)
        self.bind("<KeyPress>", self._on_keypress)
        self.bind("<Button-1>", self._focus_self)
        self.configure(exportselection=False)

    def get_value(self) -> str:
        return self._value.get().strip()

    def _focus_self(self, event: tk.Event) -> str:
        self.focus_set()
        return "break"

    def _on_keypress(self, event: tk.Event) -> str:
        modifiers = self._get_modifiers(event)
        key = self._normalize_key(event.keysym)

        if event.keysym in MODIFIER_KEYSYMS:
            return "break"
        if key is None or key in modifiers:
            return "break"

        hotkey = "+".join([*modifiers, key]) if modifiers else key
        base = normalize_base_hotkey(hotkey)
        if base:
            self._value.set(base)
            self._on_changed(base)
        self.icursor("end")
        return "break"

    @staticmethod
    def _get_modifiers(event: tk.Event) -> list[str]:
        modifiers: list[str] = []
        if event.state & CONTROL_MASK or event.keysym in {"Control_L", "Control_R"}:
            modifiers.append("ctrl")
        if event.state & SHIFT_MASK or event.keysym in {"Shift_L", "Shift_R"}:
            modifiers.append("shift")
        return modifiers

    @staticmethod
    def _normalize_key(keysym: str) -> str | None:
        if keysym in MODIFIER_KEYSYMS:
            return None
        if len(keysym) == 1:
            return keysym.lower()
        if keysym in KEY_ALIASES:
            return KEY_ALIASES[keysym]
        lower = keysym.lower()
        if lower.startswith("f") and lower[1:].isdigit():
            return lower
        if lower in {"left", "right", "up", "down", "tab"}:
            return lower
        return None


def _has_non_modifier_key(value: str) -> bool:
    parts = [part.strip().lower() for part in value.split("+") if part.strip()]
    return any(part not in {"ctrl", "shift", "alt"} for part in parts)


def _has_minimum_combo(value: str, minimum_parts: int = 3) -> bool:
    parts = [part for part in normalize_base_hotkey(value).split("+") if part]
    return len(parts) >= minimum_parts


@dataclass(frozen=True)
class RulesVersionStatus:
    headline: str
    detail: str = ""
    can_update: bool = False
    is_customized: bool = False


class SettingsDialog:
    def __init__(
        self,
        root: tk.Tk,
        settings: AppSettings,
        current_version: str,
        on_save: Callable[[AppSettings], bool],
        on_check_updates: Callable[[], None],
        on_open_rules: Callable[[], None],
        on_open_default_rules: Callable[[], None],
        on_open_rules_guide: Callable[[], None],
        on_open_readme: Callable[[], None],
        on_reset_rules: Callable[[], None],
        on_open_update_download: Callable[[str], None],
        on_close: Callable[[], None],
    ) -> None:
        self._root = root
        self._on_save = on_save
        self._on_check_updates = on_check_updates
        self._on_open_rules = on_open_rules
        self._on_open_default_rules = on_open_default_rules
        self._on_open_rules_guide = on_open_rules_guide
        self._on_open_readme = on_open_readme
        self._on_reset_rules = on_reset_rules
        self._on_open_update_download = on_open_update_download
        self._on_close = on_close
        self._update_download_url: str | None = None

        normalize_base = normalize_base_hotkey(settings.normalize_hotkey)

        self._window = tk.Toplevel(root)
        self._window.withdraw()
        self._window.title(f"{APP_NAME} Settings")
        self._window.resizable(False, False)
        self._window.attributes("-topmost", True)
        self._window.protocol("WM_DELETE_WINDOW", self.cancel)

        container = ttk.Frame(self._window, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text=f"Version v{current_version}").pack(anchor="w")

        guidance = ttk.Label(
            container,
            text=(
                "Set only Normalize hotkey. Preview hotkey is generated automatically as Alt + Normalize.\n"
                "Alt in Normalize input is ignored. Include at least 3 keys and one non-modifier key\n"
                "(for example: q, n, f8). Example: ctrl+shift+q -> ctrl+alt+shift+q."
            ),
            foreground="#5a5a5a",
            justify="left",
            wraplength=470,
        )
        guidance.pack(anchor="w", pady=(10, 0))

        form = ttk.Frame(container)
        form.pack(fill="both", expand=True, pady=(12, 0))

        ttk.Label(form, text="Normalize hotkey").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(form, text="Preview hotkey (auto)").grid(row=1, column=0, sticky="w", pady=(0, 6))

        self._preview_hotkey_var = tk.StringVar(value=to_preview_hotkey(normalize_base))
        self._normalize_entry = HotkeyCapture(
            form,
            initial_value=normalize_base,
            on_changed=self._sync_preview_hotkey,
        )
        self._preview_entry = ttk.Entry(
            form,
            textvariable=self._preview_hotkey_var,
            width=28,
            state="readonly",
        )

        self._preview_default_var = tk.BooleanVar(value=settings.preview_default)
        self._play_sound_var = tk.BooleanVar(value=settings.play_sound_on_success)

        self._normalize_entry.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=(0, 6))
        self._preview_entry.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(0, 6))

        ttk.Checkbutton(
            form,
            text="Start with preview enabled",
            variable=self._preview_default_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 4))

        ttk.Checkbutton(
            form,
            text="Play a success beep",
            variable=self._play_sound_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))

        form.columnconfigure(1, weight=1)

        rules_frame = ttk.Labelframe(container, text="Rules", padding=10)
        rules_frame.pack(fill="x", pady=(14, 0))
        ttk.Button(rules_frame, text="Open live rules.json", command=self._on_open_rules).pack(side="left")
        ttk.Button(rules_frame, text="View bundled defaults", command=self._on_open_default_rules).pack(side="left", padx=(8, 0))
        ttk.Button(rules_frame, text="Reset live rules to defaults", command=self._confirm_reset_rules).pack(side="left", padx=(8, 0))

        docs_frame = ttk.Labelframe(container, text="Docs", padding=10)
        docs_frame.pack(fill="x", pady=(14, 0))
        ttk.Button(docs_frame, text="Open README.md", command=self._on_open_readme).pack(side="left")
        ttk.Button(docs_frame, text="Open RULES.md", command=self._on_open_rules_guide).pack(side="left", padx=(8, 0))

        updates_frame = ttk.Labelframe(container, text="Updates", padding=10)
        updates_frame.pack(fill="x", pady=(14, 0))
        ttk.Label(updates_frame, text="App").pack(anchor="w")
        self._check_updates_button = ttk.Button(
            updates_frame,
            text=f"Check for updates (v{current_version})",
            command=self._start_update_check,
        )
        self._check_updates_button.pack(anchor="w", pady=(4, 0))
        self._update_status_var = tk.StringVar(value="")
        self._update_status_label = ttk.Label(
            updates_frame,
            textvariable=self._update_status_var,
            justify="left",
            wraplength=420,
        )
        self._update_status_label.pack(anchor="w", pady=(8, 0))
        self._open_download_button = ttk.Button(
            updates_frame,
            text="Open download page",
            command=self._open_download_page,
            state="disabled",
        )
        self._open_download_button.pack(anchor="w", pady=(8, 0))
        ttk.Separator(updates_frame, orient="horizontal").pack(fill="x", pady=(12, 10))
        ttk.Label(updates_frame, text="Default rules.json").pack(anchor="w")
        self._rules_status_var = tk.StringVar(value="")
        self._rules_status_label = ttk.Label(
            updates_frame,
            textvariable=self._rules_status_var,
            justify="left",
            wraplength=420,
        )
        self._rules_status_label.pack(anchor="w", pady=(4, 0))
        self._rules_detail_var = tk.StringVar(value="")
        self._rules_detail_label = ttk.Label(
            updates_frame,
            textvariable=self._rules_detail_var,
            justify="left",
            foreground="#5a5a5a",
            wraplength=420,
        )
        self._rules_detail_label.pack(anchor="w", pady=(6, 0))
        self._rules_action_button = ttk.Button(
            updates_frame,
            text="Review rules",
            command=self._on_open_rules,
            state="disabled",
        )
        self._rules_action_button.pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="right", padx=(0, 8))

        self._center_on_screen()
        self.focus()
        self._window.grab_set()

    def _start_update_check(self) -> None:
        self.set_update_checking()
        self._on_check_updates()

    def _open_download_page(self) -> None:
        if self._update_download_url:
            self._on_open_update_download(self._update_download_url)

    def set_update_checking(self) -> None:
        self._update_download_url = None
        self._check_updates_button.configure(state="disabled")
        self._open_download_button.configure(state="disabled")
        self._update_status_var.set("Checking for updates...")

    def set_update_available(self, status: UpdateStatus) -> None:
        self._update_download_url = status.download_url
        self._check_updates_button.configure(state="normal")
        self._open_download_button.configure(state="normal")
        self._update_status_var.set(
            f"Version {status.latest_version} is available. You are running {status.current_version}."
        )

    def set_up_to_date(self, current_version: str) -> None:
        self._update_download_url = None
        self._check_updates_button.configure(state="normal")
        self._open_download_button.configure(state="disabled")
        self._update_status_var.set(f"You are up to date on version {current_version}.")

    def set_update_error(self, message: str) -> None:
        self._update_download_url = None
        self._check_updates_button.configure(state="normal")
        self._open_download_button.configure(state="disabled")
        self._update_status_var.set(message)

    def set_rules_status(self, status: RulesVersionStatus) -> None:
        self._rules_status_var.set(status.headline)
        self._rules_detail_var.set(status.detail)
        if status.can_update:
            self._rules_action_button.configure(
                text="Update live rules to new defaults",
                command=self._confirm_reset_rules,
                state="normal",
            )
            return
        if status.is_customized:
            self._rules_action_button.configure(
                text="Review my live rules",
                command=self._on_open_rules,
                state="normal",
            )
            return
        self._rules_action_button.configure(
            text="Review rules",
            command=self._on_open_rules,
            state="disabled",
        )

    def _sync_preview_hotkey(self, normalize_base: str) -> None:
        self._preview_hotkey_var.set(to_preview_hotkey(normalize_base))

    def _center_on_screen(self) -> None:
        self._window.update_idletasks()
        width = self._window.winfo_reqwidth()
        height = self._window.winfo_reqheight()
        screen_w = self._window.winfo_screenwidth()
        screen_h = self._window.winfo_screenheight()
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 3, 0)
        self._window.geometry(f"+{x}+{y}")

    def focus(self) -> None:
        if not self._window.winfo_exists():
            return
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()
        self._window.after(50, self._window.lift)

    def save(self) -> None:
        normalize_hotkey = normalize_base_hotkey(self._normalize_entry.get_value())
        if not normalize_hotkey:
            messagebox.showerror(f"{APP_NAME} Settings", "Normalize hotkey is required.", parent=self._window)
            return
        if not _has_non_modifier_key(normalize_hotkey):
            messagebox.showerror(f"{APP_NAME} Settings", "Hotkey must include a non-modifier key.", parent=self._window)
            return
        if not _has_minimum_combo(normalize_hotkey):
            messagebox.showerror(f"{APP_NAME} Settings", "Hotkey must include at least 3 keys.", parent=self._window)
            return

        settings = AppSettings(
            normalize_hotkey=normalize_hotkey,
            preview_hotkey=to_preview_hotkey(normalize_hotkey),
            preview_default=bool(self._preview_default_var.get()),
            play_sound_on_success=bool(self._play_sound_var.get()),
        )
        if self._on_save(settings):
            self.cancel()

    def _confirm_reset_rules(self) -> None:
        should_reset = messagebox.askyesno(
            f"{APP_NAME} Settings",
            "Replace your live rules.json with the bundled defaults?",
            parent=self._window,
        )
        if should_reset:
            self._on_reset_rules()

    def cancel(self) -> None:
        if self._window.winfo_exists():
            try:
                self._window.grab_release()
            except tk.TclError:
                pass
            self._window.destroy()
        self._on_close()


