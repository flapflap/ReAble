"""Conversion en lot : planification (essai à blanc) et exécution sur un dossier de sets."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import alsfile, trace
from .adapters import state_note
from . import i18n
from .registry import allowed_families, definition_of, family_of
from .inventory import Inventory
from .jobs import CancelToken, OnEvent, Reporter
from .model import Plugin, SetReport
from .rewrite import check_tree, rewrite_tree

SOURCE_FORMATS = ("AU", "VST2", "VST3")   # VST3 seulement pour une mise à niveau vers un autre nom


@dataclass
class ConvertOptions:
    """Tous les choix de workflow. Sérialisable en JSON : c'est le « profil » de l'interface."""
    # portée
    only_missing: bool = True                 # ne convertir que ce qui n'est pas installé dans son format
    families: frozenset = field(default_factory=allowed_families)   # familles autorisées (validées + choix de l'utilisateur)
    mapping: dict = field(default_factory=dict)       # {"Kontakt 5": "Kontakt 8"} : cible imposée
    skip_plugins: list = field(default_factory=list)  # noms de plugins à ne jamais convertir
    # remplacement
    replace_mode: str = "replace"             # replace | duplicate_track | keep_device (effets seulement)
    mute_original: bool = True                # duplicate_track : l'originale est mutée
    original_suffix: str = " [original]"      # duplicate_track : suffixe du nom de l'originale
    state_mode: str = "transfer"              # transfer | header | none (voir adapters.py)
    copy_controller_state: bool = False       # écrire aussi l'état dans ControllerState (iZotope VST3 d'avant Ozone 10)
    # nom
    rename_target: str = "track"              # track | device | none
    rename_template: str = "{track} [{from}→{to}]"   # variables : track plugin from to preset date
    missing_preset: str = "omit"              # omit | plugin | question
    track_info: bool = True                   # texte d'info de la piste (bas à gauche dans Live)
    track_info_template: str = ("Converti par ReAble le {date}\n{plugin} : {from} → {to}\n"
                                "Preset d'origine : {preset}\n{state_note}\nPiste d'origine : {original_track}")
    # traçabilité
    write_note: bool = True                   # note ReAble dans l'Annotation du device
    embed_original: bool = True               # embarquer l'original dans la note (pour `restore`)
    max_embed_kb: int = 100                   # au-delà, restauration via le set d'origine
    # sortie
    out_dir: Path | None = None               # défaut : à côté du set
    suffix: str = ""
    if_exists: str = "skip"                   # skip (ne pas refaire) | overwrite (sauvegarde horodatée) | number (… 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["families"] = sorted(self.families)
        d["out_dir"] = str(self.out_dir) if self.out_dir else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ConvertOptions":
        known = {f for f in cls.__dataclass_fields__}
        kw = {k: v for k, v in d.items() if k in known}
        if "families" in kw:
            kw["families"] = frozenset(kw["families"])
        if kw.get("out_dir"):
            kw["out_dir"] = Path(kw["out_dir"]).expanduser()
        return cls(**kw)


def load_profile(path: str | Path) -> ConvertOptions:
    return ConvertOptions.from_dict(json.loads(Path(path).expanduser().read_text(encoding="utf-8")))


def save_profile(opts: ConvertOptions, path: str | Path) -> None:
    Path(path).expanduser().write_text(json.dumps(opts.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")


@dataclass
class PlanItem:
    set_path: str
    plugin: str
    source_format: str
    target_name: str = ""
    instances: int = 0
    template: str = ""
    status: str = "à essayer"                 # à essayer | convertible | converti | bloqué
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BatchResult:
    items: list[PlanItem] = field(default_factory=list)
    written: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"items": [i.to_dict() for i in self.items], "written": self.written, "errors": self.errors}


def _live_version(s: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3])


def build_template_index(files: list[Path]) -> dict[str, tuple[str, tuple, str]]:
    """nom VST3 (minuscules) -> (chemin du set, version de Live, nom exact) ; le set le plus récent gagne."""
    idx: dict[str, tuple[str, tuple, str]] = {}
    for f in files:
        try:
            root = alsfile.load(f).getroot()
        except Exception:
            continue
        ver = _live_version(root.get("Creator", ""))
        for info in root.iter("Vst3PluginInfo"):
            n = info.find("Name")
            if n is None or not n.get("Value"):
                continue
            key = n.get("Value").lower()
            if key not in idx or ver > idx[key][1]:
                idx[key] = (str(f), ver, n.get("Value"))
    return idx


def _natural(name: str) -> tuple:
    return tuple(int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name))


def mapped_target(name: str, mapping: dict) -> str | None:
    """Remplaçant choisi par l'utilisateur pour ce plugin : par nom exact (sans tenir compte des majuscules),
    ou pour toute la famille quand la clé est le nom d'une définition (« Play » vaut pour toutes les versions)."""
    low = name.lower()
    for k, v in mapping.items():
        if k.lower() == low:
            return str(v)
    d = definition_of(name)
    if d is not None:
        for k, v in mapping.items():
            if k.lower() in (d.id.lower(), d.display_name().lower()):
                return str(v)
    return None


