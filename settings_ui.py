from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from config import APP_NAME
from settings_store import AppSettings


class SettingsDialog:
    def __init__(
        self,
        root: tk.Tk,
        settings: AppSettings,
        on_save: Callable[[AppSettings], None],
        on_close: Callable[[], None],
    ) -> None:
        self._root = root
        self._on_save = on_save
        self._on_close = on_close
        self._window = tk.Toplevel(root)
        self._window.title(f"{APP_NAME} Settings")
        self._window.resizable(False, False)
        self._window.transient(root)
        self._window.attributes("-topmost", True)
        self._window.protocol("WM_DELETE_WINDOW", self.cancel)

        container = ttk.Frame(self._window, padding=14)
        container.pack(fill="both", expand=True)

        form = ttk.Frame(container)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Normalize hotkey").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(form, text="Preview hotkey").grid(row=1, column=0, sticky="w", pady=(0, 6))

        self._normalize_var = tk.StringVar(value=settings.normalize_hotkey)
        self._preview_var = tk.StringVar(value=settings.preview_hotkey)
        self._preview_default_var = tk.BooleanVar(value=settings.preview_default)
        self._play_sound_var = tk.BooleanVar(value=settings.play_sound_on_success)

        normalize_entry = ttk.Entry(form, textvariable=self._normalize_var, width=28)
        preview_entry = ttk.Entry(form, textvariable=self._preview_var, width=28)
        normalize_entry.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=(0, 6))
        preview_entry.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(0, 6))

        ttk.Checkbutton(
            form,
            text="Start with preview enabled",
            variable=self._preview_default_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 4))

        ttk.Checkbutton(
            form,
            text="Play a sound on success",
            variable=self._play_sound_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))

        hint = ttk.Label(
            form,
            text="Use strings like ctrl+shift+q or ctrl+alt+shift+q.",
            foreground="#5a5a5a",
        )
        hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        form.columnconfigure(1, weight=1)

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(14, 0))

        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="right", padx=(0, 8))

        self._window.after(50, self._window.lift)

    def save(self) -> None:
        settings = AppSettings(
            normalize_hotkey=self._normalize_var.get().strip(),
            preview_hotkey=self._preview_var.get().strip(),
            preview_default=bool(self._preview_default_var.get()),
            play_sound_on_success=bool(self._play_sound_var.get()),
        )
        if self._on_save(settings):
            self._window.destroy()
            self._on_close()

    def cancel(self) -> None:
        if self._window.winfo_exists():
            self._window.destroy()
        self._on_close()
