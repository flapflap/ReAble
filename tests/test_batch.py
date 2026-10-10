from pathlib import Path

import pytest

from reable import api
from reable.batch import ConvertOptions, pick_target
from reable.inventory import Inventory
from reable.model import Plugin

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


def P(name, fmt="VST2"):
    return Plugin(track="T", chain_path="", format=fmt, name=name)


def test_pick_target_prefers_same_name_then_latest_family_with_template():
    inv = Inventory(available=True, vst3_names={"kontakt", "kontakt 7", "kontakt 8", "massive"})
    opts = ConvertOptions()
    assert pick_target(P("Massive"), inv, opts) == "massive"
    assert pick_target(P("Kontakt 5"), inv, opts) == "kontakt 8"
    # « kontakt » (nom exact) n'a pas de gabarit : on retombe sur le plus récent qui en a un
    assert pick_target(P("Kontakt"), inv, opts, {"kontakt 7": ("x", (1,), "Kontakt 7")}) == "kontakt 7"
    assert pick_target(P("FabFilter Pro-Q 2"), inv, opts) is None        # famille non gérée
    assert pick_target(P("Kontakt 5"), Inventory(available=True), opts) is None  # rien d'installé


@needs_set
def test_propose_and_convert(tmp_path):
    a = api.analyze(SET)
    only_missing = api.propose(a, ConvertOptions())
    assert only_missing == []                                    # Massive X AU est installé : rien à faire
    opts = ConvertOptions(only_missing=False, out_dir=tmp_path, rename_template="{track} [{from}→{to}]")
    items = api.propose(a, opts)
    assert [(i.plugin, i.source_format, i.status) for i in items] == [("Massive X", "AU", "convertible")]
    res = api.convert(a, opts, items)
    assert items[0].status == "converti" and len(res.written) == 1
    out = Path(res.written[0])
    assert out.parent == tmp_path and out.name.endswith("[ReAble].als")
    dst, r = api.restore(out, tmp_path)
    assert dst is not None and r.restored == 1 and "Restauré" in dst.name


@needs_set
def test_original_never_overwritten(tmp_path):
    import hashlib
    before = hashlib.sha256(SET.read_bytes()).hexdigest()
    a = api.analyze(SET)
    api.convert(a, ConvertOptions(only_missing=False, out_dir=tmp_path))
    assert hashlib.sha256(SET.read_bytes()).hexdigest() == before


def test_resolve_output_policies(tmp_path):
    from reable.batch import resolve_output
    dst = tmp_path / "A [ReAble].als"
    assert resolve_output(dst, "skip") == dst                # n'existe pas : on écrit
    dst.write_bytes(b"x")
    assert resolve_output(dst, "skip") is None               # existe : on ne refait pas
    assert resolve_output(dst, "overwrite") == dst
    assert resolve_output(dst, "number").name == "A [ReAble] 2.als"
    (tmp_path / "A [ReAble] 2.als").write_bytes(b"x")
    assert resolve_output(dst, "number").name == "A [ReAble] 3.als"


@needs_set
def test_convert_twice_skips_the_second_time(tmp_path):
    a = api.analyze(SET)
    opts = ConvertOptions(only_missing=False, out_dir=tmp_path)
    assert len(api.convert(a, opts).written) == 1
    again = api.convert(a, opts)
    assert again.written == [] and [i.status for i in again.items] == ["ignoré"]
