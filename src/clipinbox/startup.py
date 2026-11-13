"""Optional autostart: only our HKCU Run value; never HKLM or admin."""

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ClipInbox"


def startup_command() -> str:
    if not getattr(sys, "frozen", False):
        raise ValueError("A inicialização com o Windows está disponível no executável distribuído.")
    exe = str(Path(sys.executable).resolve())
    command = f'"{exe}"'
    if len(command) > 260:
        raise ValueError("Move o ClipInbox para um caminho mais curto para ativar a inicialização.")
    return command


def get_startup() -> str | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, VALUE_NAME)[0]
    except FileNotFoundError:
        return None


def restore_startup(value: str | None):
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if value is None:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, value)


def set_startup(enabled: bool):
    restore_startup(startup_command() if enabled else None)
