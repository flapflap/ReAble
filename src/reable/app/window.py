"""Fenêtre native (pywebview) autour du serveur local : sélecteur de dossier macOS, glisser-déposer, fermeture sûre."""
from __future__ import annotations

import socket
import time
from pathlib import Path

from ..i18n import tr
from .logic import dropped_folder  # noqa: F401  (réexporté : utilisé par les tests)
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


_about_handler = None      # référence conservée : macOS ne garde pas le gestionnaire en vie


def install_about_item(push) -> bool:
    """Branche l'entrée « À propos de ReAble » du menu ReAble (le menu en gras) sur notre fenêtre,
    à la place du panneau standard qui n'affiche que la version. Renvoie False hors macOS."""
    global _about_handler
    try:
        import objc
        from AppKit import NSApp
        from Foundation import NSObject
        from PyObjCTools import AppHelper
    except ImportError:
        return False

    class AboutHandler(NSObject):
        @objc.python_method
        def bind(self, push_fn):
            self.push = push_fn
            return self

        def showAbout_(self, sender):
            self.push({"type": "about"})        # la page relève ce message (evaluate_js est refusé par la politique de sécurité de la page)

    def install():
        app_menu = NSApp.mainMenu().itemAtIndex_(0).submenu() if NSApp.mainMenu() else None
        if app_menu is None or app_menu.numberOfItems() == 0:
            return
        item = app_menu.itemAtIndex_(0)                      # « À propos de ReAble » : première entrée du menu de l'application
        global _about_handler
        _about_handler = AboutHandler.alloc().init().bind(push)
        item.setTarget_(_about_handler)
        item.setAction_("showAbout:")
    AppHelper.callAfter(install)
    return True


def request_close(app: App, confirm) -> bool:
    """Décide si la fenêtre peut se fermer. Pendant une tâche : demande confirmation, puis l'arrête proprement.

    `confirm(titre, message) -> bool` : boîte de dialogue native (ou simulée dans les tests)."""
    job = app.logic.jobs.current()
    if job is None:
        return True
    if not confirm(tr("Arrêter et fermer ?"),
                   tr("Une tâche est en cours. Si vous fermez, le projet en cours est abandonné proprement "
                      "et les copies déjà faites sont conservées.")):
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

    def on_shown():
        install_about_item(app.logic.push_ui)
    window.events.shown += on_shown
    try:                                     # demande à pywebview de relever les chemins déposés (sans passer par evaluate_js)
        from webview.dom import _dnd_state
        _dnd_state["num_listeners"] = max(1, _dnd_state.get("num_listeners", 0))
    except ImportError:
        pass
    try:
        webview.start()
    finally:
        app.stop()
    return 0