def pick_target(p: Plugin, inv: Inventory, opts: ConvertOptions, templates: dict | None = None) -> str | None:
    """Nom du plugin VST3 cible : le même nom s'il est installé, sinon la version la plus récente de la
    famille. Si `templates` est donné, on ne garde que les cibles pour lesquelles un gabarit existe."""
    chosen = mapped_target(p.name, opts.mapping)
    if chosen:
        return chosen.lower()
    fam = family_of(p.name)
    if fam not in opts.families:
        return None
    cands = []
    norm = p.name.lower().replace("_", " ")
    if norm in inv.vst3_names:
        cands.append(norm)
    cands += sorted((n for n in inv.vst3_names if family_of(n) == fam and n != norm), key=_natural, reverse=True)
    if templates is not None:
        usable = [c for c in cands if c in templates]
        cands = usable or cands
    return cands[0] if cands else None


def schema_ok(root) -> bool:
    return next(root.iter("NextPointeeId"), None) is not None and root.find(".//Pointee") is not None


def plan(reports: list[SetReport], inv: Inventory, templates: dict, opts: ConvertOptions) -> list[PlanItem]:
    items = []
    for r in reports:
        seen: dict[tuple[str, str], PlanItem] = {}
        for p in r.plugins:
            if p.format not in SOURCE_FORMATS:
                continue
            if opts.only_missing and p.install_status == "installé":
                continue
            if p.format == "VST3":      # seulement une mise à niveau vers un autre nom (ex. Ozone 8 → Ozone 10)
                t = pick_target(p, inv, opts, templates)
                if t is None or t.lower() == p.name.lower():
                    continue
            key = (p.name, p.format)
            if key in seen:
                seen[key].instances += 1
                continue
            it = PlanItem(r.path, p.name, p.format, instances=1)
            seen[key] = it
            if p.name in opts.skip_plugins:
                it.status, it.reason = "bloqué", "ignoré (réglages)"
                continue
            target = pick_target(p, inv, opts, templates)
            if target is None:
                it.status, it.reason = "bloqué", "pas de plugin VST3 compatible installé (famille non gérée ou absente)"
            else:
                tpl = templates.get(target.lower())
                it.target_name = tpl[2] if tpl else target
                if tpl is None:
                    it.status, it.reason = "bloqué", f"aucun gabarit VST3 « {target} » dans les sets analysés"
                else:
                    it.template = tpl[0]
        items += list(seen.values())
    return items


def render_name(template: str, values: dict) -> str:
    """Remplit le modèle ; retire crochets vides et séparateurs orphelins quand une variable est vide."""
    out = re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), "")), template)
    out = re.sub(r"\[\s*\]|\(\s*\)", "", out)
    out = re.sub(r"\s+[—\-:]\s*$", "", out)
    out = re.sub(r"^\s*[—\-:]\s+", "", out)
    return re.sub(r"\s{2,}", " ", out).strip()


