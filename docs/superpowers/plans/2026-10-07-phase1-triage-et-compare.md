# ReAble — Phase 1 (triage MesProjets) + Phase 2 (comparaison d'états) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le rapport MesProjets exploitable (distinguer « vraiment absent » de « même famille installée » / « autre format installé ») et prouver, sur des sets existants, si l'état d'un plugin est identique entre deux formats avant d'écrire la moindre réécriture.

**Architecture:** On garde le pipeline `extract → inventory.check → report`. On ajoute (1) une table de familles de plugins pour qualifier les manquants, (2) un rapport plus lisible (groupé par plugin et par set), (3) une commande `compare` qui diffuse les états de deux plugins d'un même set (VST2/AU vs VST3). La commande `rewrite` est volontairement hors de ce plan : elle dépend du résultat de la tâche 4.

**Tech Stack:** Python ≥ 3.10, stdlib + `msgpack`, pytest.

**Spec:** `CLAUDE.md` (sections « Architecture », « État et prochaines étapes ») et `docs/EVALUATION.md` §4.

## Constats du scan MesProjets (7 oct. 2026, 365 sets, 61 s, 0 erreur)

- 1821 plugins tiers (VST2 1278, VST3 498, AU 45) ; **979 « manquants »** (VST2 764, VST3 176, AU 39). 134 sets sans plugin tiers.
- Les 5 « remplacements » détectés ne concernent que Reason Rack / kHs / Snap Heap (VST3 → AU). Aucun pour les VST2.
- **Faux manquants probables** : `Kontakt 5` (VST2, id `NiO5`, 190 occ.) alors que `Kontakt` (id `Ni$D`, 362 occ.) et Kontakt 7/8 sont installés. `Ozone 7/8/9` et `Neutron 3` (VST2/VST3) alors qu'Ozone 10 est installé. Ce sont des **mêmes familles**, pas de vrais « introuvables ».
- **Vrais manquants** : toute la gamme FabFilter (Pro-Q 2 : 146, Pro-C 2 : 56…), Play/EastWest (128), EW Spaces II, WLM, Sausage Fattener, T-RackS, Nectar 3, Vienna Synchron Player, Valhalla.
- **Aucun set AU+VST3 du même plugin dans MesProjets.** Les 14 Massive X sont tous en VST3 (UID réel `5653544E6924486D6173736976652078` = `VSTNi$Hmassive x` : **la prédiction de CLAUDE.md est confirmée**). Les 39 AU manquants (Sausage Fattener, T-RackS 3, Nectar 3) ne sont installés dans aucun format : une réécriture AU→VST3 n'aurait rien à gagner ici.
- Cas « même plugin dans 2 formats dans un même set » exploitables dès maintenant : Ozone 8 (3 sets), Neutron 3 (1), Play (1), Abbey Road One (1) → test d'état entre formats sans rien demander à l'utilisateur.
- Décodage : 278 états décodés (Ozone/Neutron/Nectar/Massive X), noms de preset sur 113/1821. Kontakt (362 occ.), Reason Rack (95), Opus (54) ne sont pas décodés.
- `pytest` échoue à la collecte (`No module named 'reable'`) : piège du `.pth` caché de CLAUDE.md. Aucun commit n'existe encore sur `main`.
- `~/Library/Application Support/Ableton/Live Database/Live-plugins-1.db` existe mais n'est pas lisible depuis la session sandboxée → à explorer à part (tâche 2, bonus).

## Global Constraints

