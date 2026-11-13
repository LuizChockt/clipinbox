import json

import pytest

from clipinbox import config as config_module
from clipinbox.config import Config, ConfigError, config_path, load_config, save_config
from clipinbox.hotkeys import parse_hotkey


def test_roundtrip_and_no_markdown_changes(tmp_path):
    inbox = tmp_path / "Anotações.md"
    inbox.write_bytes(b"unchanged")
    path = tmp_path / "prefs" / "config.json"
    config = Config(str(inbox), "ctrl + alt + m", False)
    save_config(path, config)
    loaded, warning = load_config(path)
    assert warning is None
    assert loaded == Config(str(inbox), "Ctrl+Alt+M", False)
    assert inbox.read_bytes() == b"unchanged"
    assert not list(path.parent.glob("*.tmp"))


def test_missing_config_returns_defaults(tmp_path):
    assert load_config(tmp_path / "missing.json") == (Config(), None)


@pytest.mark.parametrize(
    "data",
    [
        b"broken{",
        b"null",
        b"[]",
        b"\xff",
        b"{}" * 40000,
        json.dumps({"inbox_path": 42}).encode(),
        json.dumps({"hotkey": "Win+M"}).encode(),
        json.dumps({"inbox_path": "relative.md"}).encode(),
        json.dumps({"notify_success": "yes"}).encode(),
        json.dumps({"schema_version": 2}).encode(),
        json.dumps({"unexpected": True}).encode(),
    ],
)
def test_corrupt_config_recoverable_and_not_overwritten(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_bytes(data)
    config, warning = load_config(path)
    assert config == Config()
    assert warning
    assert path.read_bytes() == data


def test_atomic_replace_failure_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    save_config(path, Config())
    original = path.read_bytes()

    def fail(*args):
        raise PermissionError

    monkeypatch.setattr(config_module.os, "replace", fail)
    with pytest.raises(ConfigError):
        save_config(path, Config(hotkey="Ctrl+Shift+F9"))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_appdata_location(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert config_path() == tmp_path / "ClipInbox" / "config.json"
    monkeypatch.delenv("APPDATA")
    with pytest.raises(ConfigError):
        config_path()


@pytest.mark.parametrize(
    "value",
    [
        "M",
        "Ctrl+M",
        "Alt+Tab",
        "Ctrl+Alt+Delete",
        "Win+M",
        "Ctrl+Alt+F12",
        "Ctrl+Ctrl+M",
        "Ctrl+Alt+F0",
        "Ctrl+Alt+",
        "Shift+F9",
        None,
        "Ctrl+Alt+á",
    ],
)
def test_invalid_or_reserved_hotkeys(value):
    with pytest.raises(ValueError):
        parse_hotkey(value)


@pytest.mark.parametrize(
    ("value", "label", "modifiers", "vk"),
    [
        ("Ctrl+Alt+M", "Ctrl+Alt+M", 3, 77),
        ("shift+ctrl+f9", "Ctrl+Shift+F9", 6, 120),
        (" alt + ctrl + shift + 9 ", "Ctrl+Alt+Shift+9", 7, 57),
        ("Alt+Shift+F11", "Alt+Shift+F11", 5, 122),
    ],
)
def test_supported_hotkeys(value, label, modifiers, vk):
    hotkey = parse_hotkey(value)
    assert (hotkey.label, hotkey.modifiers, hotkey.vk) == (label, modifiers, vk)
