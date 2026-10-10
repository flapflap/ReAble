from pathlib import Path

import pytest

from reable import alsfile, trace
from reable.batch import ConvertOptions, load_profile, render_name, save_profile
from reable.extract import extract
from reable.rewrite import check_tree, rewrite_tree

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


def test_render_name_variables_and_empty_parts():
    v = {"track": "Lead", "from": "AU", "to": "VST3", "preset": "Abstract City"}
    assert render_name("{track} [{from}→{to}]", v) == "Lead [AU→VST3]"
    assert render_name("{track} — {preset}", v) == "Lead — Abstract City"
    assert render_name("{track} — {preset}", {**v, "preset": ""}) == "Lead"
    assert render_name("{track} [{preset}]", {**v, "preset": ""}) == "Lead"
    assert render_name("{preset}", v) == "Abstract City"


def test_profile_roundtrip(tmp_path):
    o = ConvertOptions(replace_mode="duplicate_track", mapping={"Kontakt 5": "Kontakt 8"},
                       skip_plugins=["Play"], rename_template="{track} — {preset}")
    save_profile(o, tmp_path / "p.json")
    back = load_profile(tmp_path / "p.json")
    assert back == o and back.families == o.families


@needs_set
def test_duplicate_track_keeps_original_muted_and_converts_the_copy():
    tree = alsfile.load(SET)
    root = tree.getroot()
    n_before = len(list(root.iter("MidiTrack")))
    res = rewrite_tree(tree, "Massive X", None, "AU", None, replace_mode="duplicate_track")
    assert res.converted == 1 and res.warnings == []
    tracks = list(root.iter("MidiTrack"))
    assert len(tracks) == n_before + 1
    orig, copy = tracks[0], tracks[1]
    assert orig.find("DeviceChain/Mixer/Speaker/Manual").get("Value") == "false"      # originale mutée
    assert orig.find("Name/UserName").get("Value").endswith("[original]")
    assert copy.get("Id") != orig.get("Id")
    assert copy.find("DeviceChain/Mixer/Speaker/Manual").get("Value") == "true"
    assert [d.tag for d in orig.iter() if d.tag in ("AuPluginDevice", "PluginDevice")] == ["AuPluginDevice"]
    assert [d.tag for d in copy.iter() if d.tag in ("AuPluginDevice", "PluginDevice")] == ["PluginDevice"]
    assert check_tree(root) == []                                                      # Id uniques


@needs_set
def test_duplicate_track_restore_removes_copy_and_unmutes(tmp_path):
    tree = alsfile.load(SET)
    rewrite_tree(tree, "Massive X", None, "AU", None, replace_mode="duplicate_track")
    r = trace.restore_tree(tree)
    assert r.restored == 1 and r.warnings == []
    root = tree.getroot()
    first = next(root.iter("MidiTrack"))
    assert first.find("DeviceChain/Mixer/Speaker/Manual").get("Value") == "true"
    assert not first.find("Name/UserName").get("Value").endswith("[original]")
    out = tmp_path / "r.als"
    alsfile.save(tree, out, backup=False)
    assert [(p.format, p.name) for p in extract(out).plugins if p.name == "Massive X"] == [("AU", "Massive X"), ("VST3", "Massive X")]


@needs_set
def test_keep_device_on_instrument_falls_back_to_duplicate_track():
    tree = alsfile.load(SET)
    res = rewrite_tree(tree, "Massive X", None, "AU", None, replace_mode="keep_device")
    assert res.converted == 1
    assert res.devices[0]["replace_mode"] == "duplicate_track"     # un instrument ne peut pas être doublé sur la piste


def test_track_name_falls_back_to_effective_name():
    import xml.etree.ElementTree as ET
    from reable.rewrite import _set_track_name
    t = ET.fromstring('<MidiTrack><Name><EffectiveName Value="1-Kontakt"/><UserName Value=""/></Name></MidiTrack>')
    _set_track_name(t, lambda n: n + " [original]")
    assert t.find("Name/UserName").get("Value") == "1-Kontakt [original]"
    assert t.find("Name/EffectiveName").get("Value") == "1-Kontakt [original]"