- Ne jamais modifier un `.als` original (aucune tâche de ce plan n'écrit un `.als`).
- Un décodeur ne doit jamais faire planter le scan.
- Textes visibles et commentaires en français, identifiants en anglais.
- Les rapports générés et les fixtures restent hors Git.
- Python : `python3` (jamais `python`), venv `.venv`.

## Review Focus

- Set contenant le même plugin en 2 formats mais dont un des états est vide (`b""`) : `compare` doit dire « état vide », pas planter.
- Nom de plugin avec numéro de version (« Ozone 7 », « Pro-Q 2 (Mono) ») : la famille doit être détectée sans confondre « Play » et « Playground ».
- Plugin installé uniquement dans une version plus récente de la famille : afficher « famille installée (Kontakt 8) », pas « installé ».
- Rapport sur un dossier sans aucun manquant : pas de tableau vide ni de division par zéro.
- `compare` sur un set où le plugin n'existe qu'en un seul format : message clair, code retour ≠ 0.

## File Structure

- Create `src/reable/families.py` — table `FAMILIES` + `family_of(name) -> str | None`.
- Modify `src/reable/model.py` — champ `Plugin.family_installed: list[str]`.
- Modify `src/reable/inventory.py` — remplir `family_installed`.
- Modify `src/reable/report.py` — sections « À réinstaller / même famille / autre format » et tableau par set.
- Create `src/reable/compare.py` — `compare_states(a: Plugin, b: Plugin) -> dict`.
- Modify `src/reable/cli.py` — sous-commande `compare`.
- Create `tests/test_families.py`, `tests/test_report.py`, `tests/test_compare.py`.

---

### Task 1: Environnement et premier commit

**Files:**
- Modify: `.gitignore` (ajouter `.omc/`, `.pytest_cache/`)
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: `pytest` exécutable sans activer le venv (`./run.sh` reste le lanceur).

- [ ] **Step 1: Réparer le `.pth` caché et créer `tests/conftest.py` qui met `src/` dans le path**

```bash
chflags nohidden .venv/lib/python3.*/site-packages/*.pth
```

Créer `tests/conftest.py` (filet de sécurité si le `.pth` est de nouveau caché) :

```python
"""Met src/ dans le path pour que pytest marche même sans pip install -e."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
```

- [ ] **Step 2: Test de fumée**

`tests/test_smoke.py` :

```python
from reable.inventory import Inventory, check
from reable.model import Plugin


def test_inventory_unavailable_gives_unknown():
    p = Plugin(track="T", chain_path="", format="VST3", name="X")
    check([p], Inventory(available=False))
    assert p.install_status == "inconnu"
```

- [ ] **Step 3: Lancer** — `.venv/bin/python -m pytest -q` → Expected: `1 passed` (+ 2 skipped si la fixture est absente).

- [ ] **Step 4: Commit**

```bash
git add .gitignore CLAUDE.md README.md docs pyproject.toml run.sh src tests
git commit -m "chore: prototype ReAble (scan, extraction, décodeurs NI/iZotope, rapport)"
```

---

### Task 2: Familles de plugins — qualifier les « manquants »

**Files:**
- Create: `src/reable/families.py`
- Modify: `src/reable/model.py` (ajouter `family_installed: list[str] = field(default_factory=list)` après `replacements`)
- Modify: `src/reable/inventory.py` (fin de `check`)
- Test: `tests/test_families.py`

**Interfaces:**
- Produces: `family_of(name: str) -> str | None` ; `Plugin.family_installed: list[str]` (noms de bundles installés de la même famille, tous formats).
- Consumes: `Inventory.names_by_format()` existant (noms en minuscules).

- [ ] **Step 1: Test qui échoue**

```python
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
```

- [ ] **Step 2: Lancer** — `.venv/bin/python -m pytest tests/test_families.py -v` → Expected: FAIL (`ModuleNotFoundError: reable.families`).

- [ ] **Step 3: Implémenter**

`src/reable/families.py` :

```python
"""Familles de plugins : « Kontakt 5 », « Kontakt 8 » → « kontakt ».

Sert à distinguer un plugin vraiment absent d'un plugin dont une version
plus récente est installée (l'état est souvent relisible par la nouvelle version).
"""
from __future__ import annotations

import re

# (motif sur le nom normalisé, famille). Le premier qui correspond gagne.
_RULES: list[tuple[str, str]] = [
    (r"^(izotope )?ozone\b", "ozone"),
    (r"^(izotope )?neutron\b", "neutron"),
    (r"^(izotope )?nectar\b", "nectar"),
    (r"^kontakt\b", "kontakt"),
    (r"^massive x$", "massive x"),
    (r"^massive$", "massive"),
    (r"^fabfilter pro-q\b", "fabfilter pro-q"),
    (r"^fabfilter pro-c\b", "fabfilter pro-c"),
    (r"^fabfilter pro-l\b", "fabfilter pro-l"),
    (r"^fabfilter pro-mb\b", "fabfilter pro-mb"),
    (r"^play$", "play"),
    (r"^wlm\b", "wlm"),
    (r"^t-?racks\b", "t-racks"),
]


def family_of(name: str) -> str | None:
    n = name.lower().strip()
    for pattern, fam in _RULES:
        if re.search(pattern, n):
            return fam
    return None
```

Dans `inventory.py`, ajouter l'import `from .families import family_of` et, à la fin de la boucle de `check` (après `if not ok: p.replacements = ...`) :

```python
        if not ok:
            fam = family_of(p.name)
            if fam:
                installed = {nm for s in names.values() for nm in s if family_of(nm) == fam}
                p.family_installed = sorted(installed)
```

- [ ] **Step 4: Lancer** — `.venv/bin/python -m pytest tests/test_families.py -v` → Expected: 3 passed.

- [ ] **Step 5: Vérifier sur le vrai dossier** — `./run.sh scan ~/Music/MesProjets --out "$TMPDIR/pr"` puis compter les manquants avec `family_installed` non vide dans le JSON : attendu > 300 (Kontakt 5 : 190, Ozone/Neutron…).

- [ ] **Step 6: Commit** — `git add src tests && git commit -m "feat: familles de plugins pour qualifier les manquants"`

---

### Task 3: Rapport lisible (à réinstaller / même famille / autre format)

**Files:**
- Modify: `src/reable/report.py:68-90` (`folder_markdown`)
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `Plugin.install_status`, `Plugin.replacements`, `Plugin.family_installed`.
- Produces: `classify(p: Plugin) -> str` retournant `"ok" | "autre-format" | "meme-famille" | "a-reinstaller" | "inconnu"` ; `folder_markdown` utilise ces catégories.

- [ ] **Step 1: Test qui échoue**

```python
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
    assert "S.als" in md.split("## Sets")[1]            # tableau par set
    ok = SetReport(path="/a/Ok.als", live_version="Live 12", tracks=[], plugins=[P(install_status="installé")])
    assert "À réinstaller" not in folder_markdown([ok], "/a")   # pas de tableau vide
```

- [ ] **Step 2: Lancer** — Expected: FAIL (`cannot import name 'classify'`).

- [ ] **Step 3: Implémenter** dans `report.py`

```python
def classify(p: Plugin) -> str:
    if p.install_status == "installé":
        return "ok"
    if p.install_status != "manquant":
        return "inconnu"
    if p.replacements:
        return "autre-format"
    if p.family_installed:
        return "meme-famille"
    return "a-reinstaller"


_SECTIONS = [
    ("a-reinstaller", "À réinstaller (introuvable sur ce Mac)"),
    ("meme-famille", "Même famille installée (version plus récente ou voisine)"),
    ("autre-format", "Installé dans un autre format"),
]
```

(ajouter `Plugin` à l'import de `.model`). Remplacer le bloc « Plugins manquants » de `folder_markdown` par :

```python
    for cat, title in _SECTIONS:
        sel = [p for p in missing if classify(p) == cat]
        if not sel:
            continue
        L += [f"## {title}", "", "| Plugin | Occurrences | Sets | Disponible |", "|---|---|---|---|"]
        sets_of: dict[str, set[str]] = {}
        avail: dict[str, str] = {}
        for r in reports:
            for p in r.plugins:
                if p in sel:
                    k = f"{p.name} ({p.format})"
                    sets_of.setdefault(k, set()).add(r.path)
                    avail[k] = ", ".join(p.replacements or p.family_installed) or "—"
        for k, n in Counter(f"{p.name} ({p.format})" for p in sel).most_common():
            L.append(f"| {k} | {n} | {len(sets_of[k])} | {avail[k]} |")
        L.append("")
    L += ["## Sets par nombre de plugins à traiter", "", "| Set | Manquants | Dont à réinstaller |", "|---|---|---|"]
    rows = []
    for r in reports:
        m = [p for p in r.plugins if p.install_status == "manquant"]
        if m:
            rows.append((len(m), sum(classify(p) == "a-reinstaller" for p in m), Path(r.path).name))
    for n, k, name in sorted(rows, reverse=True):
        L.append(f"| {name} | {n} | {k} |")
    L.append("")
```

Garder le reste (détail par set) inchangé. Le test cherche `"## Sets"` : le titre ci-dessus commence par « ## Sets par nombre… » ; adapter l'assertion si le détail « ## Sets sans plugin tiers » apparaît avant (il est après).

- [ ] **Step 4: Lancer** — `.venv/bin/python -m pytest tests/test_report.py -v` → Expected: 2 passed.

- [ ] **Step 5: Régénérer le rapport MesProjets** et le lire : `./run.sh scan ~/Music/MesProjets --out ~/Desktop` ; vérifier que Kontakt 5 est dans « Même famille » et Pro-Q 2 dans « À réinstaller ».

- [ ] **Step 6: Commit** — `git commit -am "feat: rapport par catégorie (réinstaller / même famille / autre format)"`

---

### Task 4: Commande `compare` — l'état est-il identique entre deux formats ?

**Files:**
- Create: `src/reable/compare.py`
- Modify: `src/reable/cli.py` (sous-commande `compare`)
- Test: `tests/test_compare.py`

**Interfaces:**
- Consumes: `extract.extract(path) -> SetReport`, `Plugin.state_bytes`, `Plugin.state_full`, `Plugin.format`.
- Produces: `compare_states(a: Plugin, b: Plugin) -> dict` avec les clés `verdict` (`"identique" | "similaire" | "différent" | "état vide"`), `bytes_a`, `bytes_b`, `common_keys`, `diff_keys` (liste ≤ 20).

> Prérequis : `extract` ne conserve pas les octets bruts de l'état, seulement `state_bytes` (taille) et `state_full` (décodé). On compare donc le **décodé** quand il existe, sinon les tailles. Si aucun des deux n'est décodé (cas Play, Abbey Road One), le verdict est `"différent"` ou `"identique"` sur la seule taille et le rapport le dit.

- [ ] **Step 1: Test qui échoue**

```python
from reable.compare import compare_states
from reable.model import Plugin


def P(fmt, full, size=10):
    return Plugin(track="T", chain_path="", format=fmt, name="X", state_full=full, state_bytes=size)


def test_identical_decoded_states():
    r = compare_states(P("VST2", {"a": 1, "b": 2}), P("VST3", {"a": 1, "b": 2}))
    assert r["verdict"] == "identique" and r["diff_keys"] == []


def test_similar_states_list_differences():
    r = compare_states(P("VST2", {"a": 1, "b": 2}), P("VST3", {"a": 1, "b": 3}))
    assert r["verdict"] == "similaire" and r["diff_keys"] == ["b"]


def test_empty_state():
    r = compare_states(P("VST2", {}, size=0), P("VST3", {"a": 1}))
    assert r["verdict"] == "état vide"


def test_no_decoder_falls_back_to_size():
    assert compare_states(P("VST2", {}, 100), P("VST3", {}, 100))["verdict"] == "identique"
    assert compare_states(P("VST2", {}, 100), P("VST3", {}, 4000))["verdict"] == "différent"
```

- [ ] **Step 2: Lancer** — Expected: FAIL (module absent).

- [ ] **Step 3: Implémenter**

```python
"""Compare l'état interne de deux instances d'un même plugin (formats différents)."""
from __future__ import annotations

from .model import Plugin


def compare_states(a: Plugin, b: Plugin) -> dict:
    out = {"bytes_a": a.state_bytes, "bytes_b": b.state_bytes,
           "common_keys": 0, "diff_keys": []}
    if not a.state_bytes or not b.state_bytes:
        out["verdict"] = "état vide"
        return out
    if a.state_full and b.state_full:
        keys = set(a.state_full) | set(b.state_full)
        diff = sorted(k for k in keys if a.state_full.get(k) != b.state_full.get(k))
        out["common_keys"] = len(keys) - len(diff)
        out["diff_keys"] = diff[:20]
        out["verdict"] = "identique" if not diff else "similaire"
        return out
    out["verdict"] = "identique" if a.state_bytes == b.state_bytes else "différent"
    return out
```

Dans `cli.py`, ajouter après `sc` :

```python
    cp = sub.add_parser("compare", help="comparer l'état d'un même plugin chargé dans deux formats")
    cp.add_argument("set_file")
    cp.add_argument("plugin", help="nom du plugin, ex. « Ozone 8 »")
```

et, avant `target = ...`, gérer la branche :

```python
    if args.cmd == "compare":
        from .compare import compare_states
        r = extract(Path(args.set_file).expanduser())
        found = [p for p in r.plugins if p.name == args.plugin]
        formats = {}
        for p in found:
            formats.setdefault(p.format, p)
        if len(formats) < 2:
            print(f"« {args.plugin} » n'existe pas dans deux formats dans ce set (trouvé : {sorted(formats) or 'rien'}).")
            return 2
        (fa, pa), (fb, pb) = list(formats.items())[:2]
        res = compare_states(pa, pb)
        print(f"{args.plugin} : {fa} vs {fb} → {res['verdict']} "
              f"({res['bytes_a']} o / {res['bytes_b']} o, {res['common_keys']} clés communes)")
        for k in res["diff_keys"]:
            print(f"  ≠ {k}")
        return 0
```

- [ ] **Step 4: Lancer** — `.venv/bin/python -m pytest tests/test_compare.py -v` → Expected: 4 passed.

- [ ] **Step 5: Test réel sur les sets MesProjets** : trouver les chemins via le JSON (`Projet H.als`, `Projet 24.als`, `00129 - Projet - Ready For You.als`, `Projet I.als`), puis

```bash
./run.sh compare "<chemin du set>" "Ozone 8"
```

Noter le verdict dans `docs/EVALUATION.md` §4 (section « Résultats »). Décision de porte : si Ozone 8 / Neutron 3 VST2 vs VST3 donnent `identique`/`similaire` → écrire un plan Phase 3 (`rewrite`) ; sinon revoir l'hypothèse « état identique entre formats ».

- [ ] **Step 6: Commit** — `git commit -am "feat: commande compare (état d'un plugin entre deux formats)"`

---

## Hors plan (à planifier après la porte de la tâche 4)

1. **`rewrite` VST2/AU → VST3** : gabarits `Vst3PluginInfo` pris dans les 14 sets Massive X VST3 de MesProjets (UID confirmé), remapping des `ParameterId` par nom, mêmes Id `AutomationTarget`/`ModulationTarget`, sortie `<Set> [ReAble].als`. Un set avec Massive X en **AU** reste nécessaire pour le test AU→VST3 ; il n'existe pas dans MesProjets.
2. **Rapport/`rewrite` « même famille »** (Kontakt 5 → Kontakt) : tester si Kontakt relit l'état tel quel ; probablement un simple changement d'ID VST2 `NiO5 → Ni$D`.
3. **Décodeurs** par impact : Kontakt (362 + 190 occ.), Reason Rack (95), Opus (54), Battery 4 (21).
4. **Base de Live** (`Live-plugins-1.db`) pour l'inventaire exact : à lancer hors sandbox.
5. **Mini-app Mac** (Phase 4 de CLAUDE.md).

## Self-Review

- Couverture : constats → tâche 2 (faux manquants), tâche 3 (lisibilité), tâche 4 (test décisif adapté aux données réelles), tâche 1 (environnement). Le `rewrite` est volontairement différé.
- Placeholders : aucun ; seul le chemin des sets de la tâche 4 étape 5 est à lire dans le JSON (noms de fichiers donnés).
- Cohérence des types : `family_installed` (tâche 2) consommé par `classify` (tâche 3) ; `compare_states` utilise uniquement `state_bytes`/`state_full`.
- Risque connu : `state_full` peut contenir des valeurs non comparables (bytes) ; l'égalité Python suffit pour ce plan.
