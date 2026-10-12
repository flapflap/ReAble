import http.client
import json
import shutil
import time
from pathlib import Path

import pytest

from reable.app.logic import AppLogic, group_items, summarize
from reable.app.server import App
from reable.batch import PlanItem

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


@pytest.fixture
def app():
    a = App(port=0)
    a.start()
    yield a
    a.stop()


def call(app, method, path, body=None, token=True, host=None, origin=None):
    c = http.client.HTTPConnection("127.0.0.1", app.port, timeout=10)
    h = {"Content-Type": "application/json"}
    if token is True:
        h["X-ReAble-Token"] = app.token
    elif token:
        h["X-ReAble-Token"] = token
    if host:
        h["Host"] = host
    if origin:
        h["Origin"] = origin
    c.request(method, path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    try:
        return r.status, json.loads(raw)
    except ValueError:
        return r.status, raw


def wait_job(app, job_id, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, snap = call(app, "GET", f"/api/jobs/{job_id}")
        if snap["state"] not in ("running", "stopping"):
            return snap
        time.sleep(0.05)
    raise AssertionError("tâche trop longue")


def test_api_requires_the_token(app):
    assert call(app, "GET", "/api/state", token=False)[0] == 401
    assert call(app, "GET", "/api/state", token="mauvais")[0] == 401
    assert call(app, "GET", "/api/state")[0] == 200


def test_rejects_foreign_host_and_origin(app):
    assert call(app, "GET", "/api/state", host="evil.example.com")[0] == 403          # DNS rebinding
    assert call(app, "GET", "/api/state", origin="https://evil.example.com")[0] == 403  # appel depuis un site web
    assert call(app, "GET", "/api/state", origin=f"http://127.0.0.1:{app.port}")[0] == 200


def test_static_page_embeds_the_token_and_blocks_path_traversal(app):
    st, body = call(app, "GET", "/", token=False)
    assert st == 200 and app.token.encode() in body and b"__TOKEN__" not in body
    assert call(app, "GET", "/../logic.py", token=False)[0] in (403, 404)
    assert call(app, "GET", "/%2e%2e/logic.py", token=False)[0] in (403, 404)
    assert call(app, "GET", "/tokens.css", token=False)[0] == 200


def test_unknown_route_and_bad_body(app):
    assert call(app, "POST", "/api/nope", {})[0] == 404
    assert call(app, "POST", "/api/analyze", {"path": "/chemin/qui/n/existe/pas"})[0] == 400


def test_group_items_and_summary():
    def it(plugin, status, reason="", target="Ozone 10", fmt="VST2", path="/a.als"):
        return PlanItem(path, plugin, fmt, target, 1, "", status, reason)
    items = [it("Ozone 9", "convertible", path="/1.als"), it("Ozone 9", "convertible", path="/2.als"),
             it("Ozone 8", "convertible", "l'état de « Ozone 8 » n'est pas repris par la version cible", path="/3.als"),
             it("X", "bloqué", "set trop ancien (avant Live 11)", path="/4.als"),
             it("FabFilter", "bloqué", "pas de plugin VST3 compatible installé", target="", path="/5.als"),
             it("Y", "ignoré", "déjà converti", path="/6.als")]
    g = group_items(items)
    assert [x["kind"] for x in g] == ["validated", "default", "old", "unsupported", "done"]
    assert g[0]["count"] == 2 and g[0]["selectable"] and not g[2]["selectable"]
    assert summarize(g) == {"to_convert": 3, "notes_only": 0, "actionable": 3, "default_settings": 1, "too_old": 1, "template_missing": 0, "templates_needed": [],
                            "unsupported_plugins": 1, "already_done": 1}


@needs_set
def test_analyze_then_convert_end_to_end(app, tmp_path):
    folder = tmp_path / "projets"
    folder.mkdir()
    shutil.copy(SET, folder / "Test.als")
    st, r = call(app, "POST", "/api/options", {"only_missing": False, "out_dir": str(tmp_path / "out")})
    assert st == 200
    st, r = call(app, "POST", "/api/analyze", {"path": str(folder)})
    assert st == 202
    snap = wait_job(app, r["job"])
    assert snap["state"] == "done" and snap["last"]["status"] == "done"
    _, state = call(app, "GET", "/api/state")
    assert state["analyzed"] and state["summary"]["to_convert"] == 1
    g = [x for x in state["groups"] if x["selectable"]][0]
    st, r = call(app, "POST", "/api/convert", {"groups": [g["id"]]})
    assert st == 202
    snap = wait_job(app, r["job"])
    assert snap["state"] == "done"
    assert [p.name for p in (tmp_path / "out").rglob("*.als")] == ["Test [ReAble].als"]
    # le journal est lisible par morceaux
    _, tail = call(app, "GET", f"/api/jobs/{r['job']}?since={snap['total_events'] - 1}")
    assert len(tail["events"]) == 1


@needs_set
def test_stop_through_the_api_and_one_job_at_a_time(app, tmp_path):
    folder = tmp_path / "projets"
    folder.mkdir()
    for n in range(40):
        shutil.copy(SET, folder / f"S{n:02d}.als")
    st, r = call(app, "POST", "/api/analyze", {"path": str(folder)})
    job = r["job"]
    assert call(app, "POST", "/api/analyze", {"path": str(folder)})[0] == 409          # une seule tâche à la fois
    assert call(app, "POST", f"/api/jobs/{job}/stop", {})[1] == {"stopping": True}
    snap = wait_job(app, job)
    assert snap["state"] in ("stopped", "done")                                          # arrêté (ou déjà fini si très rapide)
    assert call(app, "POST", f"/api/jobs/{job}/stop", {})[1] == {"stopping": False}      # déjà terminé


def test_options_are_validated_and_persisted(app):
    st, state = call(app, "POST", "/api/options", {"rename_template": "{track} — {preset}", "replace_mode": "replace"})
    assert st == 200 and state["options"]["rename_template"] == "{track} — {preset}"
    assert AppLogic().load_options().rename_template == "{track} — {preset}"            # relu depuis le disque


@needs_set
def test_undo_moves_only_reable_copies_to_trash(app, tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    (fake_home / ".Trash").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    folder = tmp_path / "projets"
    folder.mkdir()
    shutil.copy(SET, folder / "Test.als")
    call(app, "POST", "/api/options", {"only_missing": False})
    wait_job(app, call(app, "POST", "/api/analyze", {"path": str(folder)})[1]["job"])
    g = [x for x in call(app, "GET", "/api/state")[1]["groups"] if x["selectable"]][0]
    snap = wait_job(app, call(app, "POST", "/api/convert", {"groups": [g["id"]]})[1]["job"])
    written = snap["result"]["written"]
    assert len(written) == 1 and Path(written[0]).exists()
    # le chemin de chaque copie est dans les événements (nécessaire pour annuler après un arrêt)
    assert any(e["path"] == written[0] for e in snap["events"])
    # un fichier qui n'est pas une copie ReAble est refusé
    original = folder / "Test.als"
    st, r = call(app, "POST", "/api/undo", {"files": [str(original)]})
    assert r["moved"] == [] and r["refused"] == [str(original)] and original.exists()
    st, r = call(app, "POST", "/api/undo", {"files": written})
    assert r["moved"] == written and not Path(written[0]).exists()
    assert [p.name for p in (fake_home / ".Trash").iterdir()] == ["Test [ReAble].als"]


def test_app_default_keeps_the_original_track():
    assert AppLogic().opts.replace_mode == "duplicate_track"


def test_counts_are_per_project_not_per_plugin():
    from reable.app.logic import _counts

    def it(path, status, reason=""):
        return PlanItem(path, "P", "VST2", "T", 1, "", status, reason)
    c = _counts([it("/a", "converti"), it("/a", "converti", "n'est pas repris"), it("/b", "converti", "n'est pas repris"),
                 it("/c", "ignoré")])
    assert c == {"converted": 1, "default": 1, "skipped": 1, "errors": 0, "annotated": 0}      # 3 projets, pas 4 conversions


def test_missing_template_is_its_own_group_not_unsupported():
    def it(plugin, target, reason, status="bloqué", path="/a.als"):
        return PlanItem(path, plugin, "VST2", target, 1, "", status, reason)
    items = [it("Ozone 8", "Ozone 10", "aucun gabarit VST3 « Ozone 10 » dans les sets analysés", path="/1.als"),
             it("Ozone 9", "Ozone 10", "aucun gabarit VST3 « Ozone 10 » dans les sets analysés", path="/2.als"),
             it("FabFilter", "", "pas de plugin VST3 compatible installé", path="/3.als")]
    g = group_items(items)
    assert [x["kind"] for x in g] == ["template", "unsupported"]
    assert g[0]["title"] == "Gabarit manquant : Ozone 10" and g[0]["count"] == 2 and not g[0]["selectable"]
    sm = summarize(g)
    assert sm["template_missing"] == 2 and sm["templates_needed"] == ["Ozone 10"] and sm["unsupported_plugins"] == 1


def test_one_group_per_conversion_whatever_the_source_format():
    def it(fmt, path):
        return PlanItem(path, "Ozone 8", fmt, "Ozone 10", 1, "", "convertible", "l'état de « Ozone 8 » n'est pas repris")
    g = group_items([it("VST2", "/1.als"), it("VST3", "/2.als"), it("VST3", "/3.als")])
    assert len(g) == 1 and g[0]["count"] == 3 and g[0]["title"] == "Ozone 8 → Ozone 10"
    logic = AppLogic()
    logic.items = [it("VST2", "/1.als"), it("VST3", "/2.als")]
    assert len(logic._selected_items([g[0]["id"]])) == 2            # cocher le groupe sélectionne les deux sources


@needs_set
def test_projects_with_the_same_name_in_different_folders_get_distinct_keys(tmp_path):
    """Régression : deux projets de même nom (dossiers différents) étaient confondus par l'interface (copies « perdues »)."""
    from reable import api
    from reable.batch import ConvertOptions
    from reable.jobs import Event
    for d in ("A", "B"):
        (tmp_path / "src" / d).mkdir(parents=True)
        shutil.copy(SET, tmp_path / "src" / d / "Meme nom.als")
    a = api.analyze(tmp_path / "src")
    events: list[Event] = []
    res = api.convert(a, ConvertOptions(only_missing=False, out_dir=tmp_path / "out"), on_event=events.append)
    done = [e for e in events if e.result in ("converti", "réglages par défaut")]
    assert len(done) == 2 and len({e.key for e in done}) == 2 and {e.item for e in done} == {"Meme nom"}
    assert sorted(e.path for e in done) == sorted(res.written) and all(e.key.endswith("Meme nom.als") for e in done)


def test_plugin_display_names_are_readable(app):
    from reable.registry import pretty_name
    assert pretty_name("fabfilter pro-q") == "FabFilter Pro-Q"
    assert pretty_name("massive x") == "Massive X"
    assert pretty_name("fm8") == "FM8"
    _, plugins = call(app, "GET", "/api/plugins")
    assert all(p["name"] and p["name"][0].isupper() for p in plugins)


def test_plugin_test_needs_an_analysis_and_a_known_plugin(app):
    st, r = call(app, "POST", "/api/plugins/test", {"id": "neutron"})
    assert st == 400 and "Analysez" in r["error"]
    st, r = call(app, "POST", "/api/plugins/test", {"id": "inconnu"})
    assert st == 400
    st, r = call(app, "POST", "/api/plugins/test", {"id": "play"})
    assert st == 400 and "rien à tester" in r["error"]


@needs_set
def test_plugin_test_writes_one_copy_outside_the_projects_then_validates(app, tmp_path):
    folder = tmp_path / "projets"
    folder.mkdir()
    shutil.copy(SET, folder / "Test.als")
    call(app, "POST", "/api/options", {"only_missing": False})
    wait_job(app, call(app, "POST", "/api/analyze", {"path": str(folder)})[1]["job"])
    st, r = call(app, "POST", "/api/plugins/test", {"id": "massive x"})
    assert st == 200 and Path(r["path"]).exists() and "tests" in r["path"]
    assert not list(folder.glob("*ReAble*"))                   # rien n'est écrit à côté des originaux
    st, d = call(app, "POST", "/api/plugins/validate", {"id": "massive x", "result": "ok", "note": "ouvre bien"})
    assert st == 200 and d["status"] == "validated" and d["validated"][-1]["note"] == "ouvre bien"
    assert call(app, "POST", "/api/plugins/validate", {"id": "massive x", "result": "peut-être"})[0] == 400


def test_beta_switch_and_version(app):
    assert call(app, "GET", "/api/beta")[1]["enabled"] is False
    assert call(app, "POST", "/api/beta", {"enabled": True})[1]["enabled"] is True
    assert call(app, "GET", "/api/beta")[1]["enabled"] is True
    _, state = call(app, "GET", "/api/state")
    from reable import __version__
    assert state["version"] == __version__ and state["version"].startswith("0.1")


def test_open_url_only_accepts_the_reable_repository(app, monkeypatch):
    import subprocess
    opened = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: opened.append(cmd))
    assert call(app, "POST", "/api/open-url", {"url": "https://github.com/flapflap/ReAble/issues/new"})[0] == 200
    assert call(app, "POST", "/api/open-url", {"url": "https://github.com/flapflap/ReAble"})[0] == 200
    assert call(app, "POST", "/api/open-url", {"url": "https://exemple.com"})[0] == 400
    assert call(app, "POST", "/api/open-url", {"url": "https://github.com/flapflap/ReAble-evil/x"})[0] == 400
    assert [c[1] for c in opened] == ["https://github.com/flapflap/ReAble/issues/new", "https://github.com/flapflap/ReAble"]


def test_native_window_messages_are_picked_up_once_by_the_page(app):
    app.logic.push_ui({"type": "about"})
    app.logic.push_ui({"type": "drop", "data": {"path": "/tmp"}})
    _, r = call(app, "GET", "/api/ui-events")
    assert [e["type"] for e in r["events"]] == ["about", "drop"]
    assert call(app, "GET", "/api/ui-events")[1]["events"] == []


def test_missing_report_is_empty_before_any_analysis(app):
    st, r = call(app, "GET", "/api/missing-report")
    assert st == 200 and r == {"folder": None, "rows": []}


def test_verdicts_say_what_to_do_for_each_missing_plugin():
    from types import SimpleNamespace as NS
    from reable.app.logic import AppLogic
    plugin = lambda name, fam=(): NS(name=name, family_installed=list(fam))
    convert = NS(status="convertible", reason="", target_name="Massive X")
    assert AppLogic._verdict(convert, plugin("Massive"))[0] == "convert"
    assert AppLogic._verdict(NS(status="bloqué", reason="set trop ancien (avant Live 11)", target_name=""), plugin("Massive"))[0] == "old"
    assert AppLogic._verdict(NS(status="bloqué", reason="aucun gabarit VST3 « x »", target_name=""), plugin("Massive"))[0] == "template"
    assert AppLogic._verdict(None, plugin("Un Plugin Inconnu"))[0] == "unknown"
    assert AppLogic._verdict(NS(status="bloqué", reason="pas de plugin VST3 compatible", target_name=""), plugin("Play"))[0] == "blocked"


@needs_set
def test_missing_report_lists_projects_and_plugins_after_an_analysis(app, tmp_path):
    folder = tmp_path / "projets"
    folder.mkdir()
    shutil.copy(SET, folder / "Test.als")
    wait_job(app, call(app, "POST", "/api/analyze", {"path": str(folder)})[1]["job"])
    _, r = call(app, "GET", "/api/missing-report")
    assert r["folder"] == str(folder)
    for row in r["rows"]:
        assert row["projects"] == ["Test"] and row["count"] == 1 and row["verdict"]


def test_missing_report_works_with_plan_items_of_any_format(app, monkeypatch):
    """Régression : le rapport lisait un attribut inexistant de PlanItem (format au lieu de source_format)."""
    from types import SimpleNamespace as NS
    from reable.batch import PlanItem
    plugin = NS(name="Play", format="VST3", manufacturer="EastWest", install_status="manquant", family_installed=[])
    app.logic.analysis = NS(root=Path("/tmp/x"), reports=[NS(path="/tmp/x/Set.als", plugins=[plugin])])
    app.logic.items = [PlanItem("/tmp/x/Set.als", "Play", "VST3", status="bloqué", reason="pas de plugin VST3 compatible")]
    _, r = call(app, "GET", "/api/missing-report")
    assert r["rows"][0]["plugin"] == "Play" and r["rows"][0]["kind"] == "blocked" and r["rows"][0]["projects"] == ["Set"]


def test_other_plugin_detection():
    from reable.adapters import effective_mode, is_other_plugin
    assert is_other_plugin("Play", "Opus") and is_other_plugin("Un Inconnu", "Opus")
    assert not is_other_plugin("Ozone 9", "Ozone 10") and not is_other_plugin("Kontakt 5", "Kontakt 8")
    mode, why = effective_mode("Play", "transfer", "Opus")
    assert mode == "none" and "n'est pas repris par « Opus »" in why and "réglages par défaut" in why
    assert effective_mode("Kontakt 5", "transfer", "Kontakt 8")[0] == "transfer"


def test_replacement_needs_a_known_candidate_and_can_be_removed(app):
    st, r = call(app, "POST", "/api/replacement", {"plugin": "Play", "target": "Opus"})
    assert st == 400 and "inconnu" in r["error"]
    assert call(app, "POST", "/api/replacement", {"plugin": "Play", "target": ""})[0] == 200      # retrait d'un remplacement absent : sans effet
    assert call(app, "GET", "/api/replacement-candidates")[1] == {"candidates": []}


@needs_set
def test_replacement_by_another_plugin_gives_default_settings_group(app, tmp_path, monkeypatch):
    import reable.adapters as adapters
    monkeypatch.setattr(adapters, "is_other_plugin", lambda a, b: True)     # le set de test n'a qu'un plugin : on simule « autre plugin »
    folder = tmp_path / "projets"
    folder.mkdir()
    shutil.copy(SET, folder / "Test.als")
    call(app, "POST", "/api/options", {"only_missing": False, "out_dir": str(tmp_path / "out")})
    wait_job(app, call(app, "POST", "/api/analyze", {"path": str(folder)})[1]["job"])
    _, c = call(app, "GET", "/api/replacement-candidates")
    assert any(x["name"] == "Massive X" for x in c["candidates"])
    st, state = call(app, "POST", "/api/replacement", {"plugin": "Massive X", "target": "Massive X"})
    assert st == 200 and state["options"]["mapping"] == {"Massive X": "Massive X"}
    assert [g["kind"] for g in state["groups"] if g["selectable"]] == ["default"]
    g = [x for x in state["groups"] if x["selectable"]][0]
    wait_job(app, call(app, "POST", "/api/convert", {"groups": [g["id"]]})[1]["job"])
    assert [p.name for p in (tmp_path / "out").rglob("*.als")] == ["Test [ReAble].als"]
    state = call(app, "POST", "/api/replacement", {"plugin": "Massive X", "target": ""})[1]
    assert state["options"]["mapping"] == {}


def test_replacement_chosen_for_a_family_applies_to_every_version_of_it():
    from reable.batch import mapped_target
    assert mapped_target("Play", {"play": "Opus"}) == "Opus"
    assert mapped_target("Sausage Fattener", {"Sausage Fattener": "Saturn"}) == "Saturn"
    assert mapped_target("FabFilter Pro-Q 3", {"FabFilter Pro-Q": "Pro-Q 4"}) == "Pro-Q 4"
    assert mapped_target("Kontakt 5", {"Play": "Opus"}) is None


def test_language_preference_and_state(app, monkeypatch):
    monkeypatch.delenv("REABLE_LANG", raising=False)
    st, s = call(app, "POST", "/api/language", {"language": "en"})
    assert st == 200 and s["lang"] == "en" and s["language"] == "en"
    assert call(app, "POST", "/api/language", {"language": "fr"})[1]["lang"] == "fr"
    assert call(app, "POST", "/api/language", {"language": "klingon"})[0] == 400


def test_python_written_texts_follow_the_language(monkeypatch):
    from reable import i18n
    from reable.adapters import state_note
    monkeypatch.setenv("REABLE_LANG", "fr")
    assert state_note("none") == "Réglages par défaut : le preset d'origine n'a pas été transféré"
    assert i18n.track_info_template(i18n.TRACK_INFO_FR) == i18n.TRACK_INFO_FR
    monkeypatch.setenv("REABLE_LANG", "en")
    assert state_note("none") == "Default settings: the original preset was not transferred"
    assert i18n.track_info_template(i18n.TRACK_INFO_FR) == i18n.TRACK_INFO_EN
    assert i18n.track_info_template("mon modèle perso") == "mon modèle perso"          # un modèle modifié n'est jamais remplacé
    assert i18n.tr("Restauré") == "Restored"


def test_english_dictionary_covers_every_static_text_of_the_interface():
    """Tout texte français « en dur » de app.js doit avoir une traduction (ou être une phrase construite via L())."""
    import re
    root = Path(__file__).parents[1] / "src/reable/app/static"
    en = json.loads((root / "locales/en.json").read_text(encoding="utf-8"))
    known = {k.strip() for k in en["exact"]}
    pats = [re.compile(p) for p, _ in en["patterns"]]
    js = (root / "app.js").read_text(encoding="utf-8")
    # chaînes entre guillemets droits, sans variable ${}, qui ressemblent à du texte français affiché
    missing = []
    for m in re.finditer(r'(?<![\w.])"((?:[^"\\\n]|\\.)*)"', js):
        t = m.group(1).replace("\\n", "\n").strip()
        if "${" in t or len(t) < 4 or t in known or any(p.match(t) for p in pats):
            continue
        if re.search(r"[À-ÿ’«»…]", t) or re.fullmatch(r"[A-Z][a-z]+( [a-zà-ÿ]+)*", t):
            missing.append(t)
    ignore = {"Lead", "Abstract City", "Ozone 10", "Escape", "Enter", "Space", "Tab",          # exemples et touches
              "[Idée]", "estimating…", "— ReAble can’t convert them yet.", "plugin n’a", "plugins n’ont",        # arguments de L() et plural()
              "copie déjà faite est conservée", "copies déjà faites sont conservées"}
    assert not [t for t in missing if t not in ignore], missing


def test_intel_only_plugins_count_as_missing_on_apple_silicon(tmp_path, monkeypatch):
    import struct
    from reable import inventory
    from reable.model import Plugin

    def bundle(name, kind, cpus, folder):
        b = tmp_path / "Plug-Ins" / folder / f"{name}.{kind}" / "Contents/MacOS"
        b.mkdir(parents=True)
        if len(cpus) == 1:
            data = b"\xcf\xfa\xed\xfe" + struct.pack("<I", cpus[0]) + b"\0" * 64
        else:
            data = b"\xca\xfe\xba\xbe" + struct.pack(">I", len(cpus)) + b"".join(struct.pack(">IIIII", c, 0, 0, 0, 0) for c in cpus)
        (b / name).write_bytes(data)
        return b.parent.parent

    X86, ARM = 0x01000007, 0x0100000C
    assert inventory.bundle_archs(bundle("Intel", "vst", [X86], "VST")) == {"x86_64"}
    assert inventory.bundle_archs(bundle("Both", "vst3", [X86, ARM], "VST3")) == {"x86_64", "arm64"}
    monkeypatch.setattr(inventory, "runs_natively_here", lambda: True)
    inv = inventory.scan_installed([tmp_path / "Plug-Ins"])
    assert inv.intel_only["VST2"] == {"intel"} and inv.intel_only["VST3"] == set()
    ps = [Plugin("T", "Intel", "VST2", "Intel"), Plugin("T", "Both", "VST3", "Both")]
    inventory.check(ps, inv)
    assert ps[0].install_status == "manquant" and "Intel" in ps[0].install_detail
    assert ps[1].install_status == "installé"
    monkeypatch.setattr(inventory, "runs_natively_here", lambda: False)          # Mac Intel : rien n'est signalé
    inv = inventory.scan_installed([tmp_path / "Plug-Ins"])
    ps = [Plugin("T", "Intel", "VST2", "Intel")]
    inventory.check(ps, inv)
    assert ps[0].install_status == "installé"


def _note_item(set_path, plugin="Massive X", fmt="AU", status="bloqué"):
    return PlanItem(set_path, plugin, fmt, status=status, note=True, instances=1,
                    reason="pas de plugin VST3 compatible installé (famille non gérée ou absente)")


def test_notes_group_comes_in_addition_to_the_original_group():
    items = [_note_item("/a/Set A.als", status="annotable"), _note_item("/a/Set B.als", "Play", "VST2", status="annotable"),
             PlanItem("/a/Set C.als", "Kontakt", "VST2", "Kontakt 8", status="convertible")]
    groups = group_items(items)
    kinds = [g["kind"] for g in groups]
    assert kinds == ["validated", "notes", "unsupported"]
    notes = next(g for g in groups if g["kind"] == "notes")
    assert notes["selectable"] and notes["count"] == 2 and notes["id"] == "notes|||"
    sm = summarize(groups)
    assert sm["to_convert"] == 1 and sm["notes_only"] == 2 and sm["actionable"] == 3


def test_selecting_the_notes_group_selects_the_annotable_items():
    logic = AppLogic()
    logic.items = [_note_item("/a/Set A.als", status="annotable"), PlanItem("/a/Set C.als", "Kontakt", "VST2", "Kontakt 8", status="convertible")]
    assert [i.set_path for i in logic._selected_items(["notes|||"])] == ["/a/Set A.als"]
    assert [i.set_path for i in logic._selected_items(None)] == ["/a/Set A.als", "/a/Set C.als"]


@needs_set
def test_info_note_is_written_on_the_track_of_an_unconvertible_plugin(tmp_path):
    from reable import alsfile, trace
    from reable.batch import ConvertOptions, run
    from reable.app.logic import _has_trace
    src = tmp_path / "Test.als"
    shutil.copy(SET, src)
    opts = ConvertOptions(out_dir=tmp_path / "out", if_exists="overwrite")
    dry = [_note_item(str(src))]
    run(dry, opts, dry_run=True, root_dir=tmp_path)
    assert dry[0].status == "annotable" and not (tmp_path / "out").exists()          # essai à blanc : rien n'est écrit
    items = [_note_item(str(src))]
    res = run(items, opts, dry_run=False, root_dir=tmp_path)
    assert items[0].status == "annoté" and len(res.written) == 1
    root = alsfile.load(res.written[0]).getroot()
    texts = [trace.get_track_block(a.get("Value", "")) for a in root.iter("Annotation")]
    texts = [t for t in texts if t]
    assert texts and all("Plugin manquant : Massive X (AU)" in t and "ReAble ne sait pas encore le convertir" in t for t in texts)
    assert _has_trace(Path(res.written[0]))                                        # annulable : la copie est reconnue comme celle de ReAble
    assert alsfile.load(src).getroot().find(".//Annotation") is not None            # l'original n'est pas touché
    assert not any(trace.get_track_block(a.get("Value", "")) for a in alsfile.load(src).getroot().iter("Annotation"))


def test_note_option_is_off_switchable():
    from reable.batch import ConvertOptions
    assert ConvertOptions().note_unconverted is True
    assert ConvertOptions.from_dict({"note_unconverted": False}).note_unconverted is False
