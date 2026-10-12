"""Traçabilité : une note ReAble dans l'`Annotation` du device converti.

Format de la note (la partie écrite par l'utilisateur reste intacte, avant le bloc) :

    <texte de l'utilisateur>
    --- ReAble ---
    {json}
    --- /ReAble ---

Le JSON décrit l'origine (format, identifiant, empreinte de l'état) et, en option,
embarque le device d'origine (XML compressé en gzip puis base64) pour `restore`.
"""
from __future__ import annotations

import base64
import copy
import gzip
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

BRAND = "ReAble"
LEGACY_BRANDS = ("PlugRescue",)       # ancien nom du projet : les copies déjà écrites restent lisibles et restaurables
BEGIN = f"--- {BRAND} ---"
END = f"--- /{BRAND} ---"


def _block_re(begin_fmt: str, end_fmt: str) -> re.Pattern:
    names = "|".join(re.escape(b) for b in (BRAND, *LEGACY_BRANDS))
    return re.compile(r"--- (?:" + names + r")" + begin_fmt + r" ---\n(.*?)\n--- /(?:" + names + r")" + end_fmt + r" ---", re.S)


_BLOCK = _block_re("", "")


TRACK_BEGIN = f"--- {BRAND} (piste) ---"
TRACK_END = f"--- /{BRAND} (piste) ---"
_TRACK_BLOCK = _block_re(r" \(piste\)", r" \(piste\)")


def set_track_block(existing: str, text: str) -> str:
    """Texte d'info de piste : le texte de l'utilisateur d'abord, puis le bloc ReAble (remplacé s'il existe)."""
    base = _TRACK_BLOCK.sub("", existing or "").strip()
    return (base + "\n\n" if base else "") + f"{TRACK_BEGIN}\n{text}\n{TRACK_END}"


def get_track_block(text: str) -> str:
    """Contenu du bloc ReAble d'un texte d'info de piste (chaîne vide s'il n'y en a pas)."""
    m = _TRACK_BLOCK.search(text or "")
    if not m:
        return ""
    return m.group(0)[len(TRACK_BEGIN):-len(TRACK_END)].strip()


def strip_track_block(text: str) -> str:
    return _TRACK_BLOCK.sub("", text or "").strip()


def clear_track_info(trk: ET.Element) -> None:
    el = trk.find("Name/Annotation")
    if el is not None:
        el.set("Value", strip_track_block(el.get("Value", "")))


def build_note(existing: str, info: dict) -> str:
    """Ajoute (ou remplace) le bloc ReAble à la suite du texte existant."""
    base = strip_note(existing).rstrip()
    body = json.dumps(info, ensure_ascii=False, indent=1)
    return (base + "\n\n" if base else "") + f"{BEGIN}\n{body}\n{END}"


