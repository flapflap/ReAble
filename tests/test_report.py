from reable.model import Plugin, SetReport
from reable.report import classify, folder_markdown


def P(**kw):
    base = dict(track="T", chain_path="", format="VST2", name="X", install_status="manquant")
    base.update(kw)
    return Plugin(**base)


def test_classify():
    assert classify(P(install_status="installé")) == "ok"
    assert classify(P(replacements=["VST3"])) == "autre-format"
    assert classify(P(family_installed=["kontakt 8"])) == "meme-famille"
    assert classify(P()) == "a-reinstaller"
    assert classify(P(install_status="inconnu")) == "inconnu"


def test_markdown_sections_and_no_missing():
    r = SetReport(path="/a/S.als", live_version="Live 12", tracks=["T"],
                  plugins=[P(name="Pro-Q 2"), P(name="Kontakt 5", family_installed=["kontakt 8"])])
    md = folder_markdown([r], "/a")
    assert "À réinstaller" in md and "Pro-Q 2" in md
    assert "Même famille installée" in md and "kontakt 8" in md
    assert "S.als" in md.split("## Sets par nombre")[1]
    ok = SetReport(path="/a/Ok.als", live_version="Live 12", tracks=[], plugins=[P(install_status="installé")])
    md_ok = folder_markdown([ok], "/a")
    assert "À réinstaller" not in md_ok and "Sets par nombre" in md_ok
