"""Small, explicitly typed Win32 bindings. Importable on other OSes for core tests."""

import ctypes
import os
from ctypes import wintypes as wt


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wt.HWND),
        ("message", wt.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wt.DWORD),
        ("pt", wt.POINT),
        ("lPrivate", wt.DWORD),
    ]


def _bind(library, name, args, result):
    function = getattr(library, name)
    function.argtypes = args
    function.restype = result
    return function


class WindowsAPI:
    MSG = MSG

    def __init__(self):
        if os.name != "nt":
            raise OSError("ClipInbox requer Windows 10 ou 11.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _bind(self.user32, "RegisterHotKey", [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT], wt.BOOL)
        _bind(self.user32, "UnregisterHotKey", [wt.HWND, ctypes.c_int], wt.BOOL)
        _bind(
            self.user32,
            "GetMessageW",
            [ctypes.POINTER(MSG), wt.HWND, wt.UINT, wt.UINT],
            ctypes.c_int,
        )
        _bind(
            self.user32,
            "PeekMessageW",
            [ctypes.POINTER(MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT],
            wt.BOOL,
        )
        _bind(
            self.user32,
            "PostThreadMessageW",
            [wt.DWORD, wt.UINT, ctypes.c_size_t, ctypes.c_ssize_t],
            wt.BOOL,
        )
        _bind(self.kernel32, "GetCurrentThreadId", [], wt.DWORD)
        _bind(self.kernel32, "CreateMutexW", [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR], wt.HANDLE)
        _bind(self.kernel32, "CloseHandle", [wt.HANDLE], wt.BOOL)
        _bind(
            self.kernel32,
            "CreateFileW",
            [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE],
            wt.HANDLE,
        )


class SingleInstance:
    def __init__(self, name=r"Local\ClipInbox-90991A15-AE21-4F6A-A82D-06A228ED3306"):
        self.api = WindowsAPI()
        self.handle = self.api.kernel32.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not self.handle:
            raise ctypes.WinError(error)
        self.already_running = error == 183  # ERROR_ALREADY_EXISTS

    def close(self):
        if self.handle:
            self.api.kernel32.CloseHandle(self.handle)
            self.handle = None


def open_append_fd(path):
    import msvcrt

    api = WindowsAPI()
    # GENERIC_READ | FILE_APPEND_DATA, FILE_SHARE_READ, OPEN_EXISTING.
    # Deny writers and replacement while appending, never truncate or recreate.
    handle = api.kernel32.CreateFileW(str(path), 0x80000004, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_APPEND | os.O_BINARY)
    except BaseException:
        api.kernel32.CloseHandle(handle)
        raise


def enable_dpi_awareness():
    if os.name != "nt":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        function = _bind(user32, "SetProcessDpiAwarenessContext", [ctypes.c_void_p], wt.BOOL)
        function(ctypes.c_void_p(-4))  # Per-monitor v2. Manifest may have set it already.
    except AttributeError:
        _bind(user32, "SetProcessDPIAware", [], wt.BOOL)()
