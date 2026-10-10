"""Sondage : classe le conteneur d'état de chaque plugin d'un dossier de sets.

Sert à savoir, pour un plugin inconnu, quel adaptateur de conversion est plausible,
sans connaître le plugin à l'avance (base de l'extension par l'utilisateur).
"""
from __future__ import annotations

import binascii
import re
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import alsfile
from .adapters import head_signature
from .registry import definition_of, family_of

KINDS = {
    "ni-classic": "conteneur NI classique (<taille> 00000000 01000000 …) : copiable tel quel",
    "ni-msgpack": "conteneur NI récent (02000000 03000000 …) : copiable tel quel",
    "izotope": "iZotope (en-tête + zlib JSON) : ré-emballage VST2 → VST3",
    "ni-tagged": "conteneur NI étiqueté (<ID plugin> 01000000 02000000 …) : à tester (copie probable)",
    "zlib": "flux zlib direct : à tester (copie probable)",
    "juce-vstw": "enveloppe « VstW » (JUCE/Spitfire/Abbey Road) : à tester (copie probable)",
    "xml": "XML en clair : à tester",
    "fxp": "chunk FXP/FXB (CcnK) : format VST2 standard, adaptation nécessaire",
    "text": "texte/préréglage nommé (ex. FabFilter) : adaptation spécifique",
    "opaque": "format propriétaire non reconnu",
    "empty": "pas d'état sauvegardé",
}


def classify(state: bytes) -> str:
    if not state:
        return "empty"
    if state[:4] == b"VstW":
        return "juce-vstw"
    if state[:4] == b"CcnK":
        return "fxp"
    if state.lstrip()[:5] == b"<?xml":
        return "xml"
    if state[:2] == b"\x78\x9c":
        return "zlib"
    if state[:8] == bytes.fromhex("0200000003000000"):
        return "ni-msgpack"
    if state[4:12] == bytes.fromhex("0100000002000000") or b"#NI#" in state[:16]:
        return "ni-tagged"
    z = state.find(b"\x78\x9c")
    if z in (16, 20):
        try:
            zlib.decompressobj().decompress(state[z:z + 4096])
            return "izotope"
        except zlib.error:
            pass
    sig = head_signature(state)
    if sig[4:12] == bytes.fromhex("0000000001000000") or sig[:8] == bytes.fromhex("0000000001000000"):
        return "ni-classic"
    if len(state) > 8 and all(32 <= c < 127 for c in state[:8]):
        return "text"
    return "opaque"


@dataclass
class ProbeRow:
    name: str
    formats: dict[str, int] = field(default_factory=dict)     # format -> instances
    kinds: dict[str, int] = field(default_factory=dict)       # type de conteneur -> instances
    vst3_template: bool = False
    installed_vst3: bool = False
    family: str | None = None

    @property
    def status(self) -> str:
        d = definition_of(self.name)
        if d and d.adapter and d.status == "validated":
            return "validé"
        if d and d.adapter and d.status == "experimental":
            return "en test"
        kind = max(self.kinds, key=self.kinds.get) if self.kinds else "empty"
        if kind in ("ni-classic", "ni-msgpack", "ni-tagged", "izotope", "zlib", "juce-vstw"):
            return "à tester"
        return "adaptateur à écrire"


def _hex(el) -> bytes:
    if el is None or not (el.text or "").strip():
        return b""
    return binascii.unhexlify(re.sub(r"\s", "", el.text))


def probe(files: list[Path]) -> list[ProbeRow]:
    rows: dict[str, ProbeRow] = {}
    for f in files:
        try:
            root = alsfile.load(f).getroot()
        except Exception:
            continue
        for d in root.iter():
            if d.tag == "AuPluginDevice":
                info, name, fmt = d.find(".//AuPluginInfo"), None, "AU"
                if info is None or info.find("Name") is None:
                    continue
                name = info.find("Name").get("Value")
                state = b""
                buf = _hex(d.find(".//AuPreset/Buffer"))
                if buf:
                    import plistlib
                    try:
                        state = plistlib.loads(buf).get("vstdata") or b""
                    except Exception:
                        state = buf
            elif d.tag == "PluginDevice":
                v3, v2 = d.find(".//Vst3PluginInfo"), d.find(".//VstPluginInfo")
                if v3 is not None and v3.find("Name") is not None:
                    name, fmt, state = v3.find("Name").get("Value"), "VST3", _hex(d.find(".//Vst3Preset/ProcessorState"))
                elif v2 is not None and v2.find("PlugName") is not None:
                    name, fmt, state = v2.find("PlugName").get("Value"), "VST2", _hex(d.find(".//VstPreset/Buffer"))
                else:
                    continue
            else:
                continue
            row = rows.setdefault(name, ProbeRow(name, family=family_of(name)))
            row.formats[fmt] = row.formats.get(fmt, 0) + 1
            k = classify(state)
            row.kinds[k] = row.kinds.get(k, 0) + 1
            if fmt == "VST3":
                row.vst3_template = True
    return sorted(rows.values(), key=lambda r: -sum(r.formats.values()))
