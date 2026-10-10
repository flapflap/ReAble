import hashlib
from pathlib import Path

import pytest

from reable import alsfile
from reable.extract import extract
from reable.rewrite import check_tree, hex_block, norm_param_name, rewrite_file, rewrite_tree

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


def test_norm_param_name():
    assert norm_param_name("01 LFO Amt") == norm_param_name("LFO Amt") == "lfo amt"
    assert norm_param_name("Morpher - X") == "morpher - x"


def test_hex_block_roundtrip_and_width():
    data = bytes(range(100))
    txt = hex_block(data, "\t\t")
    lines = [ln.strip() for ln in txt.strip("\n").split("\n")]
    assert all(len(ln) <= 80 for ln in lines)
    assert bytes.fromhex("".join(lines)) == data


@needs_set
def test_rewrite_au_to_vst3_keeps_state_and_automation_ids(tmp_path):
    before = hashlib.sha256(SET.read_bytes()).hexdigest()
    dst, res = rewrite_file(SET, "Massive X", tmp_path)
    assert hashlib.sha256(SET.read_bytes()).hexdigest() == before      # original intact
    assert res.converted == 1 and res.warnings == []
    old, new = extract(SET), extract(dst)
    au = next(p for p in old.plugins if p.format == "AU" and p.name == "Massive X")
    moved = new.plugins[0]
    assert moved.format == "VST3" and moved.identifier == "5653544E6924486D6173736976652078"
    assert moved.state_full == au.state_full                            # état identique
    lfo_old = next(x for x in au.parameters if x.name == "LFO Amt")
    lfo_new = next(x for x in moved.parameters if x.name == "01 LFO Amt")
    assert (lfo_new.automation_target, lfo_new.modulation_target) == (lfo_old.automation_target, lfo_old.modulation_target)
    assert check_tree(alsfile.load(dst).getroot()) == []                # Id uniques, pas d'enveloppe orpheline


@needs_set
def test_missing_template_is_reported():
    tree = alsfile.load(SET)
    res = rewrite_tree(tree, "Plugin Inexistant")
    assert res.converted == 0 and res.warnings


def test_head_signature_masks_the_size_field():
    from reable.adapters import head_signature
    # conteneur NI classique : <taille> 00000000 01000000 ...
    a = (20).to_bytes(4, "little") + bytes.fromhex("0000000001000000") + b"\x00" * 8
    b = (30).to_bytes(4, "little") + bytes.fromhex("0000000001000000") + b"\x00" * 18
    assert head_signature(a) == head_signature(b)
    # conteneur Massive X : 02000000 03000000 <taille> ...
    c = bytes.fromhex("0200000003000000") + (8).to_bytes(4, "little") + b"\x00" * 8
    assert head_signature(c) != head_signature(a)
