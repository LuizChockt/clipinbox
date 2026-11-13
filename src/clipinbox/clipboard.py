"""Called only by explicit capture commands, on the Tk thread."""

import tkinter as tk

from clipinbox.storage import StorageError, validate_text


def read_text(root) -> str:
    try:
        text = root.clipboard_get()
    except tk.TclError:
        raise StorageError(
            "A área de transferência está ocupada ou não contém texto. "
            "Copia um texto e tenta de novo."
        ) from None
    validate_text(text)
    return text
