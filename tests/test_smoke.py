from reable.inventory import Inventory, check
from reable.model import Plugin


def test_inventory_unavailable_gives_unknown():
    p = Plugin(track="T", chain_path="", format="VST3", name="X")
    check([p], Inventory(available=False))
    assert p.install_status == "inconnu"


def test_find_sets_ignores_reable_outputs(tmp_path):
    from reable import alsfile
    for n in ("A.als", "A [ReAble].als", "A [ReAble G1].als", "A [Restauré].als", "A.backup-1.als"):
        (tmp_path / n).write_bytes(b"x")
    assert [p.name for p in alsfile.find_sets(tmp_path)] == ["A.als"]
