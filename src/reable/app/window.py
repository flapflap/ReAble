"""Fenêtre native (pywebview) autour du serveur local : sélecteur de dossier macOS, glisser-déposer, fermeture sûre."""
from __future__ import annotations

import socket
import time
from pathlib import Path

from .server import App

STOP_WAIT = 5.0     # secondes laissées à une tâche pour s'arrêter proprement à la fermeture


def free_port(preferred: int = 3000) -> int:
    """Port 3000 s'il est libre (règle du projet), sinon un port libre quelconque."""
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise OSError("aucun port local disponible")


class NativeApi:
    """Fonctions natives exposées à la page (window.pywebview.api.*)."""

    def __init__(self) -> None:
        self.window = None

    def choose_folder(self) -> str | None:
        import webview
        r = self.window.create_file_dialog(webview.FOLDER_DIALOG, directory=str(Path.home() / "Music"))
        return str(r[0]) if r else None

    def reveal(self, path: str) -> bool:
        from .logic import AppLogic
        return AppLogic.reveal(path)


def request_close(app: App, confirm) -> bool:
    """Décide si la fenêtre peut se fermer. Pendant une tâche : demande confirmation, puis l'arrête proprement.

    `confirm(titre, message) -> bool` : boîte de dialogue native (ou simulée dans les tests)."""
    job = app.logic.jobs.current()
    if job is None:
        return True
    if not confirm("Arrêter et fermer ?",
                   "Une tâche est en cours. Si vous fermez, le projet en cours est abandonné proprement "
                   "et les copies déjà faites sont conservées."):
        return False
    app.logic.jobs.stop(job.id)
    t0 = time.time()
    while app.logic.jobs.current() is not None and time.time() - t0 < STOP_WAIT:
        time.sleep(0.05)
    return True


def run(port: int | None = None) -> int:
    import webview
    app = App(port=free_port(3000) if port is None else port)
    app.start()
    api = NativeApi()
    window = webview.create_window("ReAble", app.url, js_api=api, width=1100, height=720, min_size=(900, 620))
    api.window = window

    def on_closing():
        return request_close(app, lambda title, msg: window.create_confirmation_dialog(title, msg))
    window.events.closing += on_closing
    try:
        webview.start()
    finally:
        app.stop()
    return 0
