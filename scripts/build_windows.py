"""Build, launch the packaged exe in a space-containing path, then ZIP/hash it."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("O pacote deve ser construído no Windows com Python x64.")
    from clipinbox import __version__

    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        if os.environ.get("GITHUB_REF_NAME") != f"v{__version__}":
            raise SystemExit("A tag não corresponde à versão do código.")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "ClipInbox.spec"],
        cwd=ROOT,
        check=True,
    )
    bundle = ROOT / "dist" / "ClipInbox"
    for name in ("README.md", "LICENSE", "CHANGELOG.md"):
        shutil.copy2(ROOT / name, bundle / name)
    # Include dependency licensing in the portable distribution.
    from importlib.metadata import distribution

    licenses = bundle / "licenses"
    licenses.mkdir(exist_ok=True)
    for name in ("pystray", "Pillow", "six", "pyinstaller"):
        dist = distribution(name)
        for item in dist.files or []:
            if "license" in item.name.lower() or "copying" in item.name.lower():
                source = Path(dist.locate_file(item))
                if source.is_file():
                    shutil.copy2(source, licenses / f"{name}-{source.name}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    for item in (Path(sys.base_prefix) / "tcl").rglob("license.terms"):
        shutil.copy2(item, licenses / f"{item.parent.name}-license.terms.txt")
    test_parent = ROOT / "build" / "path with spaces ação"
    test_bundle = test_parent / "ClipInbox"
    shutil.copytree(bundle, test_bundle, dirs_exist_ok=True)
    report = ROOT / "build" / "smoke-result.json"
    exe = test_bundle / "ClipInbox.exe"
    subprocess.run([str(exe), "--smoke-test", str(report)], cwd=test_parent, check=True, timeout=40)
    result = json.loads(report.read_text(encoding="utf-8"))
    if not result.get("ok"):
        raise SystemExit("Falha no smoke test do executável.")
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    name = f"ClipInbox-v{__version__}-windows-x64"
    archive = Path(shutil.make_archive(str(output / name), "zip", bundle.parent, bundle.name))
    digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    shutil.copy2(report, output / "smoke-result.json")
    print(f"Built {archive.name}; SHA-256 {digest}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
