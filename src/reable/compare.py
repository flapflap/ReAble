"""Compare l'état interne de deux instances d'un même plugin (formats différents)."""
from __future__ import annotations

import re

from .model import Plugin


def _flat(o, prefix: str = ""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _flat(v, f"{prefix}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _flat(v, f"{prefix}[{i}]")
    else:
        yield prefix, o


def compare_states(a: Plugin, b: Plugin) -> dict:
    out = {"bytes_a": a.state_bytes, "bytes_b": b.state_bytes,
           "common_keys": 0, "diff_keys": [], "same_schema": False}
    if not a.state_bytes or not b.state_bytes:
        out["verdict"] = "état vide"
        return out
    if a.state_full and b.state_full:
        fa, fb = dict(_flat(a.state_full)), dict(_flat(b.state_full))
        keys = set(fa) | set(fb)
        diff = sorted(k for k in keys if fa.get(k) != fb.get(k))
        out["same_schema"] = set(fa) == set(fb)
        out["common_keys"] = len(keys) - len(diff)
        out["diff_keys"] = diff[:20]
        out["verdict"] = "identique" if not diff else "similaire"
        return out
    out["verdict"] = "identique" if a.state_bytes == b.state_bytes else "différent"
    return out


def _flat_values(o, prefix: str = ""):
    """Valeurs feuilles d'un état JSON iZotope, sans les identifiants d'instance ni l'interface."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _flat_values(v, f"{prefix}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _flat_values(v, f"{prefix}[{i}]")
    else:
        yield prefix, o


_IGNORED = ("Param Version", "Element Name", "Extra Bytes", "Codec Format", "PluginUUID", "Global UI", "Plugin Name", "Who set the Plugin Name", "SpectrumState", "Preset Name",
            "Selected Signal Chain Module", "Show ", "PluginHeight", "PluginWidth", "Referencing")


def verify_upgrade(old_json: dict, new_json: dict, default_json: dict | None = None, min_meaningful: int = 1) -> dict:
    """L'état du plugin d'origine a-t-il été repris par le nouveau ? Compare les valeurs DSP communes.

    `default_json` = état du nouveau plugin avec ses réglages par défaut. Une valeur « significative » est
    une valeur de l'ancien état qui diffère du défaut : si le nouvel état la contient, elle a été reprise."""
    old = {k: v for k, v in _flat_values(old_json) if k.endswith("/Value") and not any(t in k for t in _IGNORED)}
    new = {k: v for k, v in _flat_values(new_json) if k.endswith("/Value") and not any(t in k for t in _IGNORED)}
    dflt = {k: v for k, v in _flat_values(default_json or {}) if k.endswith("/Value")}
    common = [k for k in old if k in new]
    meaningful = [k for k in common if k in dflt and old[k] != dflt[k]] if dflt else []
    kept = [k for k in meaningful if new[k] == old[k]]
    at_default = [k for k in meaningful if new[k] == dflt[k]]
    if len(meaningful) < min_meaningful:
        verdict = f"indéterminé (seulement {len(meaningful)} réglage(s) comparable(s) ; il en faut au moins {min_meaningful})"
    elif len(kept) >= 0.8 * len(meaningful):
        verdict = "repris"
    elif len(at_default) >= 0.8 * len(meaningful):
        verdict = "non repris (réglages par défaut)"
    else:
        verdict = "partiellement repris"
    short = lambda k: re.sub(r".*DSP Elements/Value/|/Value$", "", k)[:70]
    val = lambda v: (str(v)[:30] + "…") if len(str(v)) > 30 else v
    return {"verdict": verdict, "common": len(common), "meaningful": len(meaningful), "kept": len(kept),
            "at_default": len(at_default),
            "examples_kept": [(short(k), val(old[k])) for k in kept[:6]],
            "examples_lost": [(short(k), val(old[k]), val(new[k])) for k in meaningful if k not in kept][:6]}
