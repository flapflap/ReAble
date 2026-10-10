"""ReAble — retrouver et sauver les plugins manquants des sets Ableton Live."""
__version__ = "0.1.0"


def short_version() -> str:
    """Numéro de version affiché à l'utilisateur : « 0.1 »."""
    return ".".join(__version__.split(".")[:2])
