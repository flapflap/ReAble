"""Logique de l'application, indépendante de HTTP et de la fenêtre : état, groupes, tâches. Testable seule."""
from __future__ import annotations

import dataclasses
import json
import platform
import shutil
import subprocess
import time
from collections import OrderedDict
from pathlib import Path

from .. import api, batch, registry, short_version, trace
from ..batch import ConvertOptions, PlanItem
from ..jobs import JobBusy, JobManager

KIND_ORDER = ["validated", "default", "template", "old", "unsupported", "done"]


def group_items(items: list[PlanItem]) -> list[dict]:
    """Regroupe le plan par conversion (ce que l'utilisateur comprend), pas par set."""
    groups: "OrderedDict[tuple, dict]" = OrderedDict()
    for it in items:
        if it.status in ("convertible", "converti"):
            kind = "default" if "n'est pas repris" in (it.reason or "") else "validated"
            key = (kind, it.plugin, "", it.target_name)       # un groupe = une conversion, quel que soit le format d'origine
            title = f"{it.plugin} → {it.target_name}"
        elif it.status == "ignoré":
            key, kind, title = ("done", "", "", ""), "done", "Déjà convertis"
        elif "trop ancien" in (it.reason or ""):
            key, kind, title = ("old", "", "", ""), "old", "Projets trop anciens"
        elif (it.reason or "").startswith("aucun gabarit"):
            key, kind, title = ("template", it.target_name, "", ""), "template", f"Gabarit manquant : {it.target_name}"
        else:
            key, kind, title = ("unsupported", "", "", ""), "unsupported", "Plugins sans équivalent"
        g = groups.setdefault(key, {"id": "|".join(key), "kind": kind, "title": title, "sets": set(), "instances": 0,
                                    "plugins": set(), "targets": set(), "selectable": kind in ("validated", "default")})
        if it.target_name:
            g["targets"].add(it.target_name)
        g["sets"].add(it.set_path)
        g["instances"] += max(it.instances, 1)
        g["plugins"].add(it.plugin)
    out = []
    for g in groups.values():
        out.append({**g, "sets": sorted(g["sets"]), "count": len(g["sets"]), "plugins": sorted(g["plugins"]),
                    "targets": sorted(g["targets"])})
    out.sort(key=lambda g: (KIND_ORDER.index(g["kind"]), -g["count"], g["title"]))
    return out


def summarize(groups: list[dict]) -> dict:
    by = lambda k: [g for g in groups if g["kind"] == k]
    conv = by("validated") + by("default")
    return {
        "to_convert": len({s for g in conv for s in g["sets"]}),
        "default_settings": len({s for g in by("default") for s in g["sets"]}),
        "too_old": len({s for g in by("old") for s in g["sets"]}),
        "template_missing": len({s for g in by("template") for s in g["sets"]}),
        "templates_needed": sorted({t for g in by("template") for t in g["targets"]}),
        "unsupported_plugins": len({p for g in by("unsupported") for p in g["plugins"]}),
        "already_done": len({s for g in by("done") for s in g["sets"]}),
    }


