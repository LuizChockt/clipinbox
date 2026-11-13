import threading
import tkinter as tk
from types import SimpleNamespace

import pytest

from clipinbox.app import App
from clipinbox.clipboard import read_text
from clipinbox.config import Config
from clipinbox.storage import StorageError


def test_clipboard_read_exactly_once_on_explicit_call():
    calls = []

    def get():
        calls.append(threading.get_ident())
        return "ação\nlinha 2"

    assert read_text(SimpleNamespace(clipboard_get=get)) == "ação\nlinha 2"
    assert calls == [threading.get_ident()]


def test_clipboard_busy_or_nontext():
    def fail():
        raise tk.TclError("private details")

    with pytest.raises(StorageError) as exc:
        read_text(SimpleNamespace(clipboard_get=fail))
    assert "private details" not in str(exc.value)


def test_missing_destination_does_not_read_clipboard():
    app = App.__new__(App)
    app.failed_capture = None
    app.capture_busy = False
    app.config = Config()
    app.root = SimpleNamespace(clipboard_get=lambda: pytest.fail("must not read"))
    errors = []
    app.notify = lambda message, **kwargs: errors.append(message)
    app.capture()
    assert errors


def test_duplicate_event_while_capture_pending_does_not_read_again(tmp_path):
    app = App.__new__(App)
    app.failed_capture = None
    app.capture_busy = False
    app.config = Config(str(tmp_path / "Inbox.md"))
    calls, operations, notifications = [], [], []

    def get():
        calls.append(1)
        return "draft"

    app.root = SimpleNamespace(clipboard_get=get)
    app.submit = lambda op, done: operations.append((op, done))
    app.notify = lambda message, **kwargs: notifications.append(message)
    app.capture()
    app.capture()
    assert len(calls) == len(operations) == 1
    operations[0][1](None, None)
    app.capture()
    assert len(calls) == len(operations) == 2  # Explicit same text allowed after completion.


def test_failed_capture_retained_and_not_retried(tmp_path):
    app = App.__new__(App)
    app.failed_capture = None
    app.capture_busy = False
    app.config = Config(str(tmp_path / "Inbox.md"))
    app.root = SimpleNamespace(clipboard_get=lambda: "private draft")
    operations, notifications = [], []
    app.submit = lambda op, done: operations.append((op, done))
    app.notify = lambda message, **kwargs: notifications.append(message)
    app.capture()
    operations[0][1](None, StorageError("Verifica o arquivo", uncertain=True))
    app.capture()
    assert len(operations) == 1
    assert app.failed_capture[0] == "private draft"
    assert all("private draft" not in message for message in notifications)


def test_unknown_exceptions_do_not_expose_content():
    assert "secret" not in App.public_error(RuntimeError("secret"))
