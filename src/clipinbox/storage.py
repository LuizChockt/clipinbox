"""Append UTF-8, sem truncamento, com confirmação de flush/fsync.

O Windows impede outros escritores/deleções enquanto o handle está aberto.
Isso não impede que um editor sobrescreva o arquivo depois de fechá-lo.
"""

import codecs
import errno
import os
import stat
import threading
from datetime import datetime
from pathlib import Path


class StorageError(Exception):
    def __init__(self, message: str, *, uncertain: bool = False):
        super().__init__(message)
        self.uncertain = uncertain


def validate_path(value: str | Path) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise StorageError("Escolhe um arquivo Markdown nas configurações.")
    raw = str(value)
    if any(ord(c) < 32 for c in raw):
        raise StorageError("O caminho contém caracteres inválidos.")
    path = Path(value)
    if not path.is_absolute() or path.suffix.lower() != ".md":
        raise StorageError("Escolhe um caminho absoluto para um arquivo .md.")
    if os.name == "nt":
        # Exclude device namespaces, alternate data streams and reserved names.
        if raw.startswith(("\\\\?\\", "\\\\.\\")):
            raise StorageError("Caminhos de dispositivo não são aceitos.")
        for part in path.parts[1:]:
            if any(c in part for c in '<>:"|?*') or part.endswith((" ", ".")):
                raise StorageError("O caminho contém um nome inválido no Windows.")
            if Path(part).is_reserved():
                raise StorageError("O caminho contém um nome reservado do Windows.")
    return path


def validate_text(text: str) -> bytes:
    if not isinstance(text, str) or not text.strip():
        raise StorageError("Não há texto para salvar.")
    if "\x00" in text:
        raise StorageError("O conteúdo contém caracteres nulos e não é texto compatível.")
    try:
        return text.encode("utf-8")
    except UnicodeError:
        raise StorageError("O texto contém caracteres Unicode inválidos.") from None


def _io_message(exc: OSError) -> str:
    if isinstance(exc, FileNotFoundError):
        return "O arquivo ou a pasta não existe. Confere o destino nas configurações."
    if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (5, 32, 33):
        return "Sem acesso ao Inbox: confere as permissões, somente leitura ou outro editor."
    if exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) == 112:
        return "Não há espaço livre suficiente no disco."
    return "Não foi possível acessar o Inbox. Confere o arquivo, o disco e as permissões."


def create_inbox(path: str | Path) -> Path:
    """Only called after explicit user confirmation. Never makes parents."""
    target = validate_path(path)
    try:
        with target.open("xb", buffering=0) as stream:
            os.fsync(stream.fileno())
    except FileExistsError:
        raise StorageError("O arquivo já existe. Seleciona-o como arquivo existente.") from None
    except OSError as exc:
        raise StorageError(_io_message(exc)) from None
    return target


def _open_append(path: Path):
    if os.name == "nt":
        from clipinbox.win32 import open_append_fd

        fd = open_append_fd(path)
    else:
        # Only for core tests/development; the application supports Windows only.
        fd = os.open(path, os.O_RDWR | os.O_APPEND)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise StorageError("O destino precisa ser um arquivo comum.")
        if os.name != "nt":
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return os.fdopen(fd, "a+b", buffering=0)
    except BaseException:
        os.close(fd)
        raise


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _validate_encoding(stream) -> bytes:
    """Stream once per external change, bounded memory, strict UTF-8."""
    stream.seek(0)
    decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
    newline = b"\n"
    found_newline = False
    previous = b""
    try:
        while chunk := stream.read(65536):
            if b"\0" in chunk:
                raise ValueError
            decoder.decode(chunk)
            if not found_newline and b"\n" in chunk:
                sample = previous + chunk
                offset = sample.index(b"\n")
                newline = b"\r\n" if offset and sample[offset - 1] == 13 else b"\n"
                found_newline = True
            previous = chunk[-1:]
        decoder.decode(b"", final=True)
    except (UnicodeError, ValueError):
        raise StorageError(
            "O Inbox não é UTF-8 válido (pode ser UTF-16 ou outro formato). "
            "Converte uma cópia para UTF-8 no teu editor antes de selecioná-la."
        ) from None
    return newline


def _blank_line_suffix(data: bytes, newline: bytes) -> bytes:
    normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalized.endswith(b"\n\n"):
        return b""
    if normalized.endswith(b"\n"):
        return newline
    return newline * 2


class MarkdownWriter:
    def __init__(self, clock=None):
        self._clock = clock or datetime.now
        self._lock = threading.Lock()
        self._cache = None

    def append(self, path: str | Path, text: str) -> None:
        target = validate_path(path)
        body = validate_text(text)
        attempted = False
        with self._lock:
            try:
                with _open_append(target) as stream:
                    before = os.fstat(stream.fileno())
                    signature = _signature(before)
                    if self._cache and self._cache[:2] == (str(target), signature):
                        newline = self._cache[2]
                    else:
                        newline = _validate_encoding(stream)
                    stream.seek(max(0, before.st_size - 4))
                    tail = stream.read(4)
                    empty = before.st_size == 0 or (before.st_size == 3 and tail == codecs.BOM_UTF8)
                    prefix = b"" if empty else _blank_line_suffix(tail, newline)
                    stamp = self._clock().strftime("%Y-%m-%d %H:%M:%S").encode("ascii")
                    payload = (
                        prefix
                        + b"### "
                        + stamp
                        + newline * 2
                        + body
                        + _blank_line_suffix(body[-4:], newline)
                    )
                    if _signature(os.fstat(stream.fileno())) != signature:
                        raise StorageError("O Inbox mudou durante a leitura. Tenta novamente.")
                    attempted = True
                    # A short write has uncertain results. Do not retry or truncate.
                    written = stream.write(payload)
                    if written != len(payload):
                        raise OSError(errno.EIO, "short append")
                    stream.flush()
                    os.fsync(stream.fileno())
                    after = os.fstat(stream.fileno())
                    if after.st_size != before.st_size + len(payload):
                        raise OSError(errno.EIO, "size changed")
                    self._cache = (str(target), _signature(after), newline)
            except OSError as exc:
                self._cache = None
                message = _io_message(exc)
                if attempted:
                    message += (
                        " A gravação pode ter sido parcial ou já estar no arquivo. "
                        "Confere o Inbox antes de tentar de novo; não houve repetição automática."
                    )
                raise StorageError(message, uncertain=attempted) from None
