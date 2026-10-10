"""Native Instruments, nouvelle génération (Massive X, etc.).

Format observé (Massive X, AU, Live 12) :
  en-tête 16 octets  [u32 2][u32 2][u32 taille][u32 ?]
  puis zlib -> flux msgpack de paires   "strings", n, {clé: str}
                                        "floats",  n, {clé: float}
                                        "doubles", n, {clé: float}
                                        "ints",    n, {clé: int}
                                        "bools",   n, {clé: bool}
                                        ... puis des vecteurs.
Les clés sont des chemins lisibles : root/engine/unit1/audioPluginSlots/...
"""
from __future__ import annotations

import re
import zlib

try:
    import msgpack
except ImportError:  # dépendance optionnelle
    msgpack = None

TYPED = ("strings", "floats", "doubles", "ints", "bools")


def _unpack(raw: bytes):
    z = raw.find(b"\x78\x9c")
    if z < 0 or z > 64 or msgpack is None:
        return None
    data = zlib.decompressobj().decompress(raw[z:])
    if not data[:12].lstrip(b"\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8").startswith(b"strings"):
        return None
    u = msgpack.Unpacker(raw=False, strict_map_key=False)
    u.feed(data)
    objs = list(u)
    tables: dict[str, dict] = {}
    for i, o in enumerate(objs):
        if isinstance(o, str) and o in TYPED and i + 2 < len(objs) and isinstance(objs[i + 2], dict):
            tables[o] = objs[i + 2]
    return tables or None


def _clean(v):
    if isinstance(v, str):
        return v.replace("\x00", "").strip()
    return v


def decode(raw: bytes, plugin_name: str = ""):
    tables = _unpack(raw)
    if not tables:
        return None
    s = tables.get("strings", {})
    nums = {**tables.get("floats", {}), **tables.get("doubles", {})}
    ints = tables.get("ints", {})
    bools = tables.get("bools", {})

    preset = _clean(s.get("meta/presetName", "")) or _clean(s.get("meta/name", "")) \
        or _clean(s.get("meta/unit0/patchName", ""))

    summary: dict = {"Format d'état": "Native Instruments (msgpack)"}

    # Macros : nom + valeur
    macros = []
    for k, name in s.items():
        m = re.match(r"root/engine/global/macros/(macro\w+)/macroName/value$", k)
        if not m:
            continue
        mid = m.group(1)
        val = nums.get(f"root/engine/global/macros/{mid}/macroValue/normalizedValue")
        name = _clean(name)
        if name and not re.fullmatch(r"Macro \d+", name):
            macros.append((mid, name, val))
    if macros:
        def order(t):
            n = re.sub(r"\D", "", t[0])
            return (0, int(n)) if n else (1, t[0])
        summary["Macros"] = {
            f"{mid} « {n} »": (f"{v * 100:.0f} %" if isinstance(v, float) else "?")
            for mid, n, v in sorted(macros, key=order)
        }

    # Modules choisis dans chaque slot (oscillateurs, filtre, FX, modulateurs)
    slots = {}
    for k, v in s.items():
        m = re.match(r"root/engine/unit1/(audio|modulation)PluginSlots/(\w+)/selectedPlugin$", k)
        if m and _clean(v):
            slots[m.group(2)] = _clean(v)
    if slots:
        summary["Modules par slot"] = dict(sorted(slots.items()))

    # Réglages à choix (type de filtre, modes...) des modules actifs
    choices = {}
    for k, v in s.items():
        m = re.match(r"root/engine/unit1/(?:audio|modulation)PluginSlots/(\w+)/(?:audio|modulation)Plugins/(\w+)/(.+?)/selectedEntryName$", k)
        if m and slots.get(m.group(1)) == m.group(2):
            choices[f"{m.group(1)} · {m.group(3).split('/')[0]}"] = _clean(v)
    for k, v in s.items():
        m = re.match(r"root/engine/unit1/genericAdapters/VoicePage/(.+?)/selectedEntryName$", k)
        if m:
            choices[f"Voix · {m.group(1).split('/')[0]}"] = _clean(v)
    if choices:
        summary["Réglages (choix)"] = dict(sorted(choices.items()))

    # Tables (wavetables, noise) : identifiants internes
    tables_used = {k.split("/audioPluginSlots/")[-1]: _clean(v) for k, v in s.items()
                   if re.search(r"(wavetable/hash|noisetableId|chordtableName|harmonizetableName)$", k)}
    if tables_used:
        summary["Tables utilisées (ids internes NI)"] = tables_used

    summary["Nombre de valeurs dans l'état"] = sum(len(t) for t in tables.values())

    full = {
        "strings": {k: _clean(v) for k, v in s.items()},
        "numbers": nums,
        "ints": ints,
        "bools": bools,
    }
    return preset, summary, full
