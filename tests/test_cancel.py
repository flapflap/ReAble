import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from reable import alsfile, api
from reable.batch import ConvertOptions
from reable.jobs import CancelToken, Cancelled, Event

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


def test_cancel_token_raises_only_after_cancel():
    t = CancelToken()
    t.check()                                   # pas annulé : ne fait rien
    t.cancel()
    assert t.cancelled
    with pytest.raises(Cancelled):
        t.check()


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path, monkeypatch):
    tmp_path = tmp_path / "out"
    tmp_path.mkdir()
    tree = ET.ElementTree(ET.fromstring("<Ableton><A/></Ableton>"))
    dst = tmp_path / "x.als"
    alsfile.save(tree, dst, backup=False)
    assert dst.exists() and [p.name for p in tmp_path.iterdir()] == ["x.als"]

    def boom(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr("reable.alsfile.os.replace", boom)
    dst2 = tmp_path / "y.als"
    with pytest.raises(OSError):
        alsfile.save(tree, dst2, backup=False)
    assert not dst2.exists() and [p.name for p in tmp_path.iterdir()] == ["x.als"]      # ni fichier final ni temporaire


def test_save_failure_keeps_previous_content(tmp_path, monkeypatch):
    dst = tmp_path / "x.als"
    alsfile.save(ET.ElementTree(ET.fromstring("<Ableton><Old/></Ableton>")), dst, backup=False)
    before = dst.read_bytes()
    monkeypatch.setattr("reable.alsfile.os.replace", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    with pytest.raises(OSError):
        alsfile.save(ET.ElementTree(ET.fromstring("<Ableton><New/></Ableton>")), dst, backup=False)
    assert dst.read_bytes() == before


@needs_set
def test_analyze_emits_events_and_can_be_cancelled(tmp_path):
    events: list[Event] = []
    a = api.analyze(SET, on_event=events.append)
    assert events and events[0].task == "analyze" and events[-1].status == "done"
    assert events[0].message == "Recherche des projets…" and events[0].total == 0      # retour immédiat, total encore inconnu
    assert all(e.total >= 1 for e in events[1:])

    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        api.analyze(SET, cancel=token)


@needs_set
def test_convert_cancel_before_write_leaves_nothing(tmp_path):
    a = api.analyze(SET)
    opts = ConvertOptions(only_missing=False, out_dir=tmp_path / "out")
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        api.convert(a, opts, cancel=token)
    assert list((tmp_path / "out").rglob("*.als")) == []


@needs_set
def test_convert_events_cover_phases_and_end_with_done(tmp_path):
    a = api.analyze(SET)
    events: list[Event] = []
    res = api.convert(a, ConvertOptions(only_missing=False, out_dir=tmp_path / "out"), on_event=events.append)
    assert len(res.written) == 1
    phases = [e.phase for e in events if e.item]
    for p in ("lecture", "conversion", "contrôle", "écriture"):
        assert p in phases
    assert events[-1].status == "done" and events[-1].index == events[-1].total


@needs_set
def test_cancel_during_conversion_stops_between_phases(tmp_path):
    a = api.analyze(SET)
    token = CancelToken()

    def stop_on_conversion(e: Event):
        if e.phase == "conversion":
            token.cancel()
    with pytest.raises(Cancelled):
        api.convert(a, ConvertOptions(only_missing=False, out_dir=tmp_path / "out"), on_event=stop_on_conversion, cancel=token)
    assert list((tmp_path / "out").rglob("*")) == []                     # rien d'écrit, pas même un dossier ou un temporaire


def test_cancel_token_is_thread_safe():
    t = CancelToken()
    th = threading.Thread(target=t.cancel)
    th.start(); th.join()
    assert t.cancelled


@needs_set
def test_cancel_in_the_middle_of_a_batch_keeps_finished_sets_and_writes_no_partial_file(tmp_path):
    import shutil
    src = tmp_path / "src"
    src.mkdir()
    for n in ("A", "B", "C"):
        shutil.copy(SET, src / f"{n}.als")
    a = api.analyze(src)
    token = CancelToken()
    seen: list[str] = []

    def stop_after_first(e: Event):
        if e.result in ("converti", "réglages par défaut"):
            seen.append(e.item)
            token.cancel()                                   # arrêt demandé dès que le premier set est terminé
    out = tmp_path / "out"
    opts = ConvertOptions(only_missing=False, out_dir=out)
    with pytest.raises(Cancelled):
        api.convert(a, opts, on_event=stop_after_first, cancel=token)
    written = sorted(p.name for p in out.rglob("*") if p.is_file())
    assert len(seen) == 1 and written == [f"{seen[0]} [ReAble].als"]         # le set fini est conservé, les autres absents
    assert not [p for p in out.rglob("*") if p.name.endswith(".tmp")]

    # reprise : seuls les sets manquants sont faits
    again = api.convert(a, opts)
    assert len(again.written) == 2 and sorted(i.status for i in again.items) == ["converti", "converti", "ignoré"]