class AppLogic:
    def __init__(self) -> None:
        self.jobs = JobManager()
        self.analysis: api.Analysis | None = None
        self.items: list[PlanItem] = []
        self.opts = self.load_options()
        self.last_written: list[str] = []

    # ---- réglages
    @staticmethod
    def _options_file() -> Path:
        return registry.user_dir() / "options.json"

    def load_options(self) -> ConvertOptions:
        try:
            return ConvertOptions.from_dict(json.loads(self._options_file().read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return ConvertOptions(replace_mode="duplicate_track")      # défaut de l'application : l'originale est gardée

    PLAN_KEYS = {"only_missing", "families", "mapping", "skip_plugins", "if_exists", "state_mode"}

    def set_options(self, data: dict) -> bool:
        """Enregistre les réglages ; renvoie True si le plan doit être recalculé (réglages qui changent les groupes)."""
        before = self.opts.to_dict()
        merged = {**self.opts.to_dict(), **{k: v for k, v in data.items() if k in ConvertOptions.__dataclass_fields__}}
        merged["out_dir"] = merged.get("out_dir") or None
        self.opts = ConvertOptions.from_dict(merged)
        self._options_file().parent.mkdir(parents=True, exist_ok=True)
        self._options_file().write_text(json.dumps(self.opts.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        after = self.opts.to_dict()
        return any(before.get(k) != after.get(k) for k in self.PLAN_KEYS)

    # ---- état
    def state(self) -> dict:
        cur = self.jobs.current()
        groups = group_items(self.items) if self.items else []
        return {"folder": str(self.analysis.root) if self.analysis else None,
                "analyzed": self.analysis is not None,
                "sets": len(self.analysis.reports) if self.analysis else 0,
                "unreadable": len(self.analysis.errors) if self.analysis else 0,
                "groups": groups, "summary": summarize(groups) if groups else None,
                "definitions": len(registry.load_all()),
                "options": self.opts.to_dict(), "job": cur.snapshot() if cur else None,
                "written": len(self.last_written), "version": short_version(),
                "system": platform.mac_ver()[0] or platform.platform()}

    # ---- tâches
    def analyze(self, path: str, template_dirs: list[str] | None = None):
        template_dirs = [str(Path(d).expanduser()) for d in (template_dirs or []) if d]
        p = Path(path).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"« {path} » n'est pas accessible")

        def work(rep, cancel):
            a = api.analyze(p, on_event=rep.on_event, cancel=cancel, template_dirs=template_dirs)
            self.analysis = a
            self.items = api.propose(a, self.opts, on_event=rep.on_event, cancel=cancel)   # 2e étape, avec sa propre progression
            return {"sets": len(a.reports)}
        self.items, self.analysis = [], None
        self.last_written = []                            # nouvelle analyse : on repart de zéro
        return self.jobs.start("analyze", 0, work)       # total inconnu : il est annoncé par le premier événement

    def replan(self) -> None:
        if self.analysis is not None:
            self.items = api.propose(self.analysis, self.opts)

    def _selected_items(self, group_ids: list[str] | None) -> list[PlanItem]:
        """Éléments du plan appartenant aux groupes cochés (seuls les groupes convertibles sont sélectionnables)."""
        if group_ids is None:
            return [i for i in self.items if i.status in ("convertible", "converti")]
        wanted = set(group_ids)
        sel = []
        for it in self.items:
            if it.status not in ("convertible", "converti"):
                continue
            kind = "default" if "n'est pas repris" in (it.reason or "") else "validated"
            if "|".join((kind, it.plugin, "", it.target_name)) in wanted:
                sel.append(it)
        return sel

    def convert(self, group_ids: list[str] | None, dry_run: bool = False):
        if self.analysis is None:
            raise RuntimeError("aucune analyse : choisissez d'abord un dossier")
        items = self._selected_items(group_ids)
        if not items:
            raise RuntimeError("rien à convertir dans la sélection")
        total = len({i.set_path for i in items})
        a, opts = self.analysis, self.opts

        def work(rep, cancel):
            if dry_run:
                api.propose(a, opts, on_event=rep.on_event, cancel=cancel)
                return {"written": []}
            def track(e):                                   # mémorise chaque copie écrite, même si la tâche est arrêtée ;
                if e.path and e.path not in self.last_written:   # la liste s'accumule d'une reprise à l'autre (annulation complète)
                    self.last_written.append(e.path)
                rep.on_event(e)
            res = api.convert(a, opts, items, on_event=track, cancel=cancel)
            return {"written": res.written, "counts": _counts(res.items)}
        return self.jobs.start("plan" if dry_run else "convert", total, work)

    def restore(self, files: list[str]):
        def work(rep, cancel):
            done, failed = [], []
            for f in files:
                rep.step("lecture", Path(f).stem)
                try:
                    dst, r = api.restore(f)
                    (done if dst else failed).append(str(dst or f))
                except Exception as e:                     # noqa: BLE001
                    failed.append(f"{f} : {e}")
                rep.finish_item(Path(f).stem, "restauré" if dst else "erreur")
            rep.end(f"{len(done)} restauré(s)")
            return {"restored": done, "failed": failed}
        return self.jobs.start("restore", len(files), work)

    def undo(self, files: list[str] | None = None) -> dict:
        """Met à la corbeille les copies [ReAble] écrites (réversible). Refuse tout fichier qui n'en est pas une."""
        files = files if files is not None else list(self.last_written)
        trash = Path.home() / ".Trash"
        moved, refused = [], []
        for f in files:
            p = Path(f)
            try:
                ok = p.is_file() and (" [ReAble" in p.name or " [PlugRescue" in p.name) and p.suffix == ".als" and _has_trace(p)
            except Exception:                              # noqa: BLE001
                ok = False
            if not ok:
                refused.append(str(p))
                continue
            dst = trash / p.name
            if dst.exists():
                dst = trash / f"{p.stem} {int(time.time())}{p.suffix}"
            shutil.move(str(p), str(dst))
            moved.append(str(p))
        self.last_written = [f for f in self.last_written if f not in moved]
        return {"moved": moved, "refused": refused}

    # ---- divers
    @staticmethod
    def reveal(path: str) -> bool:
        p = Path(path).expanduser()
        if not p.exists():
            return False
        subprocess.run(["open", "-R", str(p)], check=False)
        return True

    @staticmethod
    def choose_folder() -> str | None:
        try:
            r = subprocess.run(["osascript", "-e", 'POSIX path of (choose folder with prompt "Dossier de projets Ableton Live")'],
                               capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout.strip().rstrip("/") or None if r.returncode == 0 else None

    @staticmethod
    def plugins() -> list[dict]:
        return [{**d.to_dict(), "source": d.source, "name": d.display_name()} for d in registry.load_all()]

    REPO_URL = "https://github.com/flapflap/ReAble"

    @classmethod
    def open_url(cls, url: str) -> bool:
        """Ouvre une page du dépôt ReAble dans le navigateur. Rien d'autre : un autre site est refusé."""
        if not (url == cls.REPO_URL or url.startswith(cls.REPO_URL + "/")):
            raise ValueError("adresse refusée : seules les pages du projet ReAble s'ouvrent depuis l'application")
        subprocess.run(["open", url], check=False)
        return True

    # ---- validation d'un plugin (essai dans Live)
    def plugin_test(self, def_id: str) -> dict:
        """Écrit UNE copie de test d'un projet analysé qui utilise ce plugin (même s'il n'est pas encore validé)."""
        d = next((x for x in registry.load_all() if x.id == def_id), None)
        if d is None:
            raise KeyError(f"plugin inconnu : {def_id}")
        if not d.adapter:
            raise RuntimeError("ReAble ne sait pas encore convertir ce plugin : il n'y a rien à tester.")
        a = self.analysis
        if a is None:
            raise RuntimeError("Analysez d'abord un dossier qui contient un projet utilisant ce plugin.")
        opts = dataclasses.replace(self.opts, families=frozenset(self.opts.families) | {def_id},
                                   out_dir=registry.user_dir() / "tests" / def_id, if_exists="overwrite")
        reasons = []
        for r in sorted(a.reports, key=lambda r: Path(r.path).stat().st_size if Path(r.path).exists() else 0):
            items = [i for i in batch.plan([r], a.inventory, a.templates, opts) if registry.family_of(i.plugin) == def_id]
            ok = [i for i in items if i.status != "bloqué"]
            reasons += [i.reason for i in items if i.status == "bloqué" and i.reason]
            if not ok:
                continue
            res = batch.run(ok, opts, dry_run=False, root_dir=a.root)
            if res.written:
                return {"path": res.written[0], "project": Path(r.path).stem, "plugin": ok[0].plugin, "target": ok[0].target_name}
            reasons += res.errors
        if reasons:
            raise RuntimeError("Aucune copie de test possible : " + reasons[0])
        raise RuntimeError("Aucun projet analysé n'utilise ce plugin (ou il est installé tel quel). Analysez un dossier qui le contient.")

    def plugin_validate(self, def_id: str, result: str, note: str = "") -> dict:
        d = registry.record_validation(def_id, result, note=str(note)[:500])
        self.replan()
        return {**d.to_dict(), "source": d.source, "name": d.display_name()}

    # ---- programme bêta
    @staticmethod
    def beta_state() -> dict:
        cfg = registry.settings().get("beta", {})
        return {"enabled": bool(cfg.get("enabled")), "has_results": any(i.get("validated") for i in registry._read_user())}

    @staticmethod
    def set_beta(enabled: bool) -> dict:
        registry.set_beta(bool(enabled))
        return AppLogic.beta_state()

    @staticmethod
    def export_beta() -> str:
        dst = Path.home() / "Desktop" / "ReAble-resultats-beta.json"
        dst.write_text(json.dumps(registry.export_bundle(beta=True), ensure_ascii=False, indent=1), encoding="utf-8")
        return str(dst)

    def old_sets_list(self) -> list[str]:
        return sorted({s for g in group_items(self.items) if g["kind"] == "old" for s in g["sets"]})


def _has_trace(p: Path) -> bool:
    """Le fichier porte-t-il une note ReAble ? (garde-fou : on ne met à la corbeille que nos propres copies)"""
    from .. import alsfile
    root = alsfile.load(p).getroot()
    return any(trace.parse_note(d.find("Annotation").get("Value", "")) for d in root.iter("PluginDevice")
               if d.find("Annotation") is not None)


def _counts(items: list[PlanItem]) -> dict:
    """Compte par projet (pas par conversion de plugin) : « 7 projets » ne doit pas devenir « 8 convertis »."""
    per_set: dict[str, str] = {}
    for it in items:
        if it.status == "converti":
            kind = "default" if "n'est pas repris" in (it.reason or "") else "converted"
            if per_set.get(it.set_path) != "converted":        # un projet avec au moins une conversion complète compte « converti »
                per_set[it.set_path] = kind if it.set_path not in per_set or kind == "converted" else per_set[it.set_path]
        elif it.status == "ignoré":
            per_set.setdefault(it.set_path, "skipped")
    c = {"converted": 0, "default": 0, "skipped": 0, "errors": 0}
    for kind in per_set.values():
        c[kind] += 1
    return c
