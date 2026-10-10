# CLAUDE.md — ReAble (ancien nom : PlugRescue)

Contexte pour Claude Code. **Le projet s'appelait PlugRescue** : renommé ReAble le 10 oct. 2026 (dépôts GitHub `flapflap/ReAble` et `flapflap/ReAble-library`, privés pour l'instant). Les anciennes copies `[PlugRescue]` et les notes `--- PlugRescue ---` restent lues (compatibilité testée dans `tests/test_legacy.py`) ; le dossier de réglages `~/Library/Application Support/PlugRescue` est migré en `ReAble`. Les dossiers locaux gardent leur ancien nom (`PlugRescue/`, `PlugRescue-definitions/`). Langue de travail : **français** (code et identifiants en anglais, textes visibles et commentaires en français).

## Le projet
Outil pour les sets Ableton Live (`.als`) qui :
1. scanne un dossier de sets ;
2. détecte les plugins tiers manquants sur le Mac (et s'ils existent dans un autre format : AU, VST2 ou VST3) ;
3. extrait, par piste, le plugin, le nom du preset, les paramètres, les automations et l'état interne du plugin ;
4. résume tout ça dans un rapport lisible, pour pouvoir recréer le son ;
5. (à venir) réécrit le set avec un plugin de remplacement, en gardant le preset et les automations.

Déclencheur : un set avec 4 × Massive X en **AU** alors que seul le **VST3** est installé.
Presets retrouvés : Bump Force, Active Jay, Bubble Counter, Anime Jungle.

Utilisateur type : un producteur sur Mac (Apple Silicon), Ableton Live 12, des centaines de projets dans `~/Music/MesProjets` (et d'autres dossiers).
Outil personnel de l'auteur, en voie de publication open source.

## Lancer
```bash
./run.sh convert ~/Music/MesProjets --dry-run            # plan : convertible / bloqué (et pourquoi)
./run.sh convert <dossier> --out <sortie> [--all] [--tag-track]   # écrit des copies [ReAble]
./run.sh restore "<set [ReAble].als>" [--original <set>]       # remet les plugins d'origine
./run.sh scan ~/Music/MesProjets --out ~/Desktop      # recommandé (pas besoin d'activer le venv)
./run.sh scan "Set.als" --out ~/Desktop
./run.sh scan <dossier> --include-packs              # inclure les Factory Packs d'Ableton (ignorés par défaut)
./run.sh scan <cible> --plugins-root <dossier>       # inventorier un autre dossier Plug-Ins (tests)
```
Tests : `source .venv/bin/activate && pytest` (la fixture `tests/fixtures/MySet.xml` est le vrai set aux 4 Massive X ; elle n'est pas versionnée).

### Piège d'installation connu
`pip install -e .` installe bien, mais la commande `reable` échoue (`ModuleNotFoundError`).
Cause probable : macOS marque le fichier `__editable__.reable-0.1.0.pth` comme caché, et Python 3.13 ignore les `.pth` cachés.
Contournements : `./run.sh` (qui met `src/` dans le PYTHONPATH), ou
`chflags nohidden .venv/lib/python3.*/site-packages/*.pth`.

## Architecture
```
run.sh                 lanceur (Python du venv + PYTHONPATH=src)
src/reable/
  alsfile.py           .als = XML compressé en gzip ; find_sets() ignore Backup/ et Factory Packs/
  extract.py           pistes, plugins (AU/VST2/VST3), presets, ParameterList, liens vers les automations
  model.py             dataclasses Plugin / Parameter / SetReport
  decoders/            un décodeur par famille de plugins : decode(raw, name) -> (preset, summary, full) | None
    ni_msgpack.py      NI récents (Massive X) : en-tête 16 o + zlib + flux msgpack de clés nommées
    izotope_json.py    iZotope (Neutron, Ozone) : en-tête + zlib + JSON "Context State"
  inventory.py         plugins installés sur macOS (Components/Info.plist, VST3 moduleinfo.json ou nom, VST2 nom)
  report.py            rapport Markdown + JSON complet
  cli.py               commande `scan`
docs/EVALUATION.md     évaluation technique complète, recherche des outils existants, feuille de route
```
Dépendances : stdlib + `msgpack`. Python ≥ 3.10.

## Ce qu'on sait du format .als (vérifié sur Live 12.0.1)
- AU : `<AuPluginDevice>` → `PluginDesc/AuPluginInfo` (Name, Manufacturer, ComponentType/SubType/Manufacturer en entiers = codes de 4 caractères, ex. Massive X `aumu/Ni$H/-NI-`). L'état est dans `Preset/AuPreset/Buffer` (hex) → plist Apple. NI y range son état dans la clé **`vstdata`**.
- VST3 : `<PluginDevice>` → `Vst3PluginInfo` (Name, `Uid/Fields.0..3` = 16 octets). L'état est dans `Preset/Vst3Preset/ProcessorState` (+ `ControllerState`).
  Les UID suivent le schéma de compatibilité VST2 de Steinberg : `"VST" + ID à 4 caractères + 9 caractères du nom` (ex. `VSTNBa4battery 4`, `VSTZNN3Neutron 3`).
  Prédiction pour Massive X VST3 : `VSTNi$Hmassive x`, **non vérifiée**.
- VST2 : `VstPluginInfo` (PlugName, UniqueId, `Preset/VstPreset/Buffer`). Non testé : aucun VST2 dans les sets vus.
- Paramètres exposés dans Live : `ParameterList/PluginFloatParameter` → ParameterName, ParameterId, `ParameterValue/Manual` (0–1), AutomationTarget Id, ModulationTarget Id.
- Automations : `AutomationEnvelope` (arrangement) et `ClipEnvelope` (clips) → `EnvelopeTarget/PointeeId` = Id d'un AutomationTarget ou d'un ModulationTarget.

### Pièges
- `LastPresetRef` (« Default.aupreset ») est une référence du navigateur de Live, **pas** le vrai preset.
- `Manual` n'est pas fiable pour les plugins : les macros de Massive X sont à 0 % dans Live mais à 49 %, 25 %… dans l'état interne. `0.1234567687` = sentinelle de Live pour « valeur jamais lue ». **L'état interne fait foi.**
- Le nom du preset ne se trouve que dans l'état interne (`meta/presetName` chez NI, `Preset Name` chez iZotope). Ozone renvoie « Presets » quand aucun preset n'est chargé.
- Battery 4 (ancien format NI `hsin`) : non décodé.

## Recherche de l'existant (7 oct. 2026)
- **abletoolz** (GPL-3, CLI Python, v2.1 août 2026) : détection des manquants + `--repair-plugins` **VST2 → VST3** pour quelques plugins. **Pas d'AU → VST3.** Ne pas copier son code (licence GPL) ; une contribution (décodeur NI) reste possible.
- OwlPlug, als-tools, ALFA, PlugView : détection ou inventaire seulement. Live ne migre rien automatiquement.
- Positionnement de ReAble : AU → VST3, fiche de recréation lisible, interface simple.

## État et prochaines étapes
- ✅ Phase 2 (test décisif) : **validé dans Live 12** — AU→VST3 (Massive X), VST2→VST3 (Massive), VST2→Kontakt 8 VST3 (Kontakt, Kontakt 5), notes/noms. Voir docs/EVALUATION.md §9 et docs/TESTS-LIVE.md.
- ✅ Phase 3 (prototype) : `./run.sh rewrite SET --plugin NOM [--from VST2] [--as NOM_VST3] [--template SET]`, nouveau fichier `[ReAble]`, garde-fou sur le conteneur d'état. Limité aux plugins NI et aux sets Live ≥ 11.
- ✅ Phase 3b (moteur, branche `feature/phase3-moteur`) : note de traçabilité (`trace.py`), `restore`, conversion en lot (`batch.py`), API unique (`api.py` : `analyze`, `propose`, `convert`, `restore`), commande `convert`.
- ✅ Phase 3c (branche `feature/options-workflow`) : options de workflow (`ConvertOptions`/profil JSON : duplicate_track, keep_device, renommage par modèle, texte d'info de piste, mapping, skip) ; **validé dans Live** (lots G6, H, restore). Garde-fous : Id globaux uniques (`is_pointee`), contrôle de schéma des attributs.
- 🟡 Phase 3d (branche `feature/plugin-upgrade`) : mise à niveau d'un plugin vers une version plus récente (Ozone 9 → 10) avec `adapters.py` (`--state-mode transfer|header|none`, `--family ozone`, `--templates`), source VST3, `keep_device` sur piste principale/retour/groupe (+ restore), `probe` (classe le conteneur d'état de n'importe quel plugin). **Ozone 9 → 10 validé** (état repris, ControllerState requis ; vérifié par `reable verify`) ; Ozone 8 et 7 : état ignoré par Ozone 10 → réglages par défaut + ancien preset en note (`state_transfer_from` dans la définition). Étude d'extensibilité : docs/EXTENSIBILITY.md.
- ✅ Registre de définitions (branche `feature/plugin-registry`) : `registry.py`, commande `plugins`, deux dépôts décidés — **code** (ce dépôt) et **définitions** (`../ReAble-definitions`, local pour l'instant, à publier) ; validation locale, partageable ; non validé = bloqué ; programme bêta anonyme (docs/EXTENSIBILITY.md §6-7). La config de l'auteur pointe vers `../ReAble-definitions/definitions` (`reable plugins config --definitions-dir`).
- 🟡 Interface (branche `feature/interface`, **code testé dans le navigateur, pas encore dans une fenêtre Mac**) : `./run.sh app [--port 3000] [--browser]` lance un serveur local sécurisé (127.0.0.1, jeton, contrôle Host/Origin) qui sert `src/reable/app/static/` (design B v2 « utilitaire Mac », jetons `tokens.css`). Moteur : arrêt coopératif (`jobs.py`), écriture atomique, progression par événements, annulation vers la corbeille (`undo`), bibliothèque de gabarits (`templates.py`, alimentée à chaque analyse). Plan : docs/superpowers/plans/2026-10-09-interface.md. Maquettes : docs/design/claude-design-v2/.
- ✅ Fenêtre native : `./run.sh app` (pywebview ; `--browser` pour le navigateur) — sélecteur de dossier macOS, glisser-déposer, confirmation à la fermeture pendant une tâche (`window.py`, testé sans fenêtre). **Non vérifié visuellement par Claude** (pas d'accès à la fenêtre).
- ⏭️ Suite : Reprendre/Annuler après un arrêt en conversion à tester en réel ; onglet Plugins (ajout/validation) ; iZotope (conteneur réordonné) ; sets Live ≤ 10 (à ré-enregistrer dans Live 12) ; rendu audio (T6).

- ✅ Phase 0 : prototype (scan, extraction, décodeurs NI/iZotope, rapport, tests), testé sur un corpus réel de l'auteur (381 sets, Live 9 → 12.4, sans erreur).
- ⏭️ Phase 1 : scanner les vrais projets (`~/Music/MesProjets`) et analyser le rapport.
- ⏭️ Phase 2, **test décisif** : un set avec Massive X en AU **et** en VST3 sur le même preset → comparer `vstdata` (AU) et `ProcessorState` (VST3), et relever l'UID VST3 réel. S'ils sont identiques, la réécriture AU → VST3 est faisable.
- Phase 3 : commande `rewrite` (voir docs/EVALUATION.md §4) :
  - partir d'un **gabarit** `Vst3PluginInfo` copié d'un set réel, sans jamais inventer le XML de Live ;
  - injecter l'état ;
  - remapper les ParameterId **par nom**, en **gardant les mêmes Id AutomationTarget/ModulationTarget** pour que les automations restent branchées ;
  - écrire un **nouveau** fichier `<Set> [ReAble].als` et ne jamais écraser l'original.
- Phase 4 : mini-app Mac (glisser-déposer, tableau, bouton Réparer) : pywebview ou SwiftUI.
- Phase 5 : autres décodeurs selon les plugins les plus utilisés (JUCE, FXP/FXB, u-he, Vital, Battery…).

## Règles
- Ne **jamais** modifier un `.als` original ; toute écriture va dans un nouveau fichier, avec une sauvegarde horodatée (`alsfile.save`).
- Un décodeur ne doit jamais faire planter le scan : il renvoie `None` s'il ne reconnaît pas le format.
- Les fichiers de sets et les rapports générés restent hors de Git (`.gitignore`).
