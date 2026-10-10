"""Structures de données produites par l'extraction."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Parameter:
    name: str
    param_id: int
    value: float              # valeur normalisée 0..1 telle que stockée par Live
    automation_target: str | None = None
    modulation_target: str | None = None
    automated: bool = False    # automation d'arrangement
    clip_envelopes: int = 0    # enveloppes de clip (modulation) qui le visent


@dataclass
class Plugin:
    track: str
    chain_path: str            # ex. "Massive X" ou "Rack > Chain 1 > Plugin"
    format: str                # AU | VST2 | VST3
    name: str
    manufacturer: str = ""
    identifier: str = ""       # AU: type/sous-type/fabricant ; VST3: UID ; VST2: ID
    user_name: str = ""        # nom renommé dans Live
    enabled: bool = True
    preset_name: str = ""      # nom de preset le plus fiable trouvé
    preset_source: str = ""    # d'où vient ce nom
    last_preset_file: str = ""
    parameters: list[Parameter] = field(default_factory=list)
    state_bytes: int = 0
    state_summary: dict[str, Any] = field(default_factory=dict)  # décodage lisible
    state_full: dict[str, Any] = field(default_factory=dict)     # toutes les valeurs (JSON)
    install_status: str = "inconnu"  # installé | manquant | inconnu
    install_detail: str = ""
    replacements: list[str] = field(default_factory=list)
    family_installed: list[str] = field(default_factory=list)  # même famille, version/format voisin installé

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SetReport:
    path: str
    live_version: str
    tracks: list[str]
    plugins: list[Plugin]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "live_version": self.live_version,
            "tracks": self.tracks,
            "plugins": [p.to_dict() for p in self.plugins],
            "errors": self.errors,
        }