def apply_rename(root, opts: ConvertOptions) -> int:
    """Renomme la piste (ou le device) de chaque device converti, selon le modèle des réglages."""
    if opts.rename_target == "none" or not opts.rename_template:
        return 0
    parents = {c: p for p in root.iter() for c in p}
    n = 0
    for dev in [d for d in root.iter("PluginDevice")]:
        ann = dev.find("Annotation")
        info = trace.parse_note(ann.get("Value", "")) if ann is not None else None
        if not info:
            continue
        if opts.rename_target == "device":
            holders = [dev]
        else:
            h = dev
            while h is not None and not h.tag.endswith("Track"):
                h = parents.get(h)
            if h is not None and h.tag in ("MainTrack", "MasterTrack"):
                h = dev                # le nom de la piste principale n'est pas modifiable : on renomme le device
            holders = [h] if h is not None else []
        for h in holders:
            paths = ("UserName",) if h is dev else ("Name/UserName", "Name/EffectiveName")
            cur = h.find(paths[0])
            current = cur.get("Value", "") if cur is not None else ""
            if not current and h is not dev:
                eff = h.find("Name/EffectiveName")
                current = eff.get("Value", "") if eff is not None else ""
            if not current and h is dev:
                current = info.get("target_name", "")
            preset = info.get("preset", "")
            if not preset:
                preset = {"plugin": info.get("target_name", ""), "question": "?"}.get(opts.missing_preset, "")
            name = render_name(opts.rename_template, {
                "track": current, "plugin": info.get("target_name", ""), "from": info.get("source_format", ""),
                "to": "VST3", "preset": preset, "date": info.get("when", "")[:10]})
            if not name or name == current:
                continue
            for pth in paths:
                el = h.find(pth)
                if el is not None:
                    el.set("Value", name)
            if h is not dev:
                info["track_name_before"] = current
                ann.set("Value", trace.build_note(trace.strip_note(ann.get("Value", "")), info))
            n += 1
    return n


def render_lines(template: str, values: dict) -> str:
    """Remplit un modèle multi-lignes ; une ligne dont une variable est vide est omise."""
    out = []
    for line in template.split("\n"):
        keys = re.findall(r"\{(\w+)\}", line)
        if keys and any(not str(values.get(k, "")) for k in keys):
            continue
        out.append(re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), "")), line))
    return "\n".join(out).strip()


def _track_name_of(trk) -> str:
    for path in ("Name/UserName", "Name/EffectiveName"):
        el = trk.find(path)
        if el is not None and el.get("Value"):
            return el.get("Value")
    return ""


def apply_track_info(root, opts: ConvertOptions) -> int:
    """Écrit le texte d'info des pistes converties ; avec duplicate_track, une phrase sur l'originale aussi."""
    if not opts.track_info:
        return 0
    parents = {c: p for p in root.iter() for c in p}
    by_id = {t.get("Id"): t for tag in ("MidiTrack", "AudioTrack") for t in root.iter(tag)}
    n = 0
    for dev in [d for d in root.iter("PluginDevice")]:
        ann = dev.find("Annotation")
        info = trace.parse_note(ann.get("Value", "")) if ann is not None else None
        if not info:
            continue
        trk = dev
        while trk is not None and not trk.tag.endswith("Track"):
            trk = parents.get(trk)
        note = trk.find("Name/Annotation") if trk is not None else None
        if note is None:
            continue
        orig = by_id.get(info.get("original_track_id") or "")
        values = {"plugin": info.get("target_name", ""), "from": info.get("source_format", ""), "to": "VST3",
                  "preset": info.get("preset", ""), "date": info.get("when", "")[:10],
                  "state_note": state_note(info.get("state_mode", "transfer"), info.get("source_name", "")),
                  "track": _track_name_of(trk),
                  "original_track": _track_name_of(orig) if orig is not None else ""}
        note.set("Value", trace.set_track_block(note.get("Value", ""), render_lines(i18n.track_info_template(opts.track_info_template), values)))
        if orig is not None and orig is not trk:
            on = orig.find("Name/Annotation")
            if on is not None:
                on.set("Value", trace.set_track_block(
                    on.get("Value", ""), i18n.tr("Piste d'origine conservée et mutée (plugin {fmt}).\nRemplacée par : {track}",
                                                  fmt=info.get("source_format", ""), track=_track_name_of(trk))))
        n += 1
    return n


def _out_path(src: Path, root_dir: Path | None, opts: ConvertOptions) -> Path:
    name = f"{src.stem} [ReAble{opts.suffix}]{src.suffix}"
    if opts.out_dir is None:
        return src.with_name(name)
    rel = src.parent.relative_to(root_dir) if root_dir and src.is_relative_to(root_dir) else Path()
    return Path(opts.out_dir) / rel / name


def resolve_output(dst: Path, policy: str) -> Path | None:
    """Chemin de sortie selon la règle « si le fichier existe » ; None = ne rien écrire."""
    if not dst.exists() or policy == "overwrite":
        return dst
    if policy == "number":
        n = 2
        while True:
            cand = dst.with_name(f"{dst.stem} {n}{dst.suffix}")
            if not cand.exists():
                return cand
            n += 1
    return None


