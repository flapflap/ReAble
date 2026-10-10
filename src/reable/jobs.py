"""Tâches longues : événements de progression et arrêt coopératif.

Le moteur reste synchrone. Une tâche reçoit (1) un `CancelToken` qu'elle consulte entre ses phases et (2) un
rappel `on_event` appelé à chaque pas ; l'interface s'en sert pour le suivi et le bouton « Arrêter ».
"""
from __future__ import annotations

import threading
import traceback
import uuid
import time
from dataclasses import asdict, dataclass
from typing import Callable

PHASES = ("lecture", "conversion", "contrôle", "écriture")


class Cancelled(Exception):
    """La tâche a été arrêtée par l'utilisateur. Aucun fichier partiel ne doit subsister."""


class CancelToken:
    """Drapeau d'arrêt partagé entre l'interface et le moteur (sûr entre threads)."""

    def __init__(self) -> None:
        self._ev = threading.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()

    def check(self) -> None:
        if self._ev.is_set():
            raise Cancelled()


@dataclass
class Event:
    task: str                 # analyze | plan | convert | restore
    status: str               # running | done
    phase: str = ""           # lecture | conversion | contrôle | écriture | ""
    index: int = 0            # éléments terminés
    total: int = 0
    item: str = ""            # nom de l'élément en cours
    result: str = ""          # converti | réglages par défaut | ignoré | erreur | ""
    message: str = ""
    path: str = ""            # fichier écrit (copie [ReAble]) pour cet élément, s'il y en a un
    elapsed: float = 0.0
    eta: float | None = None  # secondes restantes estimées

    def to_dict(self) -> dict:
        return asdict(self)


OnEvent = Callable[[Event], None]


class Reporter:
    """Fabrique les événements d'une tâche : temps écoulé, estimation du reste (moyenne par élément terminé)."""

    def __init__(self, task: str, total: int, on_event: OnEvent | None, cancel: CancelToken | None) -> None:
        self.task, self.total, self.on_event, self.cancel = task, total, on_event, cancel
        self.t0 = time.monotonic()
        self.done = 0

    def check(self) -> None:
        if self.cancel is not None:
            self.cancel.check()

    def emit(self, status: str = "running", phase: str = "", item: str = "", result: str = "", message: str = "",
             path: str = "") -> None:
        if self.on_event is None:
            return
        elapsed = time.monotonic() - self.t0
        eta = (elapsed / self.done) * (self.total - self.done) if self.done else None
        self.on_event(Event(self.task, status, phase, self.done, self.total, item, result, message, path, elapsed, eta))

    def step(self, phase: str, item: str) -> None:
        """Vérifie l'arrêt puis annonce la phase : point de contrôle de l'arrêt coopératif."""
        self.check()
        self.emit(phase=phase, item=item)

    def finish_item(self, item: str, result: str = "", message: str = "", path: str = "") -> None:
        self.done += 1
        self.emit(item=item, result=result, message=message, path=path)

    def end(self, message: str = "") -> None:
        self.emit(status="done", message=message)


class JobBusy(Exception):
    """Une tâche est déjà en cours : une seule à la fois."""


class Job:
    """Une exécution suivie : état, événements, résultat. `state` : running | stopping | done | stopped | error."""

    def __init__(self, kind: str, total: int) -> None:
        self.id = uuid.uuid4().hex[:10]
        self.kind, self.total = kind, total
        self.state = "running"
        self.events: list[Event] = []
        self.result: object = None
        self.error: str | None = None
        self.cancel = CancelToken()
        self.started = time.time()
        self._lock = threading.Lock()
        self.thread: threading.Thread | None = None

    def on_event(self, e: Event) -> None:
        with self._lock:
            self.events.append(e)
            if len(self.events) > 5000:            # le journal ne grossit pas sans limite
                del self.events[:1000]

    def snapshot(self, since: int = 0) -> dict:
        with self._lock:
            ev = self.events[since:]
            last = self.events[-1].to_dict() if self.events else None
            return {"id": self.id, "kind": self.kind, "state": self.state, "error": self.error,
                    "total_events": len(self.events), "events": [e.to_dict() for e in ev], "last": last,
                    "result": self.result if isinstance(self.result, (dict, list)) else None}


class JobManager:
    """Lance les tâches longues dans un thread, une à la fois, avec arrêt coopératif."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def current(self) -> Job | None:
        with self._lock:
            return next((j for j in self._jobs.values() if j.state in ("running", "stopping")), None)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start(self, kind: str, total: int, fn) -> Job:
        """`fn(reporter, cancel)` fait le travail ; il appelle reporter.step / finish_item / end."""
        with self._lock:
            if any(j.state in ("running", "stopping") for j in self._jobs.values()):
                raise JobBusy("une tâche est déjà en cours")
            job = Job(kind, total)
            self._jobs[job.id] = job
            if len(self._jobs) > 20:
                for k in [k for k, v in self._jobs.items() if v.state not in ("running", "stopping")][:-10]:
                    self._jobs.pop(k, None)

        def runner() -> None:
            rep = Reporter(kind, total, job.on_event, job.cancel)
            try:
                job.result = fn(rep, job.cancel)
                job.state = "done"
            except Cancelled:
                job.state = "stopped"
            except Exception as e:                  # noqa: BLE001 - la tâche ne doit jamais faire tomber l'application
                job.error = f"{type(e).__name__}: {e}"
                job.state = "error"
                job.on_event(Event(kind, "error", message=job.error))
                job.error_trace = traceback.format_exc()      # type: ignore[attr-defined]
        job.thread = threading.Thread(target=runner, name=f"job-{job.id}", daemon=True)
        job.thread.start()
        return job

    def stop(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None or job.state != "running":
            return False
        job.state = "stopping"
        job.cancel.cancel()
        return True
