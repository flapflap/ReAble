from reable.compare import compare_states
from reable.model import Plugin


def P(fmt, full, size=10):
    return Plugin(track="T", chain_path="", format=fmt, name="X", state_full=full, state_bytes=size)


def test_identical_decoded_states():
    r = compare_states(P("VST2", {"a": 1, "b": 2}), P("VST3", {"a": 1, "b": 2}))
    assert r["verdict"] == "identique" and r["diff_keys"] == []


def test_similar_states_list_differences():
    r = compare_states(P("VST2", {"a": 1, "b": 2}), P("VST3", {"a": 1, "b": 3}))
    assert r["verdict"] == "similaire" and r["diff_keys"] == ["/b"]


def test_empty_state():
    r = compare_states(P("VST2", {}, size=0), P("VST3", {"a": 1}))
    assert r["verdict"] == "état vide"


def test_no_decoder_falls_back_to_size():
    assert compare_states(P("VST2", {}, 100), P("VST3", {}, 100))["verdict"] == "identique"
    assert compare_states(P("VST2", {}, 100), P("VST3", {}, 4000))["verdict"] == "différent"


def test_nested_states_are_flattened():
    a = {"j": {"x": {"v": 1}, "y": [1, 2]}}
    r = compare_states(P("VST2", a), P("VST3", {"j": {"x": {"v": 2}, "y": [1, 2]}}))
    assert r["verdict"] == "similaire" and r["same_schema"] and r["diff_keys"] == ["/j/x/v"]
