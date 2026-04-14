from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from config import APP_NAME, PREVIEW_MIN_SIZE, PREVIEW_WINDOW_GEOMETRY


LOGGER = logging.getLogger(__name__)


def _center_window_on_screen(window: tk.Toplevel, *, width: int | None = None, height: int | None = None, vertical_fraction: float = 0.33) -> None:
    window.update_idletasks()
    target_width = width or window.winfo_reqwidth()
    target_height = height or window.winfo_reqheight()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = max((screen_w - target_width) // 2, 0)
    y = max(int((screen_h - target_height) * vertical_fraction), 0)
    window.geometry(f"{target_width}x{target_height}+{x}+{y}")


class PreviewDialog:
    def __init__(
        self,
        root: tk.Tk,
        original_text: str,
        normalized_text: str,
        on_replace: Callable[[], None],
        on_cancel: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self._root = root
        self._on_replace = on_replace
        self._on_cancel = on_cancel
        self._on_close = on_close
        self._window = tk.Toplevel(root)
        self._window.withdraw()
        self._window.title(f"{APP_NAME} Preview")
        self._window.minsize(*PREVIEW_MIN_SIZE)
        self._window.attributes("-topmost", True)
        self._window.protocol("WM_DELETE_WINDOW", self.cancel)

        container = ttk.Frame(self._window, padding=12)
        container.pack(fill="both", expand=True)

        header = ttk.Label(
            container,
            text="Review the captured text before replacing the selection.",
        )
        header.pack(anchor="w", pady=(0, 10))

        panes = ttk.Panedwindow(container, orient="horizontal")
        panes.pack(fill="both", expand=True)

        left_frame = ttk.Labelframe(panes, text="Original")
        right_frame = ttk.Labelframe(panes, text="Normalized")
        panes.add(left_frame, weight=1)
        panes.add(right_frame, weight=1)

        self._build_readonly_text(left_frame, original_text)
        self._build_readonly_text(right_frame, normalized_text)

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))

        cancel_button = ttk.Button(button_row, text="Cancel", command=self.cancel)
        replace_button = ttk.Button(button_row, text="Replace", command=self.replace)
        cancel_button.pack(side="right")
        replace_button.pack(side="right", padx=(0, 8))

        width, height = (int(part) for part in PREVIEW_WINDOW_GEOMETRY.split('x', 1))
        _center_window_on_screen(self._window, width=width, height=height, vertical_fraction=0.2)
        self.focus()

    @staticmethod
    def _build_readonly_text(parent: ttk.Frame, text: str) -> tk.Text:
        text_widget = tk.Text(parent, wrap="word", height=20, width=50, padx=8, pady=8)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")
        return text_widget

    def focus(self) -> None:
        if not self._window.winfo_exists():
            return
        self._window.deiconify()
        self._window.lift()
        self._window.focus_force()
        self._window.after(50, self._window.lift)

    def replace(self) -> None:
        self._close()
        self._on_replace()

    def cancel(self) -> None:
        self._close()
        self._on_cancel()

    def _close(self) -> None:
        if self._window.winfo_exists():
            self._window.destroy()
        self._on_close()


class ProcessingDialog:
    def __init__(self, root: tk.Tk, message: str = "Processing selection...") -> None:
        self._root = root
        self._window = tk.Toplevel(root)
        self._window.withdraw()
        self._window.title(APP_NAME)
        self._window.resizable(False, False)
        self._window.attributes("-topmost", True)
        self._window.overrideredirect(True)
        self._window.protocol("WM_DELETE_WINDOW", lambda: None)
        self._guard_active = False
        self._guard_release_job: str | None = None

        container = ttk.Frame(self._window, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text=message).pack(anchor="w")
        bar = ttk.Progressbar(container, mode="indeterminate", length=240)
        bar.pack(fill="x", pady=(10, 0))
        bar.start(12)

        _center_window_on_screen(self._window)
        self._window.deiconify()
        self._window.lift()

    def activate_input_guard(self, timeout_seconds: float) -> bool:
        if not self._window.winfo_exists():
            return False
        self.release_input_guard()
        try:
            self._window.grab_set_global()
            self._guard_active = True
        except tk.TclError:
            LOGGER.exception("processing input guard failed")
            self._guard_active = False
            return False
        timeout_ms = max(int(timeout_seconds * 1000), 1)
        self._guard_release_job = self._window.after(timeout_ms, self.release_input_guard)
        return True

    def release_input_guard(self) -> None:
        if self._guard_release_job is not None and self._window.winfo_exists():
            try:
                self._window.after_cancel(self._guard_release_job)
            except tk.TclError:
                pass
            self._guard_release_job = None
        if self._guard_active and self._window.winfo_exists():
            try:
                self._window.grab_release()
            except tk.TclError:
                pass
        self._guard_active = False

    def close(self) -> None:
        self.release_input_guard()
        if self._window.winfo_exists():
            self._window.destroy()


class TrayApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        on_normalize_now: Callable[[], None],
        on_toggle_preview: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_exit: Callable[[], None],
        preview_state_getter: Callable[[], bool],
    ) -> None:
        self._root = root
        self._on_normalize_now = on_normalize_now
        self._on_toggle_preview = on_toggle_preview
        self._on_open_settings = on_open_settings
        self._on_exit = on_exit
        self._preview_state_getter = preview_state_getter
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._active_preview: PreviewDialog | None = None
        self._active_processing: ProcessingDialog | None = None
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()

    def start(self) -> None:
        image = self._create_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Normalize selected text now", self._handle_normalize_now),
            pystray.MenuItem(
                "Toggle preview before replace",
                self._handle_toggle_preview,
                checked=lambda item: self._preview_state_getter(),
            ),
            pystray.MenuItem("Settings...", self._handle_open_settings),
            pystray.MenuItem("Exit", self._handle_exit),
        )
        self._icon = pystray.Icon(APP_NAME, image, APP_NAME, menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()

    def notify(self, message: str, title: str | None = None) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title=title or APP_NAME)
        except Exception:
            LOGGER.exception("tray notification failed")

    def show_preview_dialog(
        self,
        original_text: str,
        normalized_text: str,
        on_replace: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        if self._active_preview is not None:
            self._active_preview.focus()
            return

        def _clear_preview() -> None:
            self._active_preview = None

        self._active_preview = PreviewDialog(
            self._root,
            original_text,
            normalized_text,
            on_replace,
            on_cancel,
            _clear_preview,
        )

    def show_processing(self, message: str = "Processing selection...") -> None:
        def _open() -> None:
            if self._active_processing is None:
                self._active_processing = ProcessingDialog(self._root, message)

        self._schedule_on_ui_wait(_open)

    def hide_processing(self) -> None:
        def _close() -> None:
            if self._active_processing is not None:
                self._active_processing.close()
                self._active_processing = None

        self._schedule_on_ui_wait(_close)

    def schedule_on_ui(self, callback: Callable[[], None]) -> None:
        self._ui_queue.put(callback)

    def _schedule_on_ui_wait(self, callback: Callable[[], object], timeout_seconds: float = 1.0) -> object:
        done = threading.Event()
        result: dict[str, object] = {"value": None}

        def _wrapped() -> None:
            try:
                result["value"] = callback()
            finally:
                done.set()

        self.schedule_on_ui(_wrapped)
        done.wait(timeout_seconds)
        return result["value"]

    def activate_input_guard(self, timeout_seconds: float) -> bool:
        def _activate() -> bool:
            if self._active_processing is None:
                return False
            return self._active_processing.activate_input_guard(timeout_seconds)

        return bool(self._schedule_on_ui_wait(_activate))

    def release_input_guard(self) -> None:
        def _release() -> None:
            if self._active_processing is not None:
                self._active_processing.release_input_guard()

        self._schedule_on_ui_wait(_release)

    def process_pending_ui(self) -> None:
        while True:
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                return
            try:
                callback()
            except Exception:
                LOGGER.exception("ui callback failed")

    def _handle_normalize_now(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._on_normalize_now()

    def _handle_toggle_preview(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._on_toggle_preview()
        try:
            icon.update_menu()
        except Exception:
            LOGGER.exception("failed to update tray menu")

    def _handle_open_settings(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._on_open_settings()

    def _handle_exit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self._on_exit()

    @staticmethod
    def _create_icon_image() -> Image.Image:
        image = Image.new("RGBA", (64, 64), (29, 39, 52, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=(237, 242, 247, 255))
        draw.rounded_rectangle((13, 13, 51, 51), radius=10, fill=(29, 39, 52, 255))
        draw.line((19, 25, 44, 25), fill=(255, 255, 255, 255), width=4)
        draw.line((19, 35, 44, 35), fill=(255, 255, 255, 255), width=4)
        draw.line((19, 45, 35, 45), fill=(255, 255, 255, 255), width=4)
        return image
