"""Lecture / écriture des fichiers Ableton Live (.als = XML compressé en gzip)."""
from __future__ import annotations

import gzip
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


def load(path: str | Path) -> ET.ElementTree:
    """Charge un .als (gzip) ou un .xml déjà décompressé."""
    path = Path(path)
    with open(path, "rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        with gzip.open(path, "rb") as f:
            return ET.parse(f)
    return ET.parse(path)


def live_version(tree: ET.ElementTree) -> str:
    root = tree.getroot()
    return root.get("Creator", "inconnu")


def save(tree: ET.ElementTree, path: str | Path, backup: bool = True) -> Path:
    """Écrit un .als de façon atomique : fichier temporaire dans le même dossier, puis renommage.

    Si l'écriture échoue ou est interrompue, le fichier final est complet ou absent (jamais tronqué) et aucun
    temporaire ne reste. Ne jamais écraser un original sans sauvegarde."""
    path = Path(path)
    if backup and path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}"))
    data = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


OUTPUT_MARKS = (" [ReAble", " [PlugRescue", " [Restauré", " [Restored")   # fichiers produits par l'outil (PlugRescue = ancien nom)


def is_output_file(name: str) -> bool:
    """Un fichier produit par l'outil (copie convertie ou restaurée) : jamais re-analysé, jamais traité comme un original."""
    return any(m in name for m in OUTPUT_MARKS)


SKIP_DIRS = {"Backup", "Factory Packs"}  # sauvegardes auto de Live, packs d'usine Ableton


def find_sets(folder: str | Path, include_packs: bool = False) -> list[Path]:
    """Tous les .als d'un dossier, sans les sauvegardes automatiques ni les packs d'usine."""
    folder = Path(folder)
    skip = {"Backup"} if include_packs else SKIP_DIRS
    out = []
    for p in sorted(folder.rglob("*.als")):
        if skip.intersection(p.relative_to(folder).parts) or ".backup-" in p.name:
            continue
        if is_output_file(p.name):
            continue
        out.append(p)
    return out
