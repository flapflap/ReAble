"""Adaptateurs d'état : transforme l'état sauvegardé d'un plugin pour le device VST3 cible.

Modes (`state_mode`) :
- « transfer » : on garde l'état tel quel (re-emballé si le conteneur change) ;
- « header »   : comme « transfer », mais l'identifiant/version du conteneur sont ceux du gabarit cible
                 (utile quand une version plus récente du plugin doit « reconnaître » l'ancien état) ;
- « none »     : état vide, le plugin démarre avec ses réglages par défaut (le nom de l'ancien preset
                 reste affiché dans les notes).
Chaque adaptateur renvoie (état | None, explication) ; None = conversion refusée.
"""
from __future__ import annotations

import struct
import zlib

from .registry import adapter_of, definition_of

MODES = ("transfer", "header", "none")


def head_signature(state: bytes) -> bytes:
    """12 premiers octets avec le champ « taille » mis à zéro : forme du conteneur NI."""
    head = bytearray(state[:12])
    for off in (0, 4, 8):
        size = int.from_bytes(state[off:off + 4], "little")
        if len(state) - size in (0, 4, 8, 12):
            head[off:off + 4] = b"\0\0\0\0"
            break
    return bytes(head)


def izotope_container(state: bytes) -> tuple[bytes, bytes, bytes] | None:
    """(magic+version, taille décompressée, flux zlib) d'un état iZotope VST2 ou VST3, sinon None.

    VST3 : magic(4) version(4) taille(4) taille_décompressée(4) zlib
    VST2 : taille_totale(4) + même en-tête + zlib + 11 octets de queue
    """
    z = state.find(b"\x78\x9c")
    if z not in (16, 20):
        return None
    dec = zlib.decompressobj()
    try:
        dec.decompress(state[z:])
    except zlib.error:
        return None
    used = len(state) - z - len(dec.unused_data)
    return state[z - 16:z - 8], state[z - 4:z], state[z:z + used]


def _izotope(state: bytes, template_state: bytes, retarget: bool) -> tuple[bytes | None, str]:
    src = izotope_container(state)
    if src is None:
        return None, "état iZotope non reconnu (ancien format binaire ?)"
    magic_ver, unc, stream = src
    if retarget:
        tpl = izotope_container(template_state)
        if tpl is None:
            return None, "gabarit cible : conteneur iZotope non reconnu"
        magic_ver = tpl[0]
    return magic_ver + struct.pack("<I", len(stream) + 4) + unc + stream, ""


def adapt_state(plugin_name: str, state: bytes, template_state: bytes, mode: str = "transfer") -> tuple[bytes | None, str]:
    if mode == "none":
        return b"", ""
    adapter = adapter_of(plugin_name)
    if adapter == "izotope":
        return _izotope(state, template_state, retarget=(mode == "header"))
    if adapter == "none":
        return None, "ce plugin n'accepte que l'état par défaut (state_mode = none)"
    if head_signature(state) != head_signature(template_state):
        return None, (f"conteneur d'état différent du gabarit ({head_signature(state).hex()} ≠ "
                      f"{head_signature(template_state).hex()})")
    return state, ""


def effective_mode(plugin_name: str, mode: str, target_name: str = "") -> tuple[str, str]:
    """Mode réellement appliqué : si la définition dit que l'état de cette version n'est pas repris, ou si la cible est un
    autre plugin (remplacement choisi par l'utilisateur), on passe en « none » : le plugin cible démarre avec ses
    réglages par défaut ; l'ancien nom de preset reste en note."""
    if mode != "none" and target_name and is_other_plugin(plugin_name, target_name):
        return "none", (f"l'état de « {plugin_name} » n'est pas repris par « {target_name} » (plugin différent) : "
                        "réglages par défaut (ancien preset conservé en note)")
    d = definition_of(plugin_name)
    if mode != "none" and d is not None and not d.transfers_state(plugin_name):
        return "none", (f"l'état de « {plugin_name} » n'est pas repris par la version cible : "
                        "réglages par défaut (ancien preset conservé en note)")
    return mode, ""


def is_other_plugin(source_name: str, target_name: str) -> bool:
    """Vrai si la cible n'est pas une version du même plugin que la source (ex. Play → Opus, mais pas Ozone 9 → Ozone 10)."""
    a, b = definition_of(source_name), definition_of(target_name)
    if a is not None and b is not None and a.id == b.id:
        return False
    if a is None and b is None:
        return source_name.strip().lower() != target_name.strip().lower()
    return True


def state_note(mode: str, plugin_name: str = "") -> str:
    """Phrase pour le texte d'info de piste."""
    if mode == "none":
        return "Réglages par défaut : le preset d'origine n'a pas été transféré"
    if mode == "header":
        return "Réglages transférés (en-tête adapté à la nouvelle version) : à vérifier"
    if adapter_of(plugin_name) == "izotope":
        return "Réglages transférés : à vérifier dans le plugin"
    return "Réglages transférés"
