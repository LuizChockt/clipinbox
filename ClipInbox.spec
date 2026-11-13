# Windows x64 / Python 3.12. Paths are relative to this spec, never machine-specific.
from pathlib import Path

root = Path(SPECPATH)
resources = root / "src" / "clipinbox" / "resources"
a = Analysis(
    [str(root / "scripts" / "launcher.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(resources / "clipinbox.ico"), "clipinbox/resources"),
           (str(resources / "clipinbox.png"), "clipinbox/resources")],
    hiddenimports=["pystray._win32"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["pystray._darwin", "pystray._xorg", "pystray._gtk", "pystray._appindicator",
              "pytest", "unittest", "pydoc", "doctest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="ClipInbox", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    disable_windowed_traceback=True, icon=str(resources / "clipinbox.ico"),
    version=str(root / "scripts" / "version_info.txt"),
    manifest=str(root / "scripts" / "app.manifest"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ClipInbox")
