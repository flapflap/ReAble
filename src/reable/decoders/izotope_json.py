"""iZotope (Ozone, Neutron...) : état = en-tête + zlib -> JSON « Context State »."""
from __future__ import annotations

import json
import zlib


def decode(raw: bytes, plugin_name: str = ""):
    z = raw.find(b"\x78\x9c")
    if z < 0 or z > 64:
        return None
    data = zlib.decompressobj().decompress(raw[z:])
    if not data.lstrip().startswith(b"{"):
        return None
    doc = json.loads(data.decode("utf-8", "replace"))
    preset = ""

    def walk(o, depth=0):
        nonlocal preset
        if preset or depth > 12:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and "preset" in k.lower() and "name" in k.lower():
                    val = v.get("Value") if isinstance(v, dict) else v
                    if isinstance(val, str) and val.strip():
                        preset = val.strip()
                        return
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, depth + 1)

    walk(doc)
    summary = {"Format d'état": "JSON compressé (type iZotope)",
               "Taille décompressée": f"{len(data) // 1024} Ko"}
    return preset, summary, {"json": doc}
