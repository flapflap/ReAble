"""Langue de l'application : français (langue d'origine) ou anglais.

La page web a son propre dictionnaire (app/static/locales/en.json). Ce module sert aux textes que Python écrit lui-même :
boîtes de dialogue natives et notes écrites dans les projets Live (texte d'info de piste, suffixe des copies restaurées)."""
from __future__ import annotations

import locale
import os
import subprocess

from . import registry

LANGUAGES = ("auto", "fr", "en")

# français -> anglais, pour les textes écrits par Python (exactement le texte français du code)
EN = {
    "Arrêter et fermer ?": "Stop and close?",
    "Une tâche est en cours. Si vous fermez, le projet en cours est abandonné proprement et les copies déjà faites sont conservées.":
        "A task is running. If you close, the current project is cleanly abandoned and copies already made are kept.",
    "Dossier de projets Ableton Live": "Ableton Live project folder",
    "Réglages par défaut : le preset d'origine n'a pas été transféré": "Default settings: the original preset was not transferred",
    "Réglages transférés (en-tête adapté à la nouvelle version) : à vérifier": "Settings transferred (header adapted to the new version): to be checked",
    "Réglages transférés : à vérifier dans le plugin": "Settings transferred: check them in the plugin",
    "Réglages transférés": "Settings transferred",
    "Piste d'origine conservée et mutée (plugin {fmt}).\nRemplacée par : {track}":
        "Original track kept and muted ({fmt} plugin).\nReplaced by: {track}",
    "Restauré": "Restored",
    "Plugin manquant : {plugin} ({fmt})": "Missing plugin: {plugin} ({fmt})",
    "Preset d'origine : {preset}": "Original preset: {preset}",
    "Non converti par ReAble : {why}": "Not converted by ReAble: {why}",
    "il manque un projet Live 12 contenant le plugin remplaçant en VST3": "a Live 12 project containing the replacement plugin as VST3 is missing",
    "ReAble ne sait pas encore le convertir": "ReAble can't convert it yet",
}

TRACK_INFO_FR = ("Converti par ReAble le {date}\n{plugin} : {from} → {to}\n"
                 "Preset d'origine : {preset}\n{state_note}\nPiste d'origine : {original_track}")
TRACK_INFO_EN = ("Converted by ReAble on {date}\n{plugin}: {from} → {to}\n"
                 "Original preset: {preset}\n{state_note}\nOriginal track: {original_track}")


def preference() -> str:
    p = registry.settings().get("language", "auto")
    return p if p in LANGUAGES else "auto"


def set_preference(pref: str) -> str:
    if pref not in LANGUAGES:
        raise ValueError("langue inconnue : auto, fr ou en")
    s = registry.settings()
    s["language"] = pref
    registry.save_settings(s)
    return pref


def system_language() -> str:
    """Langue de macOS (« fr » si le français est la première langue choisie, sinon « en »)."""
    try:
        out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=3).stdout
        first = next((ln.strip().strip('",()') for ln in out.splitlines() if ln.strip().strip('",()')), "")
        if first:
            return "fr" if first.lower().startswith("fr") else "en"
    except (OSError, subprocess.SubprocessError):
        pass
    lang = os.environ.get("LANG") or (locale.getlocale()[0] or "")
    return "fr" if lang.lower().startswith("fr") else "en"


def language() -> str:
    """Langue effective : variable REABLE_LANG (tests), sinon le choix de l'utilisateur, sinon la langue du système."""
    forced = os.environ.get("REABLE_LANG")
    if forced in ("fr", "en"):
        return forced
    pref = preference()
    return system_language() if pref == "auto" else pref


def tr(fr: str, **kw) -> str:
    text = EN.get(fr, fr) if language() == "en" else fr
    return text.format(**kw) if kw else text


def track_info_template(current: str) -> str:
    """Modèle du texte d'info de piste : la version anglaise remplace le modèle français d'origine (jamais un modèle modifié)."""
    return TRACK_INFO_EN if language() == "en" and current == TRACK_INFO_FR else current
