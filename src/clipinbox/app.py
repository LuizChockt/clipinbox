"""Application lifecycle: Tk main thread, tray, message loop and one I/O worker."""

import argparse
import os
import queue
import sys
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import messagebox

from clipinbox import __version__
from clipinbox.clipboard import read_text
from clipinbox.config import ConfigError, config_path, load_config, save_config
from clipinbox.hotkeys import HotkeyError, HotkeyManager
from clipinbox.startup import get_startup, restore_startup, set_startup
from clipinbox.storage import MarkdownWriter, StorageError, validate_path
from clipinbox.tray import Tray
from clipinbox.ui import NoteWindow, SettingsWindow, configure_style
from clipinbox.win32 import SingleInstance, enable_dpi_awareness


class App:
    ConfigError = ConfigError

    def __init__(self, root, preferences):
        self.root = root
        self.preferences = preferences
        self.config, self.config_warning = load_config(preferences)
        self.writer = MarkdownWriter()
        self.events = queue.Queue()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ClipInbox-io")
        self.pending = 0
        self.capture_busy = False
        self.failed_capture = None
        self.note_window = self.settings_window = None
        self.hotkeys = self.tray = None
        self.closing = False
        self.last_status = ""
        self.startup_enabled = False
        self.exit_code = 0
        configure_style(root)
        root.report_callback_exception = self.callback_error

    def emit(self, name, data=None):
        self.events.put((name, data))

    def start(self):
        self.hotkeys = HotkeyManager(
            lambda: self.emit("capture"), lambda error: self.emit("error", error)
        )
        self.tray = Tray(self.emit)
        self.tray.start()
        try:
            self.startup_enabled = get_startup() is not None
        except OSError:
            self.config_warning = "Não foi possível ler a opção de inicialização com Windows."
        self.root.after(100, self.drain_events)
        self.submit(lambda: self.hotkeys.set_hotkey(self.config.hotkey), self.hotkey_ready)
        if not self.config.inbox_path or self.config_warning:
            self.show_settings(
                self.config_warning or "Escolhe o arquivo para receber tuas capturas."
            )

    def hotkey_ready(self, result, error):
        if error:
            self.show_settings(self.public_error(error))

    def submit(self, operation, callback):
        self.pending += 1
        future = self.worker.submit(operation)
        # Done callback only writes to Queue; even root.after is forbidden here.
        future.add_done_callback(lambda done: self.emit("done", (done, callback)))

    def drain_events(self):
        if self.closing:
            return
        try:
            for _ in range(50):
                try:
                    name, data = self.events.get_nowait()
                except queue.Empty:
                    break
                if name == "done":
                    future, callback = data
                    self.pending -= 1
                    try:
                        result = future.result()
                    except Exception as exc:
                        callback(None, exc)
                    else:
                        callback(result, None)
                elif name == "capture":
                    self.capture()
                elif name == "note":
                    self.show_note()
                elif name == "open":
                    self.open_inbox()
                elif name == "settings":
                    self.show_settings(self.last_status)
                elif name == "quit":
                    self.quit()
                elif name == "error":
                    self.notify(data, error=True)
                elif name == "tray_error":
                    messagebox.showerror(
                        "ClipInbox", "A bandeja parou. Reinicia o aplicativo.", parent=self.root
                    )
                    self.exit_code = 1
                    self.quit()
                if self.closing:
                    break
        finally:
            if not self.closing:
                self.root.after(100, self.drain_events)

    @staticmethod
    def public_error(error):
        if isinstance(error, (StorageError, ConfigError, HotkeyError)):
            return str(error)
        return "A operação não foi concluída. Confere o arquivo e as permissões."

    def callback_error(self, exc_type, exc, traceback):
        # No exception text/traceback: either may contain note content or paths.
        self.notify("Ocorreu um erro na interface. O texto não foi descartado.", error=True)

    def notify(self, message, *, error=False):
        self.last_status = message
        if self.tray and (error or self.config.notify_success):
            self.tray.notify(message, error=error)

    def capture(self):
        if self.failed_capture is not None:
            self.notify(
                "Há uma captura não salva. Abre Nova anotação para recuperá-la.", error=True
            )
            return
        if self.capture_busy:
            self.notify(
                "A captura anterior ainda está sendo salva. Aguarda e tenta de novo.", error=True
            )
            return
        try:
            target = validate_path(self.config.inbox_path)
            text = read_text(self.root)
        except StorageError as exc:
            self.notify(str(exc), error=True)
            return
        self.capture_busy = True

        def finished(result, error):
            self.capture_busy = False
            if error:
                self.failed_capture = (text, target, self.public_error(error))
                self.notify(
                    self.public_error(error) + " Texto mantido em Nova anotação.", error=True
                )
            else:
                self.notify("Anotação salva no Inbox.")

        self.submit(lambda: self.writer.append(target, text), finished)

    def show_note(self):
        if self.note_window:
            self.note_window.focus()
            return
        text, warning = "", ""
        if self.failed_capture:
            text, target, error = self.failed_capture
            warning = f"Captura recuperada de {target}. {error}"
        self.note_window = NoteWindow(self, text, warning)
        self.failed_capture = None

    def save_note(self, text, window):
        target = self.config.inbox_path

        def finished(result, error):
            window.saved(self.public_error(error) if error else None)
            if not error:
                self.notify("Anotação salva no Inbox.")

        self.submit(lambda: self.writer.append(target, text), finished)

    def show_settings(self, warning=""):
        if self.settings_window:
            if warning:
                self.settings_window.status.configure(text=warning)
            self.settings_window.focus()
        else:
            self.settings_window = SettingsWindow(self, warning)

    def apply_settings(self, new, startup_enabled, window):
        old = self.config

        def apply():
            previous_startup = get_startup()
            self.hotkeys.set_hotkey(new.hotkey)  # Old registration survives a conflict.
            try:
                if startup_enabled:
                    set_startup(True)
                elif previous_startup is not None:
                    set_startup(False)
                save_config(self.preferences, new)
            except Exception as original:
                rollback_failed = False
                try:
                    restore_startup(previous_startup)
                except OSError:
                    rollback_failed = True
                try:
                    self.hotkeys.set_hotkey(old.hotkey)
                except Exception:
                    rollback_failed = True
                if rollback_failed:
                    raise ConfigError(
                        "As configurações não foram salvas e a restauração foi incompleta. "
                        "Confere a inicialização e o atalho antes de continuar."
                    ) from None
                if isinstance(original, ValueError):
                    raise ConfigError(str(original)) from None
                raise

        def finished(result, error):
            if not error:
                self.config = new
                self.startup_enabled = startup_enabled
                self.config_warning = None
                if self.note_window:
                    self.note_window.refresh_destination()
                self.notify("Configurações salvas.")
            window.saved(self.public_error(error) if error else None)

        self.submit(apply, finished)

    def open_inbox(self):
        try:
            path = validate_path(self.config.inbox_path)
            if not path.is_file():
                raise StorageError("O Inbox não existe ou está inacessível.")
            os.startfile(str(path))
        except (StorageError, OSError) as exc:
            messagebox.showerror("Abrir Inbox", self.public_error(exc), parent=self.root)

    def quit(self):
        if self.pending:
            self.notify("Aguarda a operação em andamento antes de sair.", error=True)
            return
        if self.note_window and not self.note_window.can_close():
            return
        if self.failed_capture and not messagebox.askyesno(
            "Sair do ClipInbox?",
            "Há uma captura não salva em memória. Descartá-la e sair?",
            parent=self.root,
        ):
            return
        self.closing = True
        self.root.quit()

    def cleanup(self):
        self.closing = True
        self.worker.shutdown(wait=True, cancel_futures=False)
        try:
            if self.hotkeys:
                self.hotkeys.stop()
        finally:
            try:
                if self.tray:
                    self.tray.stop()
            finally:
                self.root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description="ClipInbox — clipboard para Markdown")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--smoke-test", metavar="RESULT_JSON", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if os.name != "nt":
        print("ClipInbox requer Windows 10 ou Windows 11.", file=sys.stderr)
        return 1
    if args.smoke_test:
        from clipinbox.smoke import run_smoke

        return run_smoke(Path(args.smoke_test))
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    instance = app = None
    try:
        instance = SingleInstance()
        if instance.already_running:
            messagebox.showinfo("ClipInbox", "O ClipInbox já está aberto na bandeja.", parent=root)
            return 0
        app = App(root, config_path())
        app.start()
        root.mainloop()
        return app.exit_code
    except Exception:
        messagebox.showerror(
            "ClipInbox",
            "Não foi possível iniciar o ClipInbox. "
            "Confere a pasta extraída e reinicia o aplicativo.",
            parent=root,
        )
        return 1
    finally:
        try:
            if app:
                app.cleanup()
            else:
                root.destroy()
        finally:
            if instance:
                instance.close()
