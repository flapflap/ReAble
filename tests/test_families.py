from reable.families import family_of
from reable.inventory import Inventory, check
from reable.model import Plugin


def test_family_detection():
    assert family_of("Kontakt 5") == "kontakt"
    assert family_of("Ozone 8") == "ozone"
    assert family_of("iZotope Ozone 7 Maximizer") == "ozone"
    assert family_of("FabFilter Pro-Q 2 (Mono)") == "fabfilter pro-q"
    assert family_of("Play") == "play"
    assert family_of("Playground") is None


def test_missing_plugin_with_family_installed():
    inv = Inventory(available=True, vst3_names={"kontakt 8", "kontakt 7"}, vst2_names={"kontakt"})
    p = Plugin(track="T", chain_path="", format="VST2", name="Kontakt 5")
    check([p], inv)
    assert p.install_status == "manquant"
    assert sorted(p.family_installed) == ["kontakt", "kontakt 7", "kontakt 8"]


def test_truly_missing_has_no_family():
    inv = Inventory(available=True, vst3_names={"kontakt 8"})
    p = Plugin(track="T", chain_path="", format="VST2", name="FabFilter Pro-Q 2")
    check([p], inv)
    assert p.family_installed == []
