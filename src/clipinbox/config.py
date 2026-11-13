"""Preferences belong in AppData, never next to the executable."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from clipinbox.hotkeys import parse_hotkey
from clipinbox.storage import StorageError, validate_path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    inbox_path: str = ""
    hotkey: str = "Ctrl+Alt+M"
    notify_success: bool = True
    schema_version: int = 1

    def validated(self):
        if not isinstance(self.inbox_path, str):
            raise ConfigError("O caminho configurado é inválido.")
        if self.inbox_path:
            try:
                validate_path(self.inbox_path)
            except StorageError as exc:
                raise ConfigError(str(exc)) from None
        try:
            shortcut = parse_hotkey(self.hotkey).label
        except ValueError as exc:
            raise ConfigError(str(exc)) from None
        if type(self.notify_success) is not bool or type(self.schema_version) is not int:
            raise ConfigError("Preferências inválidas.")
        if self.schema_version != 1:
            raise ConfigError("Esta versão não entende o formato das preferências.")
        return Config(self.inbox_path, shortcut, self.notify_success)


def config_path() -> Path:
    base = os.environ.get("APPDATA")
    if not base or not Path(base).is_absolute():
        raise ConfigError("O Windows não informou uma pasta APPDATA válida.")
    return Path(base) / "ClipInbox" / "config.json"


def load_config(path: Path) -> tuple[Config, str | None]:
    try:
        if path.stat().st_size > 65536:
            raise ValueError
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return Config(**data).validated(), None
    except FileNotFoundError:
        return Config(), None
    except (OSError, UnicodeError, ValueError, TypeError, ConfigError):
        return Config(), (
            "Não foi possível ler as preferências. Confere e salva as configurações novamente. "
            "O Inbox não foi alterado."
        )


def save_config(path: Path, config: Config) -> None:
    config = config.validated()
    tmp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=".config-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            tmp = Path(stream.name)
            json.dump(asdict(config), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except OSError:
        raise ConfigError("Não foi possível salvar as preferências em APPDATA.") from None
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