def test_is_pointee_covers_all_global_id_tags():
    from reable.rewrite import is_pointee
    for tag in ("Pointee", "AutomationTarget", "ModulationTarget", "VolumeModulationTarget",
                "TranspositionModulationTarget", "ControllerTargets.0", "ControllerTargets.130"):
        assert is_pointee(tag), tag
    for tag in ("PluginFloatParameter", "ClipSlot", "MidiTrack", "NamedRemoteableKeyMidi", "TrackSendHolder"):
        assert not is_pointee(tag), tag


@needs_set
def test_duplicate_track_produces_no_duplicate_global_ids_in_any_tag():
    """Régression : Live refusait le set (« non-unique Pointee IDs ») à cause des ControllerTargets.N dupliqués."""
    import collections as C
    from reable.rewrite import is_pointee
    tree = alsfile.load(SET)
    rewrite_tree(tree, "Massive X", None, "AU", None, replace_mode="duplicate_track")
    ids = C.Counter(e.get("Id") for e in tree.getroot().iter() if is_pointee(e.tag) and e.get("Id"))
    assert [k for k, n in ids.items() if n > 1] == []


def test_routing_target_never_gets_an_id():
    from reable.rewrite import is_pointee
    assert not is_pointee("Target")


@needs_set
def test_no_element_gains_an_id_attribute():
    """Régression : Live refuse un attribut Id inconnu (« Unknown attribute 'Id' »), ex. sur <Target Value=…/>."""
    def with_id(root):
        return sorted({e.tag for e in root.iter() if e.get("Id") is not None})
    before = with_id(alsfile.load(SET).getroot())
    for mode in ("replace", "duplicate_track"):
        tree = alsfile.load(SET)
        rewrite_tree(tree, "Massive X", None, "AU", None, replace_mode=mode)
        assert set(with_id(tree.getroot())) <= set(before) | {"PluginDevice", "Vst3PluginInfo", "Vst3Preset"}, mode


def test_check_schema_flags_unknown_attribute():
    import xml.etree.ElementTree as ET
    from reable.rewrite import attribute_schema, check_schema
    ref = ET.fromstring('<A><Target Value="x"/></A>')
    bad = ET.fromstring('<A><Target Value="x" Id="5"/></A>')
    assert check_schema(ref, attribute_schema(ref)) == []
    assert check_schema(bad, attribute_schema(ref)) == ["Attribut inconnu : <Target> ['Id']"]


@needs_set
def test_conversion_passes_schema_check():
    tree = alsfile.load(SET)
    res = rewrite_tree(tree, "Massive X", None, "AU", None, replace_mode="duplicate_track")
    assert res.converted == 1 and not [w for w in res.warnings if w.startswith("Attribut inconnu")]


def test_render_lines_drops_lines_with_empty_variables():
    from reable.batch import render_lines
    t = "A : {a}\nPreset : {p}\nB : {b}"
    assert render_lines(t, {"a": "1", "p": "", "b": "3"}) == "A : 1\nB : 3"


def test_track_block_keeps_user_text_and_is_idempotent():
    note = trace.set_track_block("Test\n", "ligne 1")
    assert note.startswith("Test") and note.count(trace.TRACK_BEGIN) == 1
    assert trace.set_track_block(note, "ligne 2").count(trace.TRACK_BEGIN) == 1
    assert trace.strip_track_block(note) == "Test"


@needs_set
@pytest.mark.parametrize("mode", ["replace", "duplicate_track"])
def test_track_info_written_and_cleared_by_restore(mode, tmp_path):
    from reable import api
    a = api.analyze(SET)
    opts = ConvertOptions(only_missing=False, replace_mode=mode, out_dir=tmp_path)
    res = api.convert(a, opts)
    root = alsfile.load(res.written[0]).getroot()
    notes = [t.find("Name/Annotation").get("Value") for t in root.iter("MidiTrack")]
    assert any("Converti par ReAble" in n and "Massive X : AU → VST3" in n for n in notes)
    assert ("mutée" in " ".join(notes)) == (mode == "duplicate_track")
    dst, r = api.restore(res.written[0], tmp_path)
    back = alsfile.load(dst).getroot()
    assert all("ReAble" not in t.find("Name/Annotation").get("Value") for t in back.iter("MidiTrack"))
