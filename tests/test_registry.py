import json
import subprocess
from pathlib import Path

import pytest

from reable import registry
from reable.batch import ConvertOptions


def test_builtin_fixture_is_loaded_and_ni_is_validated():
    assert registry.family_of("Kontakt 5") == "kontakt"
    assert registry.family_of("Massive X") == "massive x"
    assert registry.family_of("Nom Inconnu 3") is None
    allowed = registry.allowed_families()
    assert {"kontakt", "massive x", "fm8"} <= allowed
    assert "ozone" in allowed                                                  # validé le 9 oct. 2026 (Ozone 9 → 10)
    assert "neutron" not in allowed and "fabfilter pro-q" not in allowed       # experimental / unsupported : bloqués
    assert ConvertOptions().families == allowed


def test_unvalidated_user_plugin_is_blocked_until_validated():
    registry.add_definition("replika", ["^replika\\b"], "container-copy", "Native Instruments")
    d = registry.definition_of("Replika XT")
    assert d.id == "replika" and d.status == "experimental" and d.source == "utilisateur"
    assert "replika" not in registry.allowed_families()                        # décision : bloqué par défaut
    registry.record_validation("replika", "ko", "transfer", "12.4")
    assert "replika" not in registry.allowed_families()
    d = registry.record_validation("replika", "ok", "header", "12.4", "ouvre sans erreur")
    assert d.status == "validated" and d.preferred_state_mode == "header" and "replika" in registry.allowed_families()
    assert [v["result"] for v in d.validated] == ["ko", "ok"]


def test_user_definition_overrides_shared_one():
    registry.add_definition("kontakt", ["^kontakt\\b"], "none", "Native Instruments", "test local")
    d = registry.definition_of("Kontakt 8")
    assert d.source == "utilisateur" and d.adapter == "none" and d.status == "experimental"


def test_invalid_input_is_rejected():
    with pytest.raises(ValueError):
        registry.add_definition("x", ["a"], "inconnu")
    with pytest.raises(Exception):
        registry.add_definition("x", ["(["], "none")
    with pytest.raises(KeyError):
        registry.record_validation("absent", "ok")


def test_beta_export_is_anonymous():
    registry.set_beta(True)
    registry.add_definition("replika", ["^replika\\b"], "container-copy", "Native Instruments", "/Users/moi/secret")
    registry.record_validation("replika", "ok", "transfer", "12.4", "note privée /Users/moi/Music")
    text = json.dumps(registry.export_bundle(beta=True), ensure_ascii=False)
    for forbidden in ("/Users", "secret", "note privée", "Music"):
        assert forbidden not in text
    doc = json.loads(text)
    assert doc["schema"] == "reable-beta/1" and doc["contributor"].startswith("beta-")
    assert doc["results"][0]["validations"][0]["result"] == "ok"


def test_import_goes_to_shared_layer(tmp_path):
    bundle = tmp_path / "def.json"
    bundle.write_text(json.dumps({"definitions": [{"id": "valhalla", "match": ["^valhalla"], "status": "experimental",
                                                   "adapter": "container-copy"}]}), encoding="utf-8")
    assert registry.import_bundle(bundle) == 1
    assert registry.definition_of("ValhallaSupermassive").source == "partagé"
    beta = tmp_path / "beta.json"
    beta.write_text(json.dumps({"schema": "reable-beta/1", "results": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        registry.import_bundle(beta)


def test_sync_clones_then_updates_a_definitions_repo(tmp_path, monkeypatch):
    src = tmp_path / "defs-origin"
    (src / "definitions" / "acme").mkdir(parents=True)
    f = src / "definitions" / "acme" / "synth.json"
    f.write_text(json.dumps({"definitions": [{"id": "acme synth", "match": ["^acme"], "status": "validated",
                                              "adapter": "container-copy", "validated": [{"live": "12", "date": "2026-10-09", "variant": "transfer"}]}]}))
    git = lambda *a, cwd=src: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
    git("init", "-q", "-b", "main"); git("add", "."); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    ok, msg = registry.sync(str(src))
    assert ok, msg
    assert registry.family_of("Acme Synth 2") == "acme synth" and "acme synth" in registry.allowed_families()
    f.write_text(f.read_text().replace('"validated"', '"experimental"', 1))   # mise à jour côté dépôt
    git("add", "."); git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "maj")
    ok, _ = registry.sync(str(src))
    assert ok and "acme synth" not in registry.allowed_families()


def test_sync_without_url_explains_what_to_do(monkeypatch):
    monkeypatch.setattr(registry, "DEFAULT_LIBRARY_URL", "")
    ok, msg = registry.sync()
    assert not ok and "--repo-url" in msg