def parse_note(text: str) -> dict | None:
    m = _BLOCK.search(text or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def strip_note(text: str) -> str:
    return _BLOCK.sub("", text or "").strip()


def pack_original(dev: ET.Element) -> str:
    """Device d'origine -> texte base64 (gzip), sans modifier `dev`."""
    clone = copy.deepcopy(dev)
    clone.tail = None
    raw = ET.tostring(clone, encoding="utf-8")
    return base64.b64encode(gzip.compress(raw, 9)).decode("ascii")


def unpack_original(payload: str) -> ET.Element:
    return ET.fromstring(gzip.decompress(base64.b64decode(payload)))


def _track_name(trk: ET.Element, fn) -> None:
    for path in ("Name/UserName", "Name/EffectiveName"):
        el = trk.find(path)
        if el is not None:
            el.set("Value", fn(el.get("Value", "")))


def _restore_duplicate(root, dev, info, parents, res) -> None:
    """Supprime la piste copie et réactive la piste d'origine (retire son suffixe)."""
    copy_trk = dev
    while copy_trk is not None and not copy_trk.tag.endswith("Track"):
        copy_trk = parents.get(copy_trk)
    orig = next((t for tag in ("MidiTrack", "AudioTrack") for t in root.iter(tag)
                 if t.get("Id") == info.get("original_track_id")), None)
    if copy_trk is None or orig is None or orig is copy_trk:
        res.warnings.append(f"« {info.get('target_name', '?')} » : piste d'origine introuvable")
        return
    sp = orig.find("DeviceChain/Mixer/Speaker/Manual")
    if sp is not None:
        sp.set("Value", "true")
    clear_track_info(orig)
    suffix = info.get("original_suffix", " [original]")
    _track_name(orig, lambda n: n[: -len(suffix)] if suffix and n.endswith(suffix) else n)
    parent = parents[copy_trk]
    if copy_trk not in list(parent):      # déjà retirée (plusieurs devices sur la même piste)
        return
    parent.remove(copy_trk)
    res.restored += 1


def _restore_keep(root, new, info, parents, res) -> None:
    """Supprime le nouveau device, réactive l'ancien et lui rend ses Id d'automation."""
    from .rewrite import transfer_ids
    old = next((d for d in root.iter() if d.tag in ("PluginDevice", "AuPluginDevice")
                and d.find("Pointee") is not None and d.find("Pointee").get("Id") == info.get("old_pointee")), None)
    if old is None or old is new:
        res.warnings.append(f"« {info.get('target_name', '?')} » : ancien device introuvable")
        return
    old.find("On/Manual").set("Value", "true")
    suffix = info.get("old_device_suffix", "")
    un = old.find("UserName")
    if un is not None and suffix and un.get("Value", "").endswith(suffix):
        un.set("Value", un.get("Value", "")[: -len(suffix)])
    transfer_ids(new, old, set(), res.warnings)          # les automations reprennent leur cible d'origine
    parent = parents[new]
    parent.remove(new)
    res.restored += 1


@dataclass
class RestoreResult:
    restored: int = 0
    warnings: list[str] = field(default_factory=list)


def restore_tree(tree: ET.ElementTree, original_tree: ET.ElementTree | None = None) -> RestoreResult:
    """Remet les devices d'origine : depuis la note si elle embarque l'original, sinon depuis
    `original_tree` (le set d'origine), en retrouvant le device par son Id `Pointee`."""
    root = tree.getroot()
    res = RestoreResult()
    parents = {c: p for p in root.iter() for c in p}
    for dev in [d for d in root.iter("PluginDevice")]:
        ann = dev.find("Annotation")
        info = parse_note(ann.get("Value", "")) if ann is not None else None
        if not info:
            continue
        if info.get("replace_mode") == "duplicate_track":
            _restore_duplicate(root, dev, info, parents, res)
            continue
        if info.get("replace_mode") == "keep_device":
            _restore_keep(root, dev, info, parents, res)
            continue
        payload = info.get("original_gz_b64")
        if payload:
            orig = unpack_original(payload)
        else:
            orig = None
            if original_tree is not None and info.get("pointee"):
                dev_tag = "AuPluginDevice" if info.get("source_format") == "AU" else "PluginDevice"
                orig = next((d for d in original_tree.getroot().iter(dev_tag)
                             if d.find("Pointee") is not None and d.find("Pointee").get("Id") == info["pointee"]), None)
                orig = copy.deepcopy(orig) if orig is not None else None
            if orig is None:
                res.warnings.append(f"« {info.get('target_name', '?')} » : original non embarqué "
                                    f"(donner le set d'origine « {info.get('source_file', '?')} » avec --original)")
                continue
        user_text = strip_note(ann.get("Value", ""))
        old = orig.find("Annotation")
        if old is not None:
            old.set("Value", user_text)
        orig.tail = dev.tail
        parent = parents[dev]
        parent[list(parent).index(dev)] = orig
        before = info.get("track_name_before")
        if before is not None:
            trk = dev
            while trk is not None and not trk.tag.endswith("Track"):
                trk = parents.get(trk)
            if trk is not None:
                _track_name(trk, lambda _n: before)
        trk = dev
        while trk is not None and not trk.tag.endswith("Track"):
            trk = parents.get(trk)
        if trk is not None:
            clear_track_info(trk)
        res.restored += 1
    return res
