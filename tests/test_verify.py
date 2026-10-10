from pathlib import Path

import pytest

from reable.compare import verify_upgrade

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"


def doc(**vals):
    return {"DSP State": {"Value": {"DSP Elements": {"Value": {"Limiter": {"Value": {k: {"Value": v} for k, v in vals.items()}}}}}}}


def test_verify_upgrade_verdicts():
    default = doc(a=-2, b=0, c=5)
    old = doc(a=-6, b=3, c=5)
    assert verify_upgrade(old, doc(a=-6, b=3, c=5), default)["verdict"] == "repris"
    assert verify_upgrade(old, doc(a=-2, b=0, c=5), default)["verdict"].startswith("non repris")
    assert verify_upgrade(old, doc(a=-6, b=0, c=5), default)["verdict"] == "partiellement repris"
    assert verify_upgrade(doc(a=-2), doc(a=-2), default)["verdict"].startswith("indéterminé")


def test_ui_and_instance_fields_are_ignored():
    default = doc(a=-2)
    old = {**doc(a=-6), "Context State": {"Value": {"PluginUUID": {"Value": "X"}}}}
    new = {**doc(a=-6), "Context State": {"Value": {"PluginUUID": {"Value": "Y"}}}}
    r = verify_upgrade(old, new, default)
    assert r["verdict"] == "repris" and r["common"] == 1
