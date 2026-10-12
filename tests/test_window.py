import pytest
import threading
import time

from reable.app.server import App
from reable.app.window import free_port, request_close


def test_free_port_prefers_3000_then_falls_back():
    import socket
    p = free_port(3000)
    assert p == 3000 or p > 0
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    busy = s.getsockname()[1]
    s.listen()
    assert free_port(busy) != busy                    # port occupé : un autre est choisi
    s.close()


def test_close_is_immediate_when_idle():
    app = App(port=0)
    asked = []
    assert request_close(app, lambda t, m: asked.append(1) or True) is True and asked == []   # rien à confirmer
    app.httpd.server_close()


def test_close_asks_and_stops_the_running_job_cleanly():
    app = App(port=0)
    started = threading.Event()

    def work(rep, cancel):
        started.set()
        while True:
            rep.step("conversion", "x")
            time.sleep(0.01)
    job = app.logic.jobs.start("convert", 10, work)
    started.wait(5)
    assert request_close(app, lambda t, m: False) is False and job.state == "running"       # refus : la tâche continue
    assert request_close(app, lambda t, m: True) is True
    assert job.state == "stopped" and app.logic.jobs.current() is None                       # accepté : arrêt propre
    app.httpd.server_close()


def test_dropped_folder(tmp_path):
    from reable.app.window import dropped_folder
    (tmp_path / "Set.als").write_bytes(b"")
    (tmp_path / "note.txt").write_text("x")
    assert dropped_folder(str(tmp_path)) == {"path": str(tmp_path)}
    assert dropped_folder(str(tmp_path / "Set.als")) == {"path": str(tmp_path)}
    assert "error" in dropped_folder(str(tmp_path / "note.txt"))
    assert "error" in dropped_folder(None)


def test_dropped_path_finds_the_real_path_by_name(tmp_path):
    pytest.importorskip("webview")            # pywebview est facultatif (extra « app ») : absent du CI des tests
    from webview.dom import _dnd_state
    from reable.app.logic import AppLogic
    d = tmp_path / "Mes Projets"
    d.mkdir()
    _dnd_state["paths"][:] = [("Mes%20Projets", str(d) + "/")]
    r = AppLogic.dropped_path("Mes Projets")
    assert r["path"].rstrip("/") == str(d)
    assert "error" in AppLogic.dropped_path("Mes Projets")        # chemin consommé : un seul usage
