"""Compact ttk windows. All methods run on the main Tk thread."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from clipinbox.config import Config
from clipinbox.storage import StorageError, create_inbox, validate_path, validate_text


def configure_style(root):
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    root.option_add("*Font", "{Segoe UI} 10")
    style.configure("TButton", padding=(10, 5))
    style.configure("Title.TLabel", font=("Segoe UI", 15, "bold"))
    icon = Path(__file__).parent / "resources" / "clipinbox.ico"
    try:
        root.iconbitmap(default=str(icon))
    except tk.TclError:
        pass


class NoteWindow:
    def __init__(self, app, text="", warning=""):
        self.app = app
        self.busy = False
        self.window = tk.Toplevel(app.root)
        self.window.title("Nova anotação")
        self.window.minsize(480, 330)
        self.window.geometry("600x420")
        frame = ttk.Frame(self.window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Nova anotação", style="Title.TLabel").pack(anchor="w")
        self.destination = ttk.Label(frame, wraplength=540)
        self.destination.pack(anchor="w", pady=(6, 12))
        self.text = ScrolledText(
            frame,
            wrap="word",
            undo=True,
            height=10,
            font=("Segoe UI", 11),
            relief="solid",
            borderwidth=1,
        )
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", text)
        self.status = ttk.Label(frame, text=warning, wraplength=540)
        self.status.pack(anchor="w", pady=(10, 6))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancelar", command=self.close).pack(side="right")
        self.save_button = ttk.Button(buttons, text="Salvar · Ctrl+Enter", command=self.save)
        self.save_button.pack(side="right", padx=(0, 8))
        self.window.bind("<Control-Return>", lambda event: self.save())
        self.window.bind("<Escape>", lambda event: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh_destination()
        self.window.after(50, self.text.focus_set)

    def refresh_destination(self):
        path = self.app.config.inbox_path or "seleciona um arquivo nas configurações"
        self.destination.configure(text=f"Destino: {path}")

    def focus(self):
        self.window.deiconify()
        self.window.lift()
        self.text.focus_set()

    def save(self):
        if self.busy:
            return "break"
        text = self.text.get("1.0", "end-1c")
        try:
            validate_text(text)
            validate_path(self.app.config.inbox_path)
        except StorageError as exc:
            self.status.configure(text=str(exc))
            return "break"
        self.busy = True
        self.save_button.state(["disabled"])
        self.text.configure(state="disabled")
        self.status.configure(text="Salvando…")
        self.app.save_note(text, self)
        return "break"

    def saved(self, error=None):
        self.busy = False
        if error is None:
            self.destroy()
            return
        self.text.configure(state="normal")
        self.save_button.state(["!disabled"])
        self.status.configure(text=error)
        # The complete draft is still in the widget. No automatic retry.

    def can_close(self):
        if self.busy:
            self.status.configure(text="Aguarda o término da gravação antes de fechar.")
            return False
        if self.text.get("1.0", "end-1c").strip():
            return messagebox.askyesno(
                "Descartar anotação?",
                "O texto ainda não foi salvo. Queres descartá-lo?",
                parent=self.window,
            )
        return True

    def close(self):
        if self.can_close():
            self.destroy()
        return "break"

    def destroy(self):
        self.window.destroy()
        self.app.note_window = None


class SettingsWindow:
    def __init__(self, app, warning=""):
        self.app = app
        self.busy = False
        self.window = tk.Toplevel(app.root)
        self.window.title("Configurações — ClipInbox")
        self.window.resizable(True, False)
        self.window.minsize(560, 420)
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="Teu Inbox, a um atalho", style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 14)
        )
        ttk.Label(frame, text="Arquivo Markdown").grid(row=1, column=0, sticky="w")
        self.path = tk.StringVar(value=app.config.inbox_path)
        self.path_entry = ttk.Entry(frame, textvariable=self.path, width=62)
        self.path_entry.grid(row=2, column=0, sticky="ew", pady=(5, 8))
        files = ttk.Frame(frame)
        files.grid(row=3, column=0, sticky="w")
        ttk.Button(files, text="Selecionar existente…", command=self.select_existing).pack(
            side="left"
        )
        ttk.Button(files, text="Criar novo…", command=self.create_new).pack(side="left", padx=8)
        ttk.Label(frame, text="Atalho global").grid(row=4, column=0, sticky="w", pady=(16, 4))
        self.hotkey = tk.StringVar(value=app.config.hotkey)
        ttk.Entry(frame, textvariable=self.hotkey, width=25).grid(row=5, column=0, sticky="w")
        ttk.Label(frame, text="Ex.: Ctrl+Alt+M ou Ctrl+Shift+F9. Win e F12 são reservadas.").grid(
            row=6, column=0, sticky="w", pady=(4, 10)
        )
        self.success = tk.BooleanVar(value=app.config.notify_success)
        ttk.Checkbutton(frame, text="Notificar capturas concluídas", variable=self.success).grid(
            row=7, column=0, sticky="w"
        )
        self.startup = tk.BooleanVar(value=app.startup_enabled)
        auto = ttk.Checkbutton(frame, text="Iniciar ClipInbox com o Windows", variable=self.startup)
        auto.grid(row=8, column=0, sticky="w", pady=(4, 8))
        if not getattr(sys, "frozen", False) and not app.startup_enabled:
            auto.state(["disabled"])
        ttk.Label(
            frame,
            wraplength=540,
            text=(
                "O atalho salva exatamente o texto copiado, inclusive senhas ou informações "
                "confidenciais. Usa-o apenas para o que desejas registrar."
            ),
        ).grid(row=9, column=0, sticky="w", pady=8)
        self.status = ttk.Label(frame, text=warning, wraplength=540)
        self.status.grid(row=10, column=0, sticky="w", pady=(3, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=11, column=0, sticky="e")
        ttk.Button(buttons, text="Cancelar", command=self.close).pack(side="right")
        self.save_button = ttk.Button(buttons, text="Salvar", command=self.save)
        self.save_button.pack(side="right", padx=8)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda event: self.close())
        self.window.after(50, self.path_entry.focus_set)

    def select_existing(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            parent=self.window, title="Selecionar Inbox", filetypes=[("Markdown", "*.md")]
        )
        if path:
            self.path.set(path)

    def create_new(self):
        if self.busy:
            return
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Criar Inbox",
            defaultextension=".md",
            initialfile="Inbox.md",
            filetypes=[("Markdown", "*.md")],
            confirmoverwrite=False,
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Criar arquivo?",
            f"Criar um arquivo Markdown vazio em:\n\n{path}\n\n"
            "Arquivos existentes não serão substituídos.",
            parent=self.window,
        ):
            return
        try:
            create_inbox(path)
        except StorageError as exc:
            self.status.configure(text=str(exc))
        else:
            self.path.set(path)
            self.status.configure(text="Arquivo vazio criado. Salva para usá-lo como destino.")

    def save(self):
        if self.busy:
            return
        try:
            config = Config(self.path.get(), self.hotkey.get(), self.success.get()).validated()
            validate_path(config.inbox_path)
            if not Path(config.inbox_path).is_file():
                raise StorageError("Seleciona um arquivo existente ou usa Criar novo.")
        except (ValueError, StorageError, self.app.ConfigError) as exc:
            self.status.configure(text=str(exc))
            return
        self.busy = True
        self.save_button.state(["disabled"])
        self.status.configure(text="Aplicando configurações…")
        self.app.apply_settings(config, self.startup.get(), self)

    def saved(self, error=None):
        self.busy = False
        if error:
            self.save_button.state(["!disabled"])
            self.status.configure(text=error)
        else:
            self.close()

    def focus(self):
        self.window.deiconify()
        self.window.lift()
        self.path_entry.focus_set()

    def close(self):
        if not self.busy:
            self.window.destroy()
            self.app.settings_window = None
        return "break"
