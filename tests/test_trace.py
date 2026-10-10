from pathlib import Path

import pytest

from reable import alsfile, trace
from reable.extract import extract
from reable.rewrite import check_tree, rewrite_file

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


def test_note_roundtrip_keeps_user_text():
    note = trace.build_note("Ma note\nsur deux lignes", {"v": 1, "x": "é"})
    assert note.startswith("Ma note\nsur deux lignes")
    assert trace.parse_note(note) == {"v": 1, "x": "é"}
    assert trace.strip_note(note) == "Ma note\nsur deux lignes"
    # reconstruire ne duplique pas le bloc
    again = trace.build_note(note, {"v": 2})
    assert again.count(trace.BEGIN) == 1 and trace.parse_note(again) == {"v": 2}


def test_parse_note_absent_or_broken():
    assert trace.parse_note("") is None
    assert trace.parse_note(f"{trace.BEGIN}\n{{pas du json\n{trace.END}") is None


@needs_set
def test_rewrite_writes_note_and_restore_returns_original(tmp_path):
    dst, res = rewrite_file(SET, "Massive X", tmp_path)
    assert res.converted == 1 and res.devices[0]["source_id"] == "aumu/Ni$H/-NI-"
    tree = alsfile.load(dst)
    ann = next(d for d in tree.getroot().iter("PluginDevice") if trace.parse_note(d.find("Annotation").get("Value")))
    info = trace.parse_note(ann.find("Annotation").get("Value"))
    assert info["source_format"] == "AU" and info["target_name"] == "Massive X" and "original_gz_b64" in info

    r = trace.restore_tree(tree)
    assert r.restored == 1 and r.warnings == []
    out = tmp_path / "restored.als"
    alsfile.save(tree, out, backup=False)
    back, orig = extract(out), extract(SET)
    au_b = next(p for p in back.plugins if p.format == "AU")
    au_o = next(p for p in orig.plugins if p.format == "AU")
    assert au_b.state_full == au_o.state_full and au_b.name == "Massive X"
    assert check_tree(tree.getroot()) == []


@needs_set
def test_restore_without_embedded_original_warns(tmp_path):
    dst, _ = rewrite_file(SET, "Massive X", tmp_path, embed_original=False)
    r = trace.restore_tree(alsfile.load(dst))
    assert r.restored == 0 and r.warnings


@needs_set
def test_big_original_not_embedded_but_restorable_from_original_file(tmp_path):
    from reable.rewrite import rewrite_tree
    tree = alsfile.load(SET)
    res = rewrite_tree(tree, "Massive X", None, "AU", None, True, True, 1_000, "orig.als")   # plafond minuscule
    assert res.converted == 1 and any("trop gros" in w for w in res.warnings)
    dev = next(d for d in tree.getroot().iter("PluginDevice") if trace.parse_note(d.find("Annotation").get("Value")))
    info = trace.parse_note(dev.find("Annotation").get("Value"))
    assert "original_gz_b64" not in info and info["pointee"] and info["source_file"] == "orig.als"
    assert trace.restore_tree(tree).restored == 0                       # sans original : avertissement
    again = trace.restore_tree(tree, alsfile.load(SET))                 # avec le set d'origine : OK
    assert again.restored == 1 and again.warnings == []
