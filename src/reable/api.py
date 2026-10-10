"""API unique du moteur : appelée par la ligne de commande et par l'interface.

    a = analyze("~/Music/MesProjets")           # scan + inventaire + gabarits
    items = propose(a, ConvertOptions())      # essai à blanc : ce qui est convertible, ce qui est bloqué (et pourquoi)
    result = convert(a, ConvertOptions(out_dir=...), items)   # écrit les nouveaux sets
    restore("set [ReAble].als")           # remet les plugins d'origine
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import alsfile, inventory, templates as tpl_lib, trace
from .batch import BatchResult, ConvertOptions, PlanItem, build_template_index, plan, run
from .extract import extract
from .jobs import CancelToken, Cancelled, Event, OnEvent, Reporter
from .model import SetReport

Progress = Callable[[str, int, int], None]   # (étape, fait, total)


@dataclass
class Analysis:
    root: Path
    files: list[Path]
    reports: list[SetReport]
    inventory: inventory.Inventory
    templates: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def analyze(target: str | Path, plugins_root: list[str] | None = None, include_packs: bool = False,
            progress: Progress | None = None, template_dirs: list[str] | None = None,
            on_event: OnEvent | None = None, cancel: CancelToken | None = None,
            remember_templates: bool = True) -> Analysis:
    target = Path(target).expanduser()
    if on_event:                                        # retour immédiat : la recherche des projets peut être longue
        on_event(Event("analyze", "running", "lecture", 0, 0, "", "", "Recherche des projets…"))
    files = [target] if target.is_file() else alsfile.find_sets(target, include_packs)
    inv = inventory.scan_installed([Path(p).expanduser() for p in plugins_root] if plugins_root else None)
    reports, errors = [], []
    rep = Reporter("analyze", len(files), on_event, cancel)
    for i, f in enumerate(files):
        rep.step("lecture", f.stem, str(f))
        if progress:
            progress("analyse", i, len(files))
        try:
            r = extract(f)
        except Exception as e:
            errors.append(f"{f} : illisible ({e})")
            rep.finish_item(f.stem, "erreur", str(e), key=str(f))
            continue
        inventory.check(r.plugins, inv)
        reports.append(r)
        rep.finish_item(f.stem, "lu", key=str(f))
    rep.step("lecture", "gabarits")
    if progress:
        progress("gabarits", 0, len(files))
    extra: list[Path] = []
    for d in template_dirs or []:
        d = Path(d).expanduser()
        extra += [d] if d.is_file() else alsfile.find_sets(d)
    rep.step("lecture", "gabarits")
    templates = build_template_index(files + extra + tpl_lib.library_files())
    if remember_templates:
        try:
            tpl_lib.remember(files + extra)          # alimente la bibliothèque pour les analyses suivantes (dossiers ajoutés compris)
        except OSError:
            pass
    rep.end(f"{len(reports)} projet(s) lu(s)")
    return Analysis(target if target.is_dir() else target.parent, files, reports, inv, templates, errors)


def propose(a: Analysis, opts: ConvertOptions, on_event: OnEvent | None = None,
            cancel: CancelToken | None = None) -> list[PlanItem]:
    """Essai à blanc : rien n'est écrit."""
    items = plan(a.reports, a.inventory, a.templates, opts)
    run(items, opts, dry_run=True, root_dir=a.root, on_event=on_event, cancel=cancel, task="plan")
    return items


def convert(a: Analysis, opts: ConvertOptions, items: list[PlanItem] | None = None,
            on_event: OnEvent | None = None, cancel: CancelToken | None = None) -> BatchResult:
    if items is None:
        items = plan(a.reports, a.inventory, a.templates, opts)
    before = {id(it): (it.status, it.reason) for it in items}
    for it in items:                       # repart d'un état propre avant l'exécution réelle
        if it.status in ("convertible", "converti"):
            it.status, it.reason = "à essayer", ""
    try:
        return run(items, opts, dry_run=False, root_dir=a.root, on_event=on_event, cancel=cancel, task="convert")
    except BaseException:                  # arrêt ou erreur : les éléments non traités redeviennent sélectionnables (« Reprendre »)
        for it in items:
            if it.status == "à essayer" and id(it) in before:
                it.status, it.reason = before[id(it)]
        raise


def restore(set_file: str | Path, out_dir: str | Path | None = None,
            original: str | Path | None = None) -> tuple[Path | None, trace.RestoreResult]:
    src = Path(set_file).expanduser()
    tree = alsfile.load(src)
    res = trace.restore_tree(tree, alsfile.load(Path(original).expanduser()) if original else None)
    if not res.restored:
        return None, res
    stem = src.stem + " [Restauré]"
    for mark in (" [ReAble", " [PlugRescue"):
        if mark in src.stem:
            stem = src.stem.replace(mark, " [Restauré")
            break
    dst = Path(out_dir or src.parent) / f"{stem}{src.suffix}"
    if dst.resolve() == src.resolve():
        raise ValueError("refus d'écraser le fichier source")
    dst.parent.mkdir(parents=True, exist_ok=True)
    alsfile.save(tree, dst, backup=False)
    return dst, res
