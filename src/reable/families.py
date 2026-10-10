"""Familles de plugins : « Kontakt 5 », « Kontakt 8 » → « kontakt ».

Les définitions viennent maintenant du registre (registry.py) : intégrées, partagées ou ajoutées par l'utilisateur.
Ce module garde les anciens noms pour les appelants existants.
"""
from __future__ import annotations

from .registry import allowed_families, family_of

__all__ = ["family_of", "allowed_families"]
