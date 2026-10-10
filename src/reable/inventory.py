"""Inventaire des plugins installés (macOS) et détection des manquants.

Sources, de la plus fiable à la moins fiable :
1. Audio Units : Info.plist de chaque .component -> AudioComponents
   (type / sous-type / fabricant). Correspondance exacte avec le .als.
2. VST3 : Contents/Resources/moduleinfo.json (SDK >= 3.7.5) -> CID des classes.
   Sinon, correspondance par nom de bundle.
3. VST2 : nom du bundle .vst (l'ID n'est lisible qu'en chargeant le plugin).

À explorer : la base de données de plugins de Live
(~/Library/Application Support/Ableton/Live Database/*.db) qui dirait
exactement ce que Live, lui, voit.
"""
from __future__ import annotations

import json
import plistlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .extract import fourcc
from .families import family_of
from .model import Plugin

ROOTS = [Path("/Library/Audio/Plug-Ins"), Path.home() / "Library/Audio/Plug-Ins"]


@dataclass
class Inventory:
    au_ids: dict[str, str] = field(default_factory=dict)      # "aumu/NiMH/-NI-" -> nom
    vst3_uids: dict[str, str] = field(default_factory=dict)   # UID hex -> nom
    vst3_names: set[str] = field(default_factory=set)
    vst2_names: set[str] = field(default_factory=set)
    available: bool = False

    def names_by_format(self) -> dict[str, set[str]]:
        return {"AU": {n.lower() for n in self.au_ids.values()},
                "VST3": {n.lower() for n in self.vst3_names},
                "VST2": {n.lower() for n in self.vst2_names}}


def _norm(name: str) -> str:
    return name.lower().replace("_", " ").strip()


def scan_installed(roots: list[Path] | None = None) -> Inventory:
    inv = Inventory()
    if sys.platform != "darwin" and roots is None:
        return inv  # inventaire non disponible : statut « inconnu »
    roots = roots or ROOTS
    for r in roots:
        for comp in (r / "Components").glob("*.component"):
            inv.available = True
            try:
                info = plistlib.loads((comp / "Contents/Info.plist").read_bytes())
            except Exception:
                continue
            for ac in info.get("AudioComponents", []):
                key = f"{ac.get('type')}/{ac.get('subtype')}/{ac.get('manufacturer')}"
                nm = ac.get("name", comp.stem)
                inv.au_ids[key] = nm.split(":")[-1].strip()
        for b in (r / "VST3").glob("*.vst3"):
            inv.available = True
            inv.vst3_names.add(_norm(b.stem))
            mi = b / "Contents/Resources/moduleinfo.json"
            if mi.exists():
                try:
                    data = json.loads(mi.read_text(errors="replace"))
                    for c in data.get("Classes", []):
                        inv.vst3_uids[c.get("CID", "").upper()] = c.get("Name", b.stem)
                except Exception:
                    pass
        for b in (r / "VST").glob("*.vst"):
            inv.available = True
            inv.vst2_names.add(_norm(b.stem))
    return inv


def check(plugins: list[Plugin], inv: Inventory) -> None:
    """Renseigne install_status / install_detail / replacements."""
    if not inv.available:
        for p in plugins:
            p.install_status = "inconnu"
            p.install_detail = "inventaire indisponible (lancer sur le Mac)"
        return
    names = inv.names_by_format()
    for p in plugins:
        n = _norm(p.name)
        if p.format == "AU":
            ok = p.identifier in inv.au_ids
            p.install_detail = "identifiant AU exact" if ok else "AU absent"
        elif p.format == "VST3":
            if p.identifier and p.identifier.upper() in inv.vst3_uids:
                ok, p.install_detail = True, "UID VST3 exact"
            else:
                ok = n in names["VST3"]
                p.install_detail = "nom de bundle (probable)" if ok else "VST3 absent"
        elif p.format == "VST2":
            ok = n in names["VST2"]
            p.install_detail = "nom de bundle (probable)" if ok else "VST2 absent"
        else:
            ok = False
        p.install_status = "installé" if ok else "manquant"
        if not ok:
            p.replacements = [fmt for fmt, s in names.items() if fmt != p.format and n in s]
        if not ok:
            fam = family_of(p.name)
            if fam:
                p.family_installed = sorted({nm for s in names.values() for nm in s if family_of(nm) == fam})
