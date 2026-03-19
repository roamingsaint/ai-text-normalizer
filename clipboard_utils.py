from __future__ import annotations

import ctypes
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from ctypes import wintypes
from typing import Iterator, Optional


LOGGER = logging.getLogger(__name__)


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


GMEM_MOVEABLE = 0x0002
CF_UNICODETEXT = 13

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_C = 0x43
VK_V = 0x56

try:
    import keyboard  # type: ignore
except Exception:  # pragma: no cover - import guard
    keyboard = None


class ClipboardError(RuntimeError):
    pass


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.OpenClipboard.argtypes = (wintypes.HWND,)
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = ()
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = ()
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = (wintypes.UINT,)
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
user32.SetClipboardData.restype = wintypes.HANDLE
user32.IsClipboardFormatAvailable.argtypes = (wintypes.UINT,)
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
user32.GetClipboardSequenceNumber.argtypes = ()
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalFree.restype = wintypes.HGLOBAL
kernel32.GlobalSize.argtypes = (wintypes.HGLOBAL,)
kernel32.GlobalSize.restype = ctypes.c_size_t


@dataclass
class ClipboardSnapshot:
    text: Optional[str]


def _raise_last_error(prefix: str) -> ClipboardError:
    error_code = ctypes.get_last_error()
    return ClipboardError(f"{prefix} failed with error code {error_code}")


@contextmanager
def _open_clipboard(retries: int = 30, delay: float = 0.01) -> Iterator[None]:
    last_error: Optional[ClipboardError] = None
    for _ in range(retries):
        if user32.OpenClipboard(None):
            try:
                yield
            finally:
                user32.CloseClipboard()
            return
        last_error = _raise_last_error("OpenClipboard")
        time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise ClipboardError("OpenClipboard failed")


def get_sequence_number() -> int:
    return int(user32.GetClipboardSequenceNumber())


def read_text() -> Optional[str]:
    with _open_clipboard():
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        locked = kernel32.GlobalLock(handle)
        if not locked:
            raise _raise_last_error("GlobalLock")
        try:
            text = ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
        return text


def write_text(text: str) -> None:
    encoded = (text + "\0").encode("utf-16-le")
    with _open_clipboard():
        if not user32.EmptyClipboard():
            raise _raise_last_error("EmptyClipboard")
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not handle:
            raise _raise_last_error("GlobalAlloc")
        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            raise _raise_last_error("GlobalLock")
        try:
            ctypes.memmove(locked, encoded, len(encoded))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise _raise_last_error("SetClipboardData")


def snapshot_text() -> ClipboardSnapshot:
    try:
        return ClipboardSnapshot(text=read_text())
    except ClipboardError:
        LOGGER.exception("failed to snapshot clipboard")
        return ClipboardSnapshot(text=None)


def restore_text(snapshot: ClipboardSnapshot) -> None:
    if snapshot.text is None:
        return
    try:
        write_text(snapshot.text)
    except ClipboardError:
        LOGGER.exception("failed to restore clipboard text")


def _build_key_input(vk: int, key_up: bool = False) -> INPUT:
    flags = KEYEVENTF_KEYUP if key_up else 0
    return INPUT(
        type=INPUT_KEYBOARD,
        union=INPUTUNION(
            ki=KEYBDINPUT(
                wVk=vk,
                wScan=0,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        ),
    )


def _send_inputs(inputs: list[INPUT]) -> None:
    array = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise _raise_last_error("SendInput")


def send_ctrl_c() -> None:
    if keyboard is not None:
        keyboard.press_and_release("ctrl+c")
        return
    _send_inputs(
        [
            _build_key_input(VK_CONTROL, key_up=False),
            _build_key_input(VK_C, key_up=False),
            _build_key_input(VK_C, key_up=True),
            _build_key_input(VK_CONTROL, key_up=True),
        ]
    )


def send_ctrl_v() -> None:
    if keyboard is not None:
        keyboard.press_and_release("ctrl+v")
        return
    _send_inputs(
        [
            _build_key_input(VK_CONTROL, key_up=False),
            _build_key_input(VK_V, key_up=False),
            _build_key_input(VK_V, key_up=True),
            _build_key_input(VK_CONTROL, key_up=True),
        ]
    )


def wait_for_sequence_change(original_sequence: int, timeout: float, poll_interval: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if get_sequence_number() != original_sequence:
            return True
        time.sleep(poll_interval)
    return False


def capture_selected_text(
    *,
    copy_timeout: float,
    poll_interval: float,
    settle_delay: float,
) -> tuple[ClipboardSnapshot, str] | None:
    snapshot = snapshot_text()
    original_sequence = get_sequence_number()
    send_ctrl_c()
    if not wait_for_sequence_change(original_sequence, copy_timeout, poll_interval):
        restore_text(snapshot)
        return None
    time.sleep(settle_delay)
    text = read_text()
    if not text:
        restore_text(snapshot)
        return None
    return snapshot, text


def replace_selection_with_text(
    text: str,
    snapshot: ClipboardSnapshot,
    *,
    restore_delay: float,
) -> None:
    write_text(text)
    try:
        send_ctrl_v()
        time.sleep(restore_delay)
    finally:
        restore_text(snapshot)
