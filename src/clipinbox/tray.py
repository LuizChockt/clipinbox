"""All callbacks enqueue actions; this thread never accesses Tk."""

import threading
from pathlib import Path


class Tray:
    def __init__(self, emit):
        import pystray
        from PIL import Image

        self._ready = threading.Event()
        self._error = False
        self._emit = emit
        self._image = Image.open(Path(__file__).parent / "resources" / "clipinbox.png")

        def action(name):
            return lambda icon, item: emit(name, None)

        self.icon = pystray.Icon(
            "ClipInbox",
            self._image,
            "ClipInbox",
            menu=pystray.Menu(
                pystray.MenuItem("Capturar área de transferência", action("capture")),
                pystray.MenuItem("Nova anotação", action("note"), default=True),
                pystray.MenuItem("Abrir Inbox", action("open")),
                pystray.MenuItem("Configurações", action("settings")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", action("quit")),
            ),
        )
        self.thread = threading.Thread(target=self._run, name="ClipInbox-tray", daemon=True)

    def _run(self):
        try:
            self.icon.run(setup=self._setup)
        except Exception:
            self._error = True
            self._ready.set()
            self._emit("tray_error", None)

    def _setup(self, icon):
        try:
            icon.visible = True
        except Exception:
            self._error = True
        finally:
            self._ready.set()

    def start(self):
        self.thread.start()
        if not self._ready.wait(5) or self._error:
            raise RuntimeError("Não foi possível criar o ícone na bandeja.")

    def notify(self, message: str, *, error: bool = False):
        # Tooltip remains useful when Windows suppresses balloons.
        try:
            self.icon.title = "ClipInbox — " + message[:100]
            if self.icon.HAS_NOTIFICATION:
                self.icon.notify(message, "ClipInbox — atenção" if error else "ClipInbox")
        except Exception:
            pass  # Notification failure must never change a save result.

    def stop(self):
        self.icon.stop()
        self.thread.join(timeout=3)
        self._image.close()
