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
import platform
import plistlib
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .extract import fourcc
from .families import family_of
from .model import Plugin

ROOTS = [Path("/Library/Audio/Plug-Ins"), Path.home() / "Library/Audio/Plug-Ins"]

_CPU_X86_64, _CPU_ARM64 = 0x01000007, 0x0100000C


def bundle_archs(bundle: Path) -> set[str]:
    """Architectures du binaire d'un plugin (« x86_64 », « arm64 »), lues dans l'en-tête Mach-O. Vide si illisible."""
    try:
        exe = None
        try:
            name = plistlib.loads((bundle / "Contents/Info.plist").read_bytes()).get("CFBundleExecutable")
            exe = bundle / "Contents/MacOS" / name if name else None
        except Exception:
            pass
        if exe is None or not exe.is_file():
            files = [f for f in (bundle / "Contents/MacOS").glob("*") if f.is_file()]
            exe = files[0] if files else None
        if exe is None:
            return set()
        with exe.open("rb") as fh:
            head = fh.read(4096)
    except OSError:
        return set()
    magic = head[:4]
    cpus: list[int] = []
    if magic in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):                 # binaire universel (en-tête en gros-boutiste)
        n = struct.unpack(">I", head[4:8])[0]
        size = 20 if magic[-1] == 0xbf else 20
        for i in range(min(n, 8)):
            off = 8 + i * size
            cpus.append(struct.unpack(">I", head[off:off + 4])[0])
    elif magic in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe"):                 # binaire simple (petit-boutiste)
        cpus.append(struct.unpack("<I", head[4:8])[0])
    names = {_CPU_X86_64: "x86_64", _CPU_ARM64: "arm64"}
    return {names[c] for c in cpus if c in names}


def runs_natively_here() -> bool:
    return platform.machine() == "arm64"


@dataclass
class Inventory:
    au_ids: dict[str, str] = field(default_factory=dict)      # "aumu/NiMH/-NI-" -> nom
    vst3_uids: dict[str, str] = field(default_factory=dict)   # UID hex -> nom
    vst3_names: set[str] = field(default_factory=set)
    vst2_names: set[str] = field(default_factory=set)
    # installés mais seulement en Intel (x86_64) : Live en natif sur Apple Silicon ne les charge pas
    intel_only: dict[str, set[str]] = field(default_factory=lambda: {"AU": set(), "VST3": set(), "VST2": set()})
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
                if _intel_only(comp):
                    inv.intel_only["AU"].add(key)
        for b in (r / "VST3").glob("*.vst3"):
            inv.available = True
            inv.vst3_names.add(_norm(b.stem))
            if _intel_only(b):
                inv.intel_only["VST3"].add(_norm(b.stem))
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
            if _intel_only(b):
                inv.intel_only["VST2"].add(_norm(b.stem))
    return inv


def _intel_only(bundle: Path) -> bool:
    if not runs_natively_here():
        return False
    a = bundle_archs(bundle)
    return bool(a) and "arm64" not in a


INTEL_DETAIL = "installé en Intel seulement : Live ne le charge pas en natif sur Apple Silicon"


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
            if ok and p.identifier in inv.intel_only["AU"]:
                ok, p.install_detail = False, INTEL_DETAIL
        elif p.format == "VST3":
            if p.identifier and p.identifier.upper() in inv.vst3_uids:
                ok, p.install_detail = True, "UID VST3 exact"
            else:
                ok = n in names["VST3"]
                p.install_detail = "nom de bundle (probable)" if ok else "VST3 absent"
            if ok and (n in inv.intel_only["VST3"] or _norm(inv.vst3_uids.get(p.identifier.upper(), "")) in inv.intel_only["VST3"]):
                ok, p.install_detail = False, INTEL_DETAIL
        elif p.format == "VST2":
            ok = n in names["VST2"]
            p.install_detail = "nom de bundle (probable)" if ok else "VST2 absent"
            if ok and n in inv.intel_only["VST2"]:
                ok, p.install_detail = False, INTEL_DETAIL
        else:
            ok = False
        p.install_status = "installé" if ok else "manquant"
        if not ok:
            p.replacements = [fmt for fmt, s in names.items() if fmt != p.format and n in s]
        if not ok:
            fam = family_of(p.name)
            if fam:
                p.family_installed = sorted({nm for s in names.values() for nm in s if family_of(nm) == fam})
