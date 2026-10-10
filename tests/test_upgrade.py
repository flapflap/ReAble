import struct
import zlib
from pathlib import Path

import pytest

from reable import alsfile, trace
from reable.adapters import adapt_state, izotope_container
from reable.extract import extract
from reable.rewrite import check_schema, check_tree, rewrite_tree

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


def vst3_state(magic=0x688ad5, version=1, payload=b'{"a": 1}'):
    z = zlib.compress(payload)
    return struct.pack("<IIII", magic, version, len(z) + 4, len(payload)) + z


def vst2_state(magic=0x688ad5, version=1, payload=b'{"a": 1}'):
    inner = vst3_state(magic, version, payload)
    return struct.pack("<I", len(inner) + 3) + inner + b"\x00" * 11       # préfixe + queue de 11 octets


def test_izotope_container_reads_both_layouts():
    for st in (vst3_state(), vst2_state()):
        magic_ver, unc, stream = izotope_container(st)
        assert magic_ver == struct.pack("<II", 0x688ad5, 1) and zlib.decompress(stream) == b'{"a": 1}'
    assert izotope_container(b"\x00" * 40) is None


def test_ozone_vst2_state_becomes_vst3_layout():
    tpl = vst3_state(0x688ade, 3)
    new, why = adapt_state("Ozone 9", vst2_state(), tpl, "transfer")
    assert new == vst3_state(0x688ad5, 1) and why == ""            # même contenu, conteneur VST3, identifiant d'origine
    new, _ = adapt_state("Ozone 9", vst2_state(), tpl, "header")
    assert new == vst3_state(0x688ade, 3)                           # identifiant et version de la cible
    assert adapt_state("Ozone 9", vst2_state(), tpl, "none") == (b"", "")


def test_unknown_format_is_refused():
    new, why = adapt_state("Ozone 6", b"\x01" * 200, vst3_state(), "transfer")
    assert new is None and "non reconnu" in why


@needs_set
def test_keep_device_on_main_track_and_restore():
    tree = alsfile.load(SET)
    root = tree.getroot()
    res = rewrite_tree(tree, "Ozone 10", None, "VST3", None, replace_mode="duplicate_track")
    assert res.converted == 1
    assert res.devices[0]["replace_mode"] == "keep_device"          # piste principale : pas de duplication
    assert any("non dupliquable" in w for w in res.warnings)
    main = root.find("LiveSet/MainTrack")
    devs = [d for d in main.iter("PluginDevice")]
    assert len(devs) == 2
    assert devs[0].find("On/Manual").get("Value") == "true"          # le nouveau, actif, en premier
    assert devs[1].find("On/Manual").get("Value") == "false"         # l'ancien, désactivé
    assert devs[1].find("UserName").get("Value").endswith("[ancien]")
    assert check_tree(root) == []
    assert len({d.get("Id") for d in main.find("DeviceChain/DeviceChain/Devices")}) == len(devs)   # Id de liste uniques
    r = trace.restore_tree(tree)
    assert r.restored == 1
    devs = [d for d in main.iter("PluginDevice")]
    assert len(devs) == 1 and devs[0].find("On/Manual").get("Value") == "true"
    assert not devs[0].find("UserName").get("Value").endswith("[ancien]")
    assert check_tree(root) == []


@needs_set
def test_state_mode_none_gives_empty_state_and_keeps_old_preset_name(tmp_path):
    tree = alsfile.load(SET)
    res = rewrite_tree(tree, "Massive X", None, "AU", None, state_mode="none")
    assert res.converted == 1 and res.devices[0]["preset"] == "Abstract City"   # ancien preset mémorisé
    out = tmp_path / "n.als"
    alsfile.save(tree, out, backup=False)
    p = next(p for p in extract(out).plugins if p.name == "Massive X" and p.state_bytes == 0)
    assert p.format == "VST3"


def test_check_list_ids_flags_duplicates():
    import xml.etree.ElementTree as ET
    from reable.rewrite import check_list_ids
    ok = ET.fromstring('<Devices><PluginDevice Id="0"/><AuPluginDevice Id="1"/></Devices>')
    bad = ET.fromstring('<Devices><PluginDevice Id="0"/><PluginDevice Id="0"/></Devices>')
    assert check_list_ids(ok) == []
    assert check_list_ids(bad) and "Devices" in check_list_ids(bad)[0]


@needs_set
def test_copy_controller_state_option(tmp_path):
    def controller_len(copy):
        tree = alsfile.load(SET)
        rewrite_tree(tree, "Massive X", None, "AU", None, copy_controller_state=copy)
        out = tmp_path / f"c{copy}.als"
        alsfile.save(tree, out, backup=False)
        r = alsfile.load(out).getroot()
        dev = next(d for d in r.iter("PluginDevice") if d.find(".//Vst3PluginInfo/Name") is not None
                   and d.find(".//Vst3PluginInfo/Name").get("Value") == "Massive X"
                   and (d.find(".//ProcessorState").text or "").strip() and d.find("Annotation").get("Value"))
        return len((dev.find(".//ControllerState").text or "").strip()), len((dev.find(".//ProcessorState").text or "").strip())
    assert controller_len(False)[0] == 0
    c, p = controller_len(True)
    assert c > 0 and c == p


def test_ozone_definition_turns_on_controller_copy():
    from reable import registry
    assert registry.definition_of("Ozone 9").copy_controller_state is True
    assert registry.definition_of("Kontakt 5").copy_controller_state is False


def test_ozone_state_transfers_only_from_ozone_9_and_10():
    from reable import registry
    from reable.adapters import effective_mode
    d = registry.definition_of("Ozone 9")
    assert d.status == "validated" and "ozone" in registry.allowed_families()
    assert effective_mode("Ozone 9", "transfer") == ("transfer", "")
    assert effective_mode("iZotope Ozone 9", "header")[0] == "header"
    mode, why = effective_mode("Ozone 8", "transfer")
    assert mode == "none" and "n'est pas repris" in why
    assert effective_mode("iZotope Ozone 7", "transfer")[0] == "none"
    assert effective_mode("Ozone 8", "none") == ("none", "")
    assert effective_mode("Kontakt 5", "transfer") == ("transfer", "")          # sans restriction : toutes les versions
