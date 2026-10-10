"""Serveur local : API JSON + interface statique. Écoute sur 127.0.0.1 uniquement.

Sécurité (le serveur tourne sur le Mac de l'utilisateur et peut écrire des fichiers) :
- jeton aléatoire par lancement, exigé dans l'en-tête `X-ReAble-Token` pour toute l'API ;
- en-tête Host vérifié (127.0.0.1 / localhost) contre le « DNS rebinding » ;
- en-tête Origin, s'il existe, doit être celui du serveur (refuse les appels depuis un site web) ;
- aucune permission CORS.
"""
from __future__ import annotations

import json
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import i18n
from ..jobs import JobBusy
from .logic import AppLogic

STATIC = Path(__file__).parent / "static"
MAX_BODY = 1_000_000


class App:
    """Un serveur lié à une logique et à un jeton."""

    def __init__(self, host: str = "127.0.0.1", port: int = 3000, logic: AppLogic | None = None) -> None:
        self.logic = logic or AppLogic()
        self.token = secrets.token_urlsafe(24)
        self.httpd = ThreadingHTTPServer((host, port), self._handler())
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> None:
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="reable-http", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        app = self

        class H(BaseHTTPRequestHandler):
            server_version = "ReAble"

            def log_message(self, *a):          # pas de bruit dans le terminal
                pass

            # --- utilitaires
            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").split(":")[0]
                return host in ("127.0.0.1", "localhost")

            def _origin_ok(self) -> bool:
                o = self.headers.get("Origin")
                return o is None or o in (f"http://127.0.0.1:{app.port}", f"http://localhost:{app.port}")

            def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, data) -> None:
                self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

            def _err(self, code: int, msg: str) -> None:
                self._json(code, {"error": msg})

            def _body(self) -> dict:
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    raise ValueError("requête trop grande")
                raw = self.rfile.read(n) if n else b"{}"
                return json.loads(raw or b"{}")

            # --- routage
            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def _route(self, method: str) -> None:
                if not self._host_ok() or not self._origin_ok():
                    return self._err(403, "origine refusée")
                u = urlparse(self.path)
                if not u.path.startswith("/api/"):
                    return self._static(u.path) if method == "GET" else self._err(405, "méthode refusée")
                if self.headers.get("X-ReAble-Token") != app.token:
                    return self._err(401, "jeton invalide")
                try:
                    self._api(method, u.path, parse_qs(u.query))
                except JobBusy as e:
                    self._err(409, str(e))
                except (FileNotFoundError, RuntimeError, ValueError, KeyError) as e:
                    self._err(400, str(e))
                except Exception as e:              # noqa: BLE001
                    self._err(500, f"{type(e).__name__}: {e}")

            def _static(self, path: str) -> None:
                name = "index.html" if path in ("", "/") else path.lstrip("/")
                f = (STATIC / name).resolve()
                if STATIC.resolve() not in f.parents and f != STATIC.resolve() or not f.is_file():
                    return self._err(404, "introuvable")
                body = f.read_bytes()
                if f.name == "index.html":
                    body = body.replace(b"__TOKEN__", app.token.encode())
                ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                self._send(200, body, ctype + ("; charset=utf-8" if ctype.startswith("text/") or "javascript" in ctype else ""))

            def _api(self, method: str, path: str, q: dict) -> None:
                L = app.logic
                if method == "GET" and path == "/api/state":
                    return self._json(200, L.state())
                if method == "GET" and path == "/api/plugins":
                    return self._json(200, L.plugins())
                if method == "GET" and path == "/api/replacement-candidates":
                    return self._json(200, {"candidates": L.replacement_candidates()})
                if method == "GET" and path == "/api/missing-report":
                    return self._json(200, L.missing_report())
                if method == "GET" and path == "/api/ui-events":
                    return self._json(200, {"events": L.pop_ui()})
                if method == "GET" and path == "/api/beta":
                    return self._json(200, L.beta_state())
                if method == "GET" and path == "/api/old-sets":
                    return self._json(200, {"sets": L.old_sets_list()})
                if method == "GET" and path.startswith("/api/jobs/"):
                    j = L.jobs.get(path.rsplit("/", 1)[-1])
                    if j is None:
                        return self._err(404, "tâche inconnue")
                    return self._json(200, j.snapshot(int((q.get("since") or ["0"])[0])))
                if method != "POST":
                    return self._err(404, "route inconnue")
                body = self._body()
                if path == "/api/choose-folder":
                    return self._json(200, {"path": L.choose_folder()})
                if path == "/api/analyze":
                    return self._json(202, {"job": L.analyze(str(body.get("path", "")), body.get("template_dirs")).id})
                if path == "/api/options":
                    if L.set_options(body):
                        L.replan()
                    return self._json(200, L.state())
                if path == "/api/undo":
                    return self._json(200, L.undo(body.get("files")))
                if path == "/api/convert":
                    return self._json(202, {"job": L.convert(body.get("groups"), bool(body.get("dry_run"))).id})
                if path == "/api/restore":
                    return self._json(202, {"job": L.restore([str(f) for f in body.get("files", [])]).id})
                if path.startswith("/api/jobs/") and path.endswith("/stop"):
                    return self._json(200, {"stopping": L.jobs.stop(path.split("/")[3])})
                if path == "/api/plugins/test":
                    return self._json(200, L.plugin_test(str(body.get("id", ""))))
                if path == "/api/plugins/validate":
                    return self._json(200, L.plugin_validate(str(body.get("id", "")), str(body.get("result", "")), str(body.get("note", ""))))
                if path == "/api/beta":
                    return self._json(200, L.set_beta(bool(body.get("enabled"))))
                if path == "/api/beta/export":
                    return self._json(200, {"path": L.export_beta()})
                if path == "/api/language":
                    i18n.set_preference(str(body.get("language", "")))
                    return self._json(200, L.state())
                if path == "/api/replacement":
                    return self._json(200, L.set_replacement(str(body.get("plugin", "")), str(body.get("target", ""))))
                if path == "/api/dropped-path":
                    return self._json(200, L.dropped_path(str(body.get("name", ""))))
                if path == "/api/open-url":
                    return self._json(200, {"ok": L.open_url(str(body.get("url", "")))})
                if path == "/api/reveal":
                    return self._json(200, {"ok": L.reveal(str(body.get("path", "")))})
                return self._err(404, "route inconnue")

        return H


def main(port: int = 3000, open_browser: bool = False) -> int:
    app = App(port=port)
    app.start()
    print(f"ReAble : {app.url}")
    if open_browser:
        import webbrowser
        webbrowser.open(app.url)
    try:
        app.thread.join()
    except KeyboardInterrupt:
        app.stop()
    return 0
