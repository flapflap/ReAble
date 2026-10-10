"""Fenêtre native (pywebview) autour du serveur local : sélecteur de dossier macOS, glisser-déposer, fermeture sûre."""
from __future__ import annotations

import json
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

    def open_url(self, url: str) -> bool:
        from .logic import AppLogic
        return AppLogic.open_url(url)

    def reveal(self, path: str) -> bool:
        from .logic import AppLogic
        return AppLogic.reveal(path)


def dropped_folder(path: str | None) -> dict:
    """Interprète un élément déposé sur la fenêtre : un dossier, ou un projet .als (on prend son dossier)."""
    if not path:
        return {"error": "Le chemin du dossier déposé n'a pas pu être lu. Utilisez « Choisir… »."}
    p = Path(path)
    if p.is_dir():
        return {"path": str(p)}
    if p.suffix.lower() == ".als" and p.parent.is_dir():
        return {"path": str(p.parent)}
    return {"error": "Déposez un dossier de projets (ou un projet Live .als), pas un autre type de fichier."}


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

    def on_drop(event):
        files = (event.get("dataTransfer") or {}).get("files") or []
        path = files[0].get("pywebviewFullPath") if files else None
        window.evaluate_js(f"window.reableDropped({json.dumps(dropped_folder(path))})")

    def on_loaded():
        from webview.dom import DOMEventHandler
        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)   # empêche la navigation du navigateur
    window.events.loaded += on_loaded
    def show_about():
        window.evaluate_js("window.reableShowAbout && window.reableShowAbout()")
    try:
        from webview.menu import Menu, MenuAction
        menu = [Menu("ReAble", [MenuAction("À propos de ReAble", show_about)])]
    except ImportError:                      # ancienne version de pywebview : pas de menu personnalisé
        menu = []
    try:
        webview.start(menu=menu)
    finally:
        app.stop()
    return 0
