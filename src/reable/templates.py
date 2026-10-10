"""Bibliothèque de gabarits VST3 : un device VST3 écrit par Live, gardé pour les analyses suivantes.

Pourquoi : pour convertir un plugin il faut un device VST3 « modèle » écrit par Live lui-même (jamais inventé). Il est
pris dans les projets de l'utilisateur. Sans bibliothèque, analyser un petit dossier qui ne contient pas déjà le plugin
cible bloquerait tout. Chaque analyse mémorise donc, dans `<dossier utilisateur>/templates/`, un exemplaire par plugin
(le plus récent), sous forme d'un mini-fichier .als qui ne contient que ce device.
"""
from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import alsfile, registry


def library_dir() -> Path:
    return registry.user_dir() / "templates"


def library_files() -> list[Path]:
    d = library_dir()
    return sorted(d.glob("*.als")) if d.is_dir() else []


def _version(creator: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", creator)[:3])


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "plugin"


def _stored_version(f: Path) -> tuple:
    try:
        return _version(alsfile.load(f).getroot().get("Creator", ""))
    except Exception:                                   # noqa: BLE001 - fichier abîmé : sera remplacé
        return ()


def remember(files: list[Path]) -> list[str]:
    """Mémorise, pour chaque plugin VST3 vu dans `files`, le device de la version de Live la plus récente.
    Renvoie les noms de plugins ajoutés ou mis à jour. Ne touche jamais aux projets analysés."""
    best: dict[str, tuple[tuple, ET.Element, str]] = {}
    for f in files:
        try:
            root = alsfile.load(f).getroot()
        except Exception:                               # noqa: BLE001
            continue
        ver = _version(root.get("Creator", ""))
        if root.find(".//Pointee") is None:
            continue                                    # projet trop ancien : schéma incompatible, pas un bon gabarit
        for dev in root.iter("PluginDevice"):
            info = dev.find(".//Vst3PluginInfo")
            n = info.find("Name") if info is not None else None
            if n is None or not n.get("Value") or dev.find("Pointee") is None:
                continue
            key = n.get("Value").lower()
            if key not in best or ver > best[key][0]:
                best[key] = (ver, dev, root.get("Creator", ""))
    added: list[str] = []
    library_dir().mkdir(parents=True, exist_ok=True)
    for key, (ver, dev, creator) in best.items():
        dst = library_dir() / f"{_slug(key)}.als"
        if dst.exists() and _stored_version(dst) >= ver:
            continue
        mini = ET.Element("Ableton", {"Creator": creator, "MajorVersion": "5"})
        live = ET.SubElement(mini, "LiveSet")
        ET.SubElement(live, "NextPointeeId", {"Value": "1"})
        live.append(copy.deepcopy(dev))
        alsfile.save(ET.ElementTree(mini), dst, backup=False)
        added.append(dev.find(".//Vst3PluginInfo/Name").get("Value"))
    return added
