"""Décodeurs d'état de plugins.

Chaque décodeur reçoit les octets bruts de l'état sauvegardé par Live et
renvoie (preset_name, summary, full) ou None s'il ne reconnaît pas le format.
Ajouter un plugin = ajouter un module ici et l'enregistrer dans DECODERS.
"""
from __future__ import annotations

from . import ni_msgpack, izotope_json

# Ordre = priorité
DECODERS = [ni_msgpack.decode, izotope_json.decode]


def decode_state(raw: bytes, plugin_name: str = ""):
    for dec in DECODERS:
        try:
            res = dec(raw, plugin_name)
        except Exception:  # un décodeur ne doit jamais casser le scan
            res = None
        if res:
            return res
    return None
