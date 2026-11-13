import sys
from types import SimpleNamespace

import pytest

from clipinbox import startup


@pytest.fixture
def registry(monkeypatch):
    values = {"OtherApplication": "unchanged"}
    accesses = []

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def open_key(hive, path, *args):
        accesses.append((hive, path))
        return Key()

    def query(key, name):
        if name not in values:
            raise FileNotFoundError
        return values[name], 1

    def delete(key, name):
        if name not in values:
            raise FileNotFoundError
        del values[name]

    mock = SimpleNamespace(
        HKEY_CURRENT_USER="HKCU",
        KEY_SET_VALUE=2,
        REG_SZ=1,
        OpenKey=open_key,
        CreateKeyEx=open_key,
        QueryValueEx=query,
        SetValueEx=lambda key, name, reserved, typ, value: values.update({name: value}),
        DeleteValue=delete,
    )
    monkeypatch.setitem(sys.modules, "winreg", mock)
    return values, accesses


def test_startup_optional_user_only_quoted_and_reversible(tmp_path, monkeypatch, registry):
    values, accesses = registry
    exe = tmp_path / "app with spaces" / "ClipInbox.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert startup.get_startup() is None
    startup.set_startup(True)
    assert startup.get_startup() == f'"{exe.resolve()}"'
    startup.set_startup(False)
    startup.set_startup(False)
    assert startup.get_startup() is None
    assert values == {"OtherApplication": "unchanged"}
    assert all(hive == "HKCU" and path == startup.RUN_KEY for hive, path in accesses)


def test_source_mode_cannot_enable_startup(monkeypatch, registry):
    monkeypatch.delattr(sys, "frozen", raising=False)
    with pytest.raises(ValueError, match="executável"):
        startup.set_startup(True)


def test_registry_failure_is_not_silenced(monkeypatch, registry):
    def fail(*args):
        raise PermissionError

    monkeypatch.setattr(sys.modules["winreg"], "CreateKeyEx", fail)
    with pytest.raises(PermissionError):
        startup.set_startup(False)
