import codecs
import errno
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from clipinbox import storage
from clipinbox.storage import MarkdownWriter, StorageError, create_inbox, validate_path

STAMP = datetime(2026, 1, 2, 3, 4, 5)


@pytest.fixture
def inbox(tmp_path):
    return create_inbox(tmp_path / "Inbox.md")


@pytest.fixture
def writer():
    return MarkdownWriter(clock=lambda: STAMP)


def test_create_empty_exclusive_and_no_overwrite(tmp_path):
    path = create_inbox(tmp_path / "Inbox.md")
    assert path.read_bytes() == b""
    path.write_text("original", encoding="utf-8")
    with pytest.raises(StorageError, match="já existe"):
        create_inbox(path)
    assert path.read_text(encoding="utf-8") == "original"


def test_first_append_exact_timestamp(writer, inbox):
    writer.append(inbox, "Texto")
    assert inbox.read_bytes() == b"### 2026-01-02 03:04:05\n\nTexto\n\n"


def test_explicit_identical_captures_are_preserved(writer, inbox):
    writer.append(inbox, "igual")
    writer.append(inbox, "igual")
    assert inbox.read_bytes().count(b"igual") == 2
    assert inbox.read_bytes().count(b"### ") == 2


@pytest.mark.parametrize(
    "original",
    [
        b"antigo",
        b"antigo\n",
        b"antigo\n\n",
        b"antigo\r\n",
        b"antigo\r\n\r\n",
        b"---\ntags: [test]\n---\n# Inbox\n",
    ],
)
def test_previous_bytes_and_file_identity_preserved(writer, inbox, original):
    inbox.write_bytes(original)
    before = inbox.stat().st_ino
    writer.append(inbox, "novo")
    assert inbox.read_bytes().startswith(original)
    assert inbox.stat().st_ino == before
    assert inbox.read_bytes()[len(original) :].count(b"### ") == 1


@pytest.mark.parametrize(
    "text",
    [
        "ação — 日本語 😀 café",
        "  espaços antes e depois  ",
        "linha 1\nlinha 2\n",
        "linha 1\r\nlinha 2\r\n",
        "a\nb\r\nc\r",
        "# Título\n- item\n> citação\n\n```python\nprint('ok')\n```",
    ],
)
def test_text_is_preserved_exactly(writer, inbox, text):
    writer.append(inbox, text)
    assert text.encode("utf-8") in inbox.read_bytes()


@pytest.mark.parametrize("text", ["", " ", "\t\n\r", None, 42, "bad\x00text", "\ud800"])
def test_invalid_text_does_not_write(writer, inbox, text):
    with pytest.raises(StorageError):
        writer.append(inbox, text)
    assert inbox.read_bytes() == b""


@pytest.mark.parametrize(
    "original",
    [
        "exemplo".encode("utf-16"),
        "exemplo".encode("utf-32"),
        "exemplo".encode("utf-16-be"),
        b"caf\xe9",
        b"\xff\xfe",
        b"a" * 70000 + b"\xff",
    ],
)
def test_incompatible_encoding_is_rejected_without_changes(writer, inbox, original):
    inbox.write_bytes(original)
    with pytest.raises(StorageError, match="UTF-8"):
        writer.append(inbox, "novo")
    assert inbox.read_bytes() == original


@pytest.mark.parametrize("original", [codecs.BOM_UTF8, codecs.BOM_UTF8 + b"first\r\n"])
def test_bom_preserved_once(writer, inbox, original):
    inbox.write_bytes(original)
    writer.append(inbox, "novo")
    data = inbox.read_bytes()
    assert data.startswith(original)
    assert data.count(codecs.BOM_UTF8) == 1
    if original == codecs.BOM_UTF8:
        assert data.startswith(codecs.BOM_UTF8 + b"### ")


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_structural_newline_matches_existing(writer, inbox, newline):
    inbox.write_bytes(b"old" + newline)
    writer.append(inbox, "novo")
    assert inbox.read_bytes() == (
        b"old" + newline * 2 + b"### 2026-01-02 03:04:05" + newline * 2 + b"novo" + newline * 2
    )


def test_unicode_path_and_spaces(writer, tmp_path):
    folder = tmp_path / "Estudos e ação 日本語"
    folder.mkdir()
    path = create_inbox(folder / "Anotações [1].md")
    writer.append(path, "teste")
    assert "teste" in path.read_text(encoding="utf-8")


def test_missing_folder_not_created(writer, tmp_path):
    path = tmp_path / "ausente" / "Inbox.md"
    with pytest.raises(StorageError):
        create_inbox(path)
    with pytest.raises(StorageError):
        writer.append(path, "teste")
    assert not path.parent.exists()


