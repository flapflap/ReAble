"""Tests sur un vrai set. Placer un set de test dans tests/fixtures/ (non versionné)."""
from pathlib import Path

import pytest

from reable.extract import extract

FIX = Path(__file__).parent / "fixtures" / "MySet.xml"


@pytest.mark.skipif(not FIX.exists(), reason="fixture absente")
def test_massive_x_presets():
    r = extract(FIX)
    mx = [p for p in r.plugins if p.name == "Massive X"]
    assert [p.preset_name for p in mx] == ["Bump Force", "Active Jay", "Bubble Counter", "Anime Jungle"]
    assert all(p.format == "AU" for p in mx)
    assert mx[0].state_summary["Macros"]


@pytest.mark.skipif(not FIX.exists(), reason="fixture absente")
def test_clip_envelopes_linked():
    r = extract(FIX)
    last = [p for p in r.plugins if p.name == "Massive X"][-1]
    assert sum(x.clip_envelopes for x in last.parameters) == 3
