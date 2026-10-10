"""Met src/ dans le path pour que pytest marche même sans pip install -e."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


import json

import pytest


@pytest.fixture(autouse=True)
def _isolated_registry(tmp_path, monkeypatch):
    """Chaque test voit un dossier utilisateur vide + les définitions de test (copie du dépôt de définitions)."""
    home = tmp_path / "reable-home"
    home.mkdir()
    fixtures = Path(__file__).resolve().parent / "definitions_fixture"
    (home / "settings.json").write_text(json.dumps({"definitions_dirs": [str(fixtures)]}), encoding="utf-8")
    monkeypatch.setenv("REABLE_HOME", str(home))