def run(items: list[PlanItem], opts: ConvertOptions, dry_run: bool, root_dir: Path | None = None,
        on_event: OnEvent | None = None, cancel: CancelToken | None = None, task: str = "convert") -> BatchResult:
    """Exécute le plan set par set. `dry_run` : tout est calculé en mémoire, rien n'est écrit.

    Arrêt : `cancel` est consulté avant chaque phase (lecture, conversion, contrôle, écriture) ; l'écriture finale est
    atomique, donc un arrêt laisse les sets déjà faits intacts et n'écrit jamais de fichier partiel (lève `Cancelled`)."""
    res = BatchResult(items=items)
    by_set: dict[str, list[PlanItem]] = {}
    for it in items:
        by_set.setdefault(it.set_path, []).append(it)
    rep = Reporter(task, len(by_set), on_event, cancel)
    tpl_cache: dict[str, object] = {}
    for set_path, group in by_set.items():
        name = Path(set_path).stem
        rep.step("lecture", name, set_path)
        pending = [g for g in group if g.status != "bloqué"]
        if pending and resolve_output(_out_path(Path(set_path), root_dir, opts), opts.if_exists) is None:
            for it in pending:
                it.status, it.reason = "ignoré", "déjà converti (le fichier de sortie existe)"
            rep.finish_item(name, "ignoré", "déjà converti", key=set_path)
            continue
        try:
            tree = alsfile.load(set_path)
        except Exception as e:
            res.errors.append(f"{set_path} : illisible ({e})")
            for it in group:
                it.status, it.reason = "bloqué", "set illisible"
            rep.finish_item(name, "erreur", "illisible", key=set_path)
            continue
        if not schema_ok(tree.getroot()):
            for it in group:
                if it.status != "bloqué":
                    it.status, it.reason = "bloqué", "set trop ancien (avant Live 11) : l'ouvrir et l'enregistrer dans Live 12"
            rep.finish_item(name, "ignoré", "trop ancien", key=set_path)
            continue
        baseline = set(check_tree(tree.getroot()))
        converted = 0
        for it in group:
            if it.status == "bloqué":
                continue
            rep.step("conversion", name, set_path)
            if it.template not in tpl_cache:
                tpl_cache[it.template] = alsfile.load(it.template)
            r = rewrite_tree(tree, it.plugin, tpl_cache[it.template], it.source_format, it.target_name,
                             opts.write_note, opts.embed_original, opts.max_embed_kb * 1000, Path(set_path).name,
                             opts.replace_mode, opts.mute_original, opts.original_suffix, opts.state_mode,
                             " [ancien]", opts.copy_controller_state)
            warns = [w for w in r.warnings if w not in baseline]
            if any(w.startswith(("Id en double", "Id de liste en double", "Attribut inconnu")) for w in warns):   # Live refuserait ce fichier
                for g in group:
                    g.status, g.reason = "bloqué", "contrôle d'intégrité échoué : " + "; ".join(warns)
                converted = 0
                break
            if r.converted:
                it.status = "convertible" if dry_run else "converti"
                it.instances = r.converted
                it.reason = "; ".join(warns)
                converted += r.converted
            else:
                it.status, it.reason = "bloqué", "; ".join(warns) or "rien à convertir"
        rep.step("contrôle", name, set_path)
        written, written_path = False, ""
        if converted and not dry_run:
            rep.step("écriture", name, set_path)          # dernier point d'arrêt : ensuite l'écriture atomique va à son terme
            apply_rename(tree.getroot(), opts)
            apply_track_info(tree.getroot(), opts)
            dst = resolve_output(_out_path(Path(set_path), root_dir, opts), opts.if_exists)
            if dst.resolve() == Path(set_path).resolve():
                raise ValueError("refus d'écraser l'original")
            dst.parent.mkdir(parents=True, exist_ok=True)
            alsfile.save(tree, dst)
            res.written.append(str(dst))
            written, written_path = True, str(dst)
        defaulted = any("réglages par défaut" in (g.reason or "") for g in group if g.status in ("converti", "convertible"))
        outcome = ("réglages par défaut" if defaulted else "converti") if converted else "ignoré"
        rep.finish_item(name, outcome, path=written_path, key=set_path)
    rep.end(f"{len(res.written)} projet(s) écrit(s)" if not dry_run else "essai à blanc terminé")
    return res
