# ReAble — Phase 3 : traçabilité, restauration, conversion en lot, API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (ou subagent-driven-development). Steps use checkbox syntax.

**Goal:** Faire du prototype `rewrite` un moteur réutilisable : une API unique (`analyze`, `propose`, `convert`, `restore`) appelée par la ligne de commande aujourd'hui et par l'interface (pywebview) ensuite.

**Architecture:** `rewrite.py` reste le cœur d'une conversion. `trace.py` écrit/lit une note dans l'`Annotation` du device (JSON + original compressé en option). `batch.py` planifie et exécute sur un dossier (index de gabarits, règles de cible, options). `api.py` expose des dataclasses simples, sérialisables en JSON, pour l'interface.

**Tech Stack:** Python ≥ 3.10, stdlib + msgpack, pytest.

**Spec:** conversation du 7 oct. 2026 ; `docs/EVALUATION.md` §9 ; `docs/TESTS-LIVE.md`.

## Global Constraints
- Ne jamais modifier un `.als` original ; sortie dans un autre dossier ou avec le suffixe `[ReAble]`.
- Un set illisible ou non convertible ne doit jamais arrêter un lot : il est rapporté.
- Sets Live < 11 (sans `Pointee`/`NextPointeeId`) : refusés avec un motif clair.
- Textes visibles en français, identifiants en anglais.
- Les options de l'utilisateur sont explicites (`ConvertOptions`) ; valeurs par défaut sûres.

## Review Focus
- Annotation déjà remplie par l'utilisateur : elle doit être conservée avant le bloc ReAble.
- Set sans aucun device convertible : aucun fichier écrit, motif rapporté.
- Deux sets de Live différents utilisés comme gabarit : choisir le plus récent.
- `restore` sur un device sans original embarqué : avertissement, pas de plantage.
- Note très longue (original embarqué) : l'option peut être coupée (`embed_original=False`).

## Tasks
1. **Traçabilité** (`trace.py`, test `tests/test_trace.py`) : `build_note`, `parse_note`, `strip_note`, `pack_original`, `unpack_original` ; `rewrite_tree` écrit la note (option `write_note`, `embed_original`) et copie l'`Annotation` d'origine.
2. **Restauration** (`trace.restore_tree`, CLI `restore`) : remet le device d'origine à partir de la note.
3. **Lot** (`batch.py`, test `tests/test_batch.py`) : index de gabarits d'un dossier, règles de cible (`families.COMPATIBLE`), plan par set, exécution, rapport.
4. **API + CLI** (`api.py`, `cli.py convert|restore`) : `analyze`, `propose`, `convert`, `restore`, dataclasses JSON.
5. **Doc + fichiers de test Live** : section dans `docs/TESTS-LIVE.md` (note longue embarquée, restauration, lot).
