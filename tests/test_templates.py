import shutil
from pathlib import Path

import pytest

from reable import alsfile, templates
from reable.batch import build_template_index
from reable.extract import extract
from reable.rewrite import check_tree, rewrite_file

SET = Path(__file__).parents[1] / "Test Plugins AU VST3 Project" / "Test Plugins AU VST3.als"
needs_set = pytest.mark.skipif(not SET.exists(), reason="set de test absent (non versionné)")


@needs_set
def test_remember_stores_one_small_template_per_plugin_and_is_idempotent():
    before = SET.read_bytes()
    added = templates.remember([SET])
    assert sorted(a.lower() for a in added) == ["massive x", "ozone 10"]
    files = templates.library_files()
    assert len(files) == 2 and all(f.stat().st_size < 60_000 for f in files)       # mini-fichiers, pas des copies de projet
    assert SET.read_bytes() == before                                              # le projet analysé n'est pas touché
    assert templates.remember([SET]) == []                                         # deuxième fois : rien à refaire


@needs_set
def test_library_templates_feed_the_template_index():
    templates.remember([SET])
    idx = build_template_index(templates.library_files())
    assert {"massive x", "ozone 10"} <= set(idx)


@needs_set
def test_conversion_through_a_library_template_matches_the_one_through_the_project(tmp_path):
    templates.remember([SET])
    lib = next(f for f in templates.library_files() if "massive-x" in f.name)
    a, _ = rewrite_file(SET, "Massive X", tmp_path / "a", template=SET)
    b, res = rewrite_file(SET, "Massive X", tmp_path / "b", template=lib)
    assert res.warnings == [] and check_tree(alsfile.load(b).getroot()) == []
    pa, pb = extract(a), extract(b)
    ga = [(p.name, p.format, p.state_bytes, p.preset_name) for p in pa.plugins]
    gb = [(p.name, p.format, p.state_bytes, p.preset_name) for p in pb.plugins]
    assert ga == gb


@needs_set
def test_old_projects_are_not_used_as_templates(tmp_path):
    root = alsfile.load(SET).getroot()
    for e in list(root.iter("Pointee")):               # imite un schéma ancien : pas d'Id Pointee
        e.tag = "Autre"
    old = tmp_path / "old.als"
    import xml.etree.ElementTree as ET
    alsfile.save(ET.ElementTree(root), old, backup=False)
    assert templates.remember([old]) == []