def test_deleted_inbox_not_recreated(writer, inbox):
    inbox.unlink()
    with pytest.raises(StorageError):
        writer.append(inbox, "teste")
    assert not inbox.exists()


@pytest.mark.parametrize("value", ["", "relative.md", "/tmp/no.txt", "bad\x00.md", 123])
def test_bad_path(value):
    with pytest.raises(StorageError):
        validate_path(value)


def test_large_file_streamed_once_then_bounded_reads(writer, inbox, monkeypatch):
    # Multi-byte character straddles the 64 KiB decoder boundary.
    original = b"x" * 65535 + "á".encode() + b"\n" + b"z" * (2 * 1024 * 1024)
    inbox.write_bytes(original)
    actual_open = storage._open_append
    reads = []

    class Measured:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def read(self, size):
            assert 0 < size <= 65536
            data = self.stream.read(size)
            reads.append(len(data))
            return data

    monkeypatch.setattr(storage, "_open_append", lambda path: Measured(actual_open(path)))
    writer.append(inbox, "primeira")
    assert sum(reads) >= len(original)
    reads.clear()
    writer.append(inbox, "segunda")
    assert sum(reads) <= 4
    assert inbox.read_bytes().startswith(original)


def test_external_change_invalidates_encoding_cache(writer, inbox):
    writer.append(inbox, "ok")
    with inbox.open("ab") as stream:
        stream.write(b"\xff")
    before = inbox.read_bytes()
    with pytest.raises(StorageError):
        writer.append(inbox, "novo")
    assert inbox.read_bytes() == before


@pytest.mark.parametrize(
    "error",
    [
        PermissionError(errno.EACCES, "denied"),
        OSError(errno.ENOSPC, "full"),
        OSError(errno.EIO, "disk"),
    ],
)
def test_open_failures_no_false_success(writer, inbox, monkeypatch, error):
    def fail(path):
        raise error

    monkeypatch.setattr(storage, "_open_append", fail)
    with pytest.raises(StorageError) as result:
        writer.append(inbox, "SENSITIVE_TEST_MARKER")
    assert not result.value.uncertain
    assert "SENSITIVE_TEST_MARKER" not in str(result.value)
    assert inbox.read_bytes() == b""


def test_fsync_failure_uncertain_no_retry(writer, inbox, monkeypatch):
    def fail(fd):
        raise OSError(errno.ENOSPC, "full")

    monkeypatch.setattr(storage.os, "fsync", fail)
    with pytest.raises(StorageError, match="parcial") as result:
        writer.append(inbox, "uma vez")
    assert result.value.uncertain
    assert inbox.read_bytes().count(b"uma vez") == 1


@pytest.mark.parametrize("kind", ["short", "exception_after_partial", "zero"])
def test_partial_write_never_rolls_back_or_retries(writer, inbox, monkeypatch, kind):
    original = b"preservar\n"
    inbox.write_bytes(original)
    actual_open = storage._open_append
    calls = []

    class Broken:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, data):
            calls.append(data)
            if kind == "zero":
                return 0
            n = self.stream.write(data[:12])
            if kind == "exception_after_partial":
                raise OSError(errno.ENOSPC, "full")
            return n

    monkeypatch.setattr(storage, "_open_append", lambda path: Broken(actual_open(path)))
    with pytest.raises(StorageError) as result:
        writer.append(inbox, "nova nota")
    assert result.value.uncertain
    assert len(calls) == 1
    assert inbox.read_bytes().startswith(original)
    assert len(inbox.read_bytes()) == len(original) + (0 if kind == "zero" else 12)


def test_threads_do_not_interleave(writer, inbox):
    entries = [f"<entry-{i:03d}> " + "á" * 5000 for i in range(32)]
    with ThreadPoolExecutor(max_workers=8) as workers:
        list(workers.map(lambda text: writer.append(inbox, text), entries))
    data = inbox.read_text(encoding="utf-8")
    assert data.count("### ") == len(entries)
    for entry in entries:
        assert data.count(entry) == 1


def test_readonly_file(writer, inbox):
    inbox.chmod(0o444)
    try:
        if os.name != "nt" and os.geteuid() == 0:
            pytest.skip("root ignora bits de permissão; PermissionError também testado por injeção")
        with pytest.raises(StorageError):
            writer.append(inbox, "não escrever")
        assert inbox.read_bytes() == b""
    finally:
        inbox.chmod(0o600)
