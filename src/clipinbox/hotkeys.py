"""One blocking Win32 message loop; no keyboard hook or clipboard polling."""

import ctypes
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass

MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_COMMAND = 0x8001
WM_QUIT = 0x0012


@dataclass(frozen=True)
class Hotkey:
    label: str
    modifiers: int
    vk: int


def parse_hotkey(value: str) -> Hotkey:
    if not isinstance(value, str):
        raise ValueError("O atalho deve ser um texto como Ctrl+Alt+M.")
    tokens = [token.strip().upper() for token in value.split("+")]
    mapping = {"CTRL": ("Ctrl", 2), "ALT": ("Alt", 1), "SHIFT": ("Shift", 4)}
    mods, key = tokens[:-1], tokens[-1]
    if not mods or len(set(mods)) != len(mods) or any(m not in mapping for m in mods):
        raise ValueError("Usa Ctrl, Alt e/ou Shift, sem repetição; a tecla Win é reservada.")
    # A small conservative grammar avoids stealing common editing shortcuts,
    # Alt+Tab, Ctrl+Alt+Del, F12, IME and Windows shortcuts.
    if len(mods) < 2 or not ({"CTRL", "ALT"} & set(mods)):
        raise ValueError("Usa pelo menos dois modificadores (ex.: Ctrl+Alt+M).")
    if len(key) == 1 and key in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 11:
        vk = 0x70 + int(key[1:]) - 1
        key = f"F{int(key[1:])}"
    else:
        raise ValueError("Usa uma letra A–Z, número 0–9 ou F1–F11. F12 é reservada.")
    ordered = [m for m in mapping if m in mods]
    return Hotkey(
        "+".join([mapping[m][0] for m in ordered] + [key]),
        sum(mapping[m][1] for m in ordered),
        vk,
    )


class HotkeyError(Exception):
    pass


class HotkeyManager:
    def __init__(self, on_capture, on_error):
        from clipinbox.win32 import WindowsAPI

        self.api = WindowsAPI()
        self.on_capture = on_capture
        self.on_error = on_error
        self._commands = queue.Queue()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ClipInbox-hotkey", daemon=True)
        self._thread_id = 0
        self._active_id = 0
        self._active = None
        self._thread.start()
        if not self._ready.wait(3) or not self._thread.is_alive():
            raise HotkeyError("Não foi possível iniciar o atalho global.")

    def set_hotkey(self, label: str) -> None:
        hotkey = parse_hotkey(label)
        future = Future()
        if not self._thread.is_alive():
            raise HotkeyError("O serviço de atalhos foi encerrado. Reinicia o ClipInbox.")
        self._commands.put((hotkey, future))
        if not self.api.user32.PostThreadMessageW(self._thread_id, WM_COMMAND, 0, 0):
            future.cancel()
            raise HotkeyError("Não foi possível comunicar com o atalho global.")
        # Executed from the application's worker for settings changes.
        future.result(timeout=5)

    def _register(self, hotkey: Hotkey):
        if self._active == hotkey:
            return
        new_id = 2 if self._active_id == 1 else 1
        if not self.api.user32.RegisterHotKey(
            None,
            new_id,
            hotkey.modifiers | MOD_NOREPEAT,
            hotkey.vk,
        ):
            raise HotkeyError(
                "O atalho não está disponível. Escolhe outra combinação; "
                "outro aplicativo pode estar usando esta."
            )
        if self._active_id and not self.api.user32.UnregisterHotKey(None, self._active_id):
            self.api.user32.UnregisterHotKey(None, new_id)
            raise HotkeyError("Não foi possível liberar o atalho anterior.")
        self._active_id, self._active = new_id, hotkey

    def _run(self):
        message = self.api.MSG()
        try:
            self._thread_id = self.api.kernel32.GetCurrentThreadId()
            self.api.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            self._ready.set()
            while True:
                result = self.api.user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == 0:
                    break
                if result == -1:
                    raise HotkeyError("O Windows encerrou o processamento de atalhos.")
                if message.message == WM_COMMAND:
                    while True:
                        try:
                            hotkey, future = self._commands.get_nowait()
                        except queue.Empty:
                            break
                        if future.set_running_or_notify_cancel():
                            try:
                                self._register(hotkey)
                            except Exception as exc:
                                future.set_exception(exc)
                            else:
                                future.set_result(None)
                elif message.message == WM_HOTKEY and message.wParam == self._active_id:
                    self.on_capture()
        except Exception:
            self.on_error("O atalho global parou. Reinicia o ClipInbox.")
        finally:
            if self._active_id:
                self.api.user32.UnregisterHotKey(None, self._active_id)
            self._active_id = 0
            while not self._commands.empty():
                _, future = self._commands.get_nowait()
                if not future.done():
                    future.set_exception(HotkeyError("O atalho global foi encerrado."))
            self._ready.set()

    def stop(self):
        if self._thread.is_alive():
            if not self.api.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0):
                raise HotkeyError("Não foi possível encerrar o atalho global.")
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                raise HotkeyError("O atalho ainda está encerrando.")
