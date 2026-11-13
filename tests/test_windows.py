"""Real Windows APIs, not mocks. No physical-key or human tray validation."""

import ctypes
import os
import queue
import threading
import uuid

import pytest

from clipinbox.hotkeys import MOD_NOREPEAT, HotkeyError, HotkeyManager
from clipinbox.storage import MarkdownWriter, StorageError, create_inbox, validate_path

pytestmark = [pytest.mark.windows, pytest.mark.skipif(os.name != "nt", reason="Windows API")]


def test_native_hotkey_conflict_switch_rollback_and_release():
    errors = []
    first = HotkeyManager(lambda: None, errors.append)
    second = HotkeyManager(lambda: None, errors.append)
    try:
        first.set_hotkey("Ctrl+Alt+Shift+F11")
        second.set_hotkey("Ctrl+Alt+Shift+F10")
        with pytest.raises(HotkeyError):
            second.set_hotkey("Ctrl+Alt+Shift+F11")
        assert second._active.label == "Ctrl+Alt+Shift+F10"
        first.set_hotkey("Ctrl+Alt+Shift+F9")
        second.set_hotkey("Ctrl+Alt+Shift+F11")
        assert MOD_NOREPEAT == 0x4000
    finally:
        first.stop()
        second.stop()
    assert not first._thread.is_alive()
    assert not second._thread.is_alive()
    assert not errors
    third = HotkeyManager(lambda: None, errors.append)
    try:
        third.set_hotkey("Ctrl+Alt+Shift+F11")
    finally:
        third.stop()


def test_synthetic_message_dispatch_stays_on_worker():
    # Deliberately synthetic WM_HOTKEY, NOT proof that a physical key works.
    events = queue.Queue()
    manager = HotkeyManager(lambda: events.put(threading.get_ident()), lambda e: None)
    try:
        manager.set_hotkey("Ctrl+Alt+Shift+F11")
        manager.api.user32.PostThreadMessageW(manager._thread_id, 0x0312, manager._active_id, 0)
        assert events.get(timeout=3) != threading.get_ident()
    finally:
        manager.stop()


def test_native_single_instance_mutex_and_release():
    from clipinbox.win32 import SingleInstance

    name = "Local\\ClipInbox-test-" + uuid.uuid4().hex
    first, second = SingleInstance(name), SingleInstance(name)
    try:
        assert not first.already_running
        assert second.already_running
    finally:
        first.close()
        second.close()
    third = SingleInstance(name)
    try:
        assert not third.already_running
    finally:
        third.close()


def test_native_share_mode_prevents_write_or_delete(tmp_path):
    from clipinbox.storage import _open_append

    inbox = create_inbox(tmp_path / "Inbox.md")
    inbox.write_bytes(b"original")
    with _open_append(inbox):
        with pytest.raises(OSError):
            inbox.open("ab")
        with pytest.raises(OSError):
            inbox.unlink()
    MarkdownWriter().append(inbox, "ok")
    assert inbox.read_bytes().startswith(b"original")


def test_native_locked_file_reports_failure_without_writing(tmp_path):
    from clipinbox.win32 import WindowsAPI

    inbox = create_inbox(tmp_path / "Inbox.md")
    api = WindowsAPI()
    handle = api.kernel32.CreateFileW(str(inbox), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        with pytest.raises(StorageError):
            MarkdownWriter().append(inbox, "teste")
    finally:
        api.kernel32.CloseHandle(handle)
    assert inbox.read_bytes() == b""


@pytest.mark.parametrize("path", [r"C:\test\CON.md", r"C:\test\a:b.md", r"\\.\device.md"])
def test_windows_device_and_stream_names_rejected(path):
    with pytest.raises(StorageError):
        validate_path(path)


def test_msg_layout_x64():
    from clipinbox.win32 import MSG

    assert ctypes.sizeof(MSG) == (48 if ctypes.sizeof(ctypes.c_void_p) == 8 else 32)


@pytest.mark.desktop
@pytest.mark.skipif(
    os.environ.get("CLIPINBOX_DESKTOP_TESTS") != "1",
    reason="requires an isolated Windows desktop/clipboard",
)
def test_real_tk_clipboard_read_and_manual_failure_preserves_draft(tmp_path):
    import tkinter as tk
    from types import SimpleNamespace

    from clipinbox.clipboard import read_text
    from clipinbox.config import Config
    from clipinbox.ui import NoteWindow, configure_style

    root = tk.Tk()
    root.withdraw()
    try:
        configure_style(root)
        root.clipboard_clear()
        root.clipboard_append("fictício — 日本語\nsegunda linha")
        root.update()
        assert read_text(root) == "fictício — 日本語\nsegunda linha"
        before = root.clipboard_get()
        app = SimpleNamespace(root=root, config=Config(str(tmp_path / "Inbox.md")))
        drafts = []
        app.save_note = lambda text, win: (drafts.append(text), win.saved("Falha de teste"))
        window = NoteWindow(app, "rascunho")
        app.note_window = window
        root.update()
        window.save_button.invoke()
        assert drafts == ["rascunho"]
        assert window.text.get("1.0", "end-1c") == "rascunho"
        assert not window.busy
        assert root.clipboard_get() == before
        window.destroy()
        root.clipboard_clear()
    finally:
        root.destroy()
