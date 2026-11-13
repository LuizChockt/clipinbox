"""Opt-in packaging smoke test using only a temporary Inbox, never the clipboard.

This automates initialization, widgets, native registration, writing and shutdown.
It does not represent human interactive validation of the tray or keyboard.
"""

import json
import tempfile
import time
import tkinter as tk
from pathlib import Path

from clipinbox import __version__


def run_smoke(result_path: Path) -> int:
    from clipinbox.app import App
    from clipinbox.config import Config, save_config
    from clipinbox.storage import create_inbox
    from clipinbox.win32 import SingleInstance, enable_dpi_awareness

    result = {"version": __version__, "ok": False, "checks": [], "interactive": False}
    root = app = instance = None
    try:
        enable_dpi_awareness()
        instance = SingleInstance(r"Local\ClipInbox-packaging-smoke")
        if instance.already_running:
            raise RuntimeError("Another smoke test is running")
        with tempfile.TemporaryDirectory(prefix="ClipInbox test ") as folder:
            preferences = Path(folder) / "config.json"
            inbox = create_inbox(Path(folder) / "Inbox ação.md")
            save_config(preferences, Config(str(inbox), "Ctrl+Alt+Shift+F10", False))
            root = tk.Tk()
            root.withdraw()
            app = App(root, preferences)
            app.start()
            result["checks"].extend(["tk_init", "tray_init", "load_config"])
            stage = 0
            deadline = time.monotonic() + 20

            def tick():
                nonlocal stage
                try:
                    if time.monotonic() > deadline:
                        raise TimeoutError("smoke timeout")
                    if stage == 0 and app.pending == 0:
                        if not app.hotkeys._active or app.settings_window is not None:
                            raise RuntimeError("hotkey registration failed")
                        result["checks"].append("native_hotkey_register")
                        app.show_note()
                        assert app.note_window.window.title() == "Nova anotação"
                        app.note_window.text.insert("1.0", "Teste fictício — 日本語\nlinha 2")
                        app.note_window.save_button.invoke()
                        stage = 1
                    elif stage == 1 and app.pending == 0:
                        assert app.note_window is None
                        assert "Teste fictício — 日本語\nlinha 2" in inbox.read_text(
                            encoding="utf-8"
                        )
                        result["checks"].extend(["manual_widget_save", "utf8_append"])
                        app.show_settings()
                        assert app.settings_window.path.get() == str(inbox)
                        app.settings_window.close()
                        result["checks"].append("settings_widgets")
                        app.quit()
                        result["ok"] = True
                        return
                    root.after(100, tick)
                except Exception as exc:
                    result["error_type"] = type(exc).__name__
                    root.quit()

            root.after(100, tick)
            root.mainloop()
            app.cleanup()
            assert not app.hotkeys._thread.is_alive()
            assert not app.tray.thread.is_alive()
            result["checks"].append("ordered_shutdown")
            app = root = None
    except Exception as exc:
        result["ok"] = False
        result["error_type"] = type(exc).__name__
    finally:
        try:
            if app:
                app.cleanup()
            elif root:
                root.destroy()
        except Exception:
            result["ok"] = False
        if instance:
            instance.close()
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
