"""Compatibilité avec l'ancien nom (PlugRescue) : les copies déjà écrites doivent rester lisibles, restaurables et ignorées."""
import shutil
from pathlib import Path

import pytest

from reable import alsfile, api, registry, trace
from reable.app.logic import AppLogic
from reable.batch import ConvertOptions
from reable.extract import extract

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")

OLD_NOTE = "Ma note\n\n--- PlugRescue ---\n{\"v\": 2, \"x\": 1}\n--- /PlugRescue ---"
OLD_TRACK = "Test\n\n--- PlugRescue (piste) ---\nConverti par PlugRescue\n--- /PlugRescue (piste) ---"


def test_new_notes_use_the_new_name():
    note = trace.build_note("", {"v": 2})
    assert "--- ReAble ---" in note and "PlugRescue" not in note
    assert "--- ReAble (piste) ---" in trace.set_track_block("", "x")


def test_old_notes_are_still_read_and_replaced_without_duplicates():
    assert trace.parse_note(OLD_NOTE) == {"v": 2, "x": 1}
    assert trace.strip_note(OLD_NOTE) == "Ma note"
    rebuilt = trace.build_note(OLD_NOTE, {"v": 3})
    assert rebuilt.count("---") == 4 and "PlugRescue" not in rebuilt and trace.parse_note(rebuilt) == {"v": 3}
    assert trace.strip_track_block(OLD_TRACK) == "Test"
    assert trace.set_track_block(OLD_TRACK, "neuf").count("(piste)") == 2             # une seule paire de marqueurs


def test_output_files_of_both_names_are_never_analysed(tmp_path):
    for n in ("A.als", "A [ReAble].als", "A [PlugRescue].als", "A [PlugRescue G1 Massive].als", "A [Restauré].als"):
        (tmp_path / n).write_bytes(b"x")
    assert [p.name for p in alsfile.find_sets(tmp_path)] == ["A.als"]
    assert alsfile.is_output_file("x [PlugRescue].als") and alsfile.is_output_file("x [ReAble].als")


@needs_set
def test_a_copy_written_under_the_old_name_can_still_be_restored_and_undone(tmp_path, monkeypatch):
    out = tmp_path / "out"
    from reable.rewrite import rewrite_file
    new, res = rewrite_file(SET, "Massive X", out)
    assert new.name.endswith("[ReAble].als")
    # fabrique une copie « à l'ancienne » : même fichier, notes et nom à l'ancienne mode
    tree = alsfile.load(new)
    for dev in tree.getroot().iter("PluginDevice"):
        a = dev.find("Annotation")
        if a is not None:
            a.set("Value", a.get("Value").replace("--- ReAble ---", "--- PlugRescue ---").replace("--- /ReAble ---", "--- /PlugRescue ---"))
    old = out / "Test Plugins AU VST3 [PlugRescue].als"
    alsfile.save(tree, old, backup=False)
    restored, r = api.restore(old, out)
    assert restored is not None and r.restored == 1 and restored.name == "Test Plugins AU VST3 [Restauré].als"
    assert any(p.format == "AU" for p in extract(restored).plugins)                    # le device d'origine est revenu
    # l'annulation reconnaît aussi l'ancien nom
    fake_home = tmp_path / "home"
    (fake_home / ".Trash").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    r = AppLogic().undo([str(old)])
    assert r["moved"] == [str(old)] and not old.exists()


def test_old_user_folder_is_migrated_once(tmp_path, monkeypatch):
    monkeypatch.delenv("REABLE_HOME", raising=False)
    monkeypatch.delenv("PLUGRESCUE_HOME", raising=False)
    base = tmp_path / "Library" / "Application Support"
    (base / "PlugRescue").mkdir(parents=True)
    (base / "PlugRescue" / "settings.json").write_text('{"definitions_dirs": ["/x"]}')
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    d = registry.user_dir()
    assert d == base / "ReAble" and (d / "settings.json").read_text() == '{"definitions_dirs": ["/x"]}'
    assert not (base / "PlugRescue").exists()
    assert registry.user_dir() == base / "ReAble"                                       # idempotent


def test_old_environment_variable_still_works(tmp_path, monkeypatch):
    monkeypatch.delenv("REABLE_HOME", raising=False)
    monkeypatch.setenv("PLUGRESCUE_HOME", str(tmp_path / "ancien"))
    assert registry.user_dir() == tmp_path / "ancien"
