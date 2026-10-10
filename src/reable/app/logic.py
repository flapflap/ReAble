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

from .. import __version__, api, batch, i18n, registry, trace
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


class AppLogic:
    def __init__(self) -> None:
        self.jobs = JobManager()
        self.analysis: api.Analysis | None = None
        self.items: list[PlanItem] = []
        self.opts = self.load_options()
        self.last_written: list[str] = []
        self.ui_events: list[dict] = []          # messages de la fenêtre native vers la page (menu, dépôt) : la page les relève

    @staticmethod
    def dropped_path(name: str) -> dict:
        """Chemin réel de l'élément que la page vient de recevoir (elle ne connaît que son nom).
        La fenêtre native (pywebview, macOS) note les chemins déposés ; on retrouve celui qui porte ce nom."""
        try:
            from urllib.parse import unquote
            from webview.dom import _dnd_state
        except ImportError:
            return {"error": "Le glisser-déposer n'est disponible que dans la fenêtre ReAble. Utilisez « Choisir… »."}
        for item in list(_dnd_state["paths"]):
            if unquote(item[0]) == name:
                _dnd_state["paths"].remove(item)
                return dropped_folder(unquote(item[1]))
        return dropped_folder(None)

    # ---- messages de la fenêtre native
    def push_ui(self, event: dict) -> None:
        self.ui_events.append(event)
        del self.ui_events[:-20]

    def pop_ui(self) -> list[dict]:
        out, self.ui_events = self.ui_events, []
        return out

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
                "written": len(self.last_written), "version": __version__,
                "system": platform.mac_ver()[0] or platform.platform(),
                "lang": i18n.language(), "language": i18n.preference()}

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
            r = subprocess.run(["osascript", "-e", f'POSIX path of (choose folder with prompt "{i18n.tr("Dossier de projets Ableton Live")}")'],
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

    def missing_report(self) -> dict:
        """Rapport des plugins manquants du dossier analysé : pour chacun, les projets concernés et ce qu'il faut faire."""
        if self.analysis is None:
            return {"folder": None, "rows": []}
        by_item = {(i.set_path, i.plugin, i.source_format): i for i in self.items}
        rows: dict[tuple[str, str], dict] = {}
        for r in self.analysis.reports:
            for p in r.plugins:
                if p.install_status != "manquant":
                    continue
                row = rows.setdefault((p.name, p.format), {"plugin": p.name, "format": p.format, "vendor": p.manufacturer, "projects": set(),
                                                           "verdicts": set(), "kind": "unknown", "hint": ""})
                row["projects"].add(Path(r.path).stem)
                kind, text = self._verdict(by_item.get((r.path, p.name, p.format)), p)
                row["verdicts"].add((kind, text))
                if p.family_installed and not row["hint"]:
                    row["hint"] = "Déjà installé : " + ", ".join(p.family_installed[:3])
        out = []
        order = {"blocked": 0, "unknown": 1, "template": 2, "old": 3, "convert": 4, "done": 5}
        for row in rows.values():
            verdicts = sorted(row.pop("verdicts"), key=lambda v: order.get(v[0], 9))
            row["kind"], row["verdict"] = verdicts[0] if verdicts else ("unknown", "")
            if len({v[0] for v in verdicts}) > 1:
                row["verdict"] += f" ({len(verdicts)} situations selon les projets)"
            row["projects"] = sorted(row["projects"])
            row["count"] = len(row["projects"])
            out.append(row)
        out.sort(key=lambda x: (order.get(x["kind"], 9), -x["count"], x["plugin"].lower()))
        return {"folder": str(self.analysis.root), "rows": out}

    def replacement_candidates(self) -> list[dict]:
        """Plugins VST3 que l'utilisateur peut choisir comme remplaçants : ceux dont ReAble a un gabarit
        (projet Live 12 contenant le plugin en VST3), seuls utilisables tout de suite. Sans analyse en cours,
        on regarde la bibliothèque de gabarits que ReAble garde d'une analyse à l'autre."""
        templates = self.analysis.templates if self.analysis is not None else self._library_templates()
        out = {}
        for key, tpl in (templates or {}).items():
            out[key] = {"name": tpl[2] if len(tpl) > 2 and tpl[2] else key, "key": key}
        return sorted(out.values(), key=lambda c: c["name"].lower())

    _lib_cache: tuple = (None, {})

    def _library_templates(self) -> dict:
        from .. import templates as tpl_lib
        files = tpl_lib.library_files()
        sig = tuple((str(f), f.stat().st_mtime) for f in files if f.exists())
        if AppLogic._lib_cache[0] != sig:
            AppLogic._lib_cache = (sig, batch.build_template_index(files))
        return AppLogic._lib_cache[1]

    def set_replacement(self, plugin: str, target: str) -> dict:
        """Remplace (ou retire le remplacement) d'un plugin par un autre, pour toutes les analyses suivantes."""
        mapping = dict(self.opts.mapping)
        if target:
            if not any(c["name"] == target for c in self.replacement_candidates()):
                raise ValueError("plugin remplaçant inconnu : il doit exister en VST3 dans un projet analysé ou dans les gabarits")
            mapping[plugin] = target
        else:
            mapping.pop(plugin, None)
        if self.set_options({"mapping": mapping}):
            self.replan()
        return self.state()

    @staticmethod
    def _verdict(item, plugin) -> tuple[str, str]:
        d = registry.definition_of(plugin.name)
        if item is not None and item.status in ("convertible", "converti"):
            return "convert", f"Sera converti vers {item.target_name}"
        if item is not None and item.status == "ignoré":
            return "done", "Déjà converti : la copie existe"
        reason = (item.reason if item is not None else "") or ""
        if "trop ancien" in reason:
            return "old", "Projet à ouvrir et enregistrer dans Live 12, puis réanalyser"
        if reason.startswith("aucun gabarit"):
            return "template", "Il manque un projet Live 12 contenant ce plugin en VST3 (gabarit)"
        if d is None:
            return "unknown", "Plugin inconnu de ReAble : il n'est pas encore pris en charge"
        if d.status == "unsupported" or not d.adapter:
            return "blocked", "ReAble ne sait pas encore le convertir"
        if d.status == "experimental":
            return "blocked", "À tester dans l'onglet Plugins avant de pouvoir être converti"
        return "blocked", "Pas de version VST3 compatible installée sur ce Mac"

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
