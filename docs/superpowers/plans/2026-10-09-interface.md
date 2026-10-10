# ReAble — Interface : plan de conception et de réalisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development ou superpowers:executing-plans. Steps use checkbox syntax.

**Goal :** Une application Mac simple et didactique pour convertir des sets Ableton Live, avec un suivi de progression clair et un arrêt possible à tout moment.

**Architecture :** Le moteur existant (`api.py`) reste inchangé dans son principe. On lui ajoute (1) des **événements de progression**, (2) un **arrêt coopératif** et (3) des **écritures atomiques**. Un petit **serveur local** (127.0.0.1:3000, bibliothèque standard) expose une API JSON et sert une interface web statique (HTML/CSS/JS sans étape de build). `pywebview` affiche cette interface dans une fenêtre Mac ; le même serveur est testable dans un navigateur.

**Tech Stack :** Python ≥ 3.10 (stdlib + pywebview), HTML/CSS/JS natifs, pytest, navigateur intégré pour les tests visuels.

**Spec :** conversation du 9 oct. 2026 ; `docs/OPTIONS.md` (réglages) ; `docs/EXTENSIBILITY.md` (onglet Plugins).

## Global Constraints
- Jamais de modification d'un set original ; un arrêt ne laisse **aucun fichier partiel**.
- Textes visibles en français, clairs, sans jargon non expliqué ; le jargon (AU, VST3, état…) est défini au premier usage.
- Thème : clair/sombre selon le système. Contraste ≥ 4,5:1. L'état n'est jamais indiqué par la couleur seule (icône + texte).
- Chaque action longue est **annulable** et montre où elle en est.
- Port 3000 pour le front (règle utilisateur) ; vérifier s'il tourne, le relancer si besoin.
- Les réglages par défaut sont les plus sûrs ; tout choix de workflow est configurable (voir `ConvertOptions`).

## Review Focus
- Arrêt pendant l'écriture d'un set : le fichier de sortie est complet ou absent, jamais tronqué.
- Arrêt pendant l'analyse (365 sets) : l'état partiel est jeté proprement, l'application reste utilisable.
- Reprise après arrêt : relancer ne refait pas ce qui est fait (règle « si le fichier existe : ne pas refaire »).
- Dossier sans aucun set, ou sans rien de convertible : un écran qui explique quoi faire, pas un tableau vide.
- Deux clics rapides sur « Convertir » : une seule tâche à la fois.

---

## 1. Principes de design (« simple et didactique »)
1. **Trois étapes, toujours visibles** : ① Choisir → ② Comprendre → ③ Convertir. Un seul gros bouton principal par étape.
2. **Dire ce qui va se passer avant de le faire.** L'étape ② se lit comme une phrase : « 21 sets seront convertis. 18 Ozone 9 garderont leurs réglages. 66 sets sont trop anciens : ouvrez-les d'abord dans Live 12. »
3. **Chaque « non » a un « pourquoi » et un « que faire »** (une ligne, avec une action : copier la liste, ouvrir le dossier, voir l'aide).
4. **Réglages sûrs par défaut, repliés.** Panneau « Réglages » à droite, avec **aperçu en direct** (exemple de nom de piste avant/après).
5. **Rassurer en permanence** : bandeau discret « Vos sets d'origine ne sont jamais modifiés. Les copies portent [ReAble] dans leur nom. »
6. **Vocabulaire** : un petit glossaire en infobulle (AU, VST2, VST3, état, gabarit), sans interrompre.

## 2. Parcours et écrans

### Écran principal (une seule fenêtre)
```
┌────────────────────────────────────────────────────────────────────────────┐
│ ReAble            ① Choisir  ─  ② Comprendre  ─  ③ Convertir     ⚙ Plugins │
├───────────────────────────────────────────────────────┬────────────────────┤
│  ZONE PRINCIPALE (change selon l'étape)               │  RÉGLAGES           │
│                                                       │  ▸ Que faire de la  │
│  ① « Quel dossier de sets analyser ? »                │    piste ?          │
│     [ ~/Music/MesProjets            ] [Choisir…]        │  ▸ Nom des pistes   │
│     (ou glisser-déposer un dossier)                   │    [aperçu]         │
│                      [ Analyser ]                     │  ▸ Texte d'info     │
│                                                       │  ▸ Plugins autorisés│
│  ② « Voici ce qui va se passer »                      │  ▸ Où écrire        │
│     résumé en phrases + tableau regroupé              │  ▸ Si le fichier    │
│     [ Essai à blanc ]   [ Convertir 21 sets ]         │    existe déjà      │
│                                                       │                     │
│  ③ Suivi (voir §3)                                    │                     │
└───────────────────────────────────────────────────────┴────────────────────┘
```

### Étape ② « Comprendre » : le tableau didactique
Regroupé par **conversion**, pas par set (c'est ce que l'utilisateur comprend) :

| Groupe | Contenu | Étiquette |
|---|---|---|
| ✔ **Ozone 9 → Ozone 10** · 18 sets | « Vos réglages seront repris. » | validé |
| ◐ **Ozone 8 → Ozone 10** · 42 sets | « Ozone 10 ne sait pas lire les réglages d'Ozone 8. Il démarre avec ses réglages par défaut ; le nom de l'ancien preset est noté sur la piste. » | réglages par défaut |
| ✔ **Kontakt 5 → Kontakt 8** · 7 sets | « La piste est dupliquée ; l'originale reste, mutée. » | validé |
| ⛔ **66 sets trop anciens** | « Ouvrez-les dans Live 12 et enregistrez-les. » [Copier la liste] [Ouvrir le dossier] | action requise |
| ○ **245 plugins sans équivalent** (FabFilter, Play…) | « ReAble ne sait pas encore les convertir. » [Voir lesquels] | non pris en charge |

Chaque groupe se déplie en liste de sets (cases à cocher), chaque ligne affiche le **nom du set** et **la piste/le plugin concerné**. Un lien « Pourquoi ? » ouvre l'explication courte.

### Étape ③ « Convertir » : voir §3.

### Après la conversion : l'écran de bilan
- Phrase : « 24 sets convertis, 0 erreur, 3 ignorés (déjà faits). »
- Boutons : **Ouvrir le dossier**, **Copier la liste des fichiers**, **Annuler cette conversion** (restauration), **Que vérifier dans Live ?** (courte checklist).
- Liste des fichiers produits (cliquable pour les révéler dans le Finder).

### Onglet « Plugins » (secondaire)
Liste des définitions avec leur statut (✔ validé · ◐ expérimental, bloqué · ○ non pris en charge), **Ajouter**, **J'ai testé dans Live** (ok/ko), **Exporter pour la bêta** (aperçu exact de ce qui sera partagé), **Synchroniser**.

## 3. Suivi de progression et arrêt à tout moment

### Ce que l'utilisateur voit
```
┌ Conversion en cours ──────────────────────────────────────────────────────┐
│  ████████████░░░░░░░░░░░░░░░░  14 / 51 sets      ⏱ 02:10 · reste ≈ 05:30  │
│  Maintenant : « Projet 12 »                                                 │
│    ✔ lecture  ✔ conversion  ● contrôle  ○ écriture                        │
│                                                                            │
│  ✔ 12 convertis   ◐ 2 en réglages par défaut   ⛔ 0 erreur   ○ 0 ignoré    │
│                                                                            │
│  Journal ▾  (se replie ; filtres : tout · avertissements · erreurs)        │
│   10:42:03  Projet 11 — Ozone 8 → Ozone 10 ✔                                │
│   10:42:05  Projet 12 — lecture…                                            │
│                                                                            │
│                                         [ ■ Arrêter ]                      │
└────────────────────────────────────────────────────────────────────────────┘
```
- **Barre globale** (sets faits / total), **temps écoulé et estimé** (moyenne glissante), **élément en cours** et **phase** (lecture → conversion → contrôle → écriture).
- **Compteurs** par résultat, **journal** filtrable, **toujours visible** : le bouton **Arrêter**.
- Le même suivi sert pour l'**analyse** (365 sets), l'**essai à blanc**, la **conversion** et la **restauration**.

### Comportement de l'arrêt
1. Clic sur **Arrêter** → le bouton passe à « Arrêt en cours… » (désactivé) et le message dit « Le set en cours est abandonné proprement. »
2. L'arrêt est **coopératif et rapide** : vérifié entre les sets *et* aux étapes internes d'un set (lecture, conversion, contrôle, avant l'écriture). Délai visé : < 2 s sur un set normal.
3. **Écriture atomique** : le fichier est écrit sous un nom temporaire puis renommé ; si l'arrêt survient avant le renommage, le temporaire est supprimé. Les sets déjà terminés sont conservés.
4. Écran de bilan d'arrêt : « Arrêté : 14 faits, 37 non traités. » avec **Reprendre** (relance en sautant ce qui est fait) et **Annuler ce qui a été fait** (restauration).
5. Aucune perte : fermer la fenêtre pendant une tâche demande confirmation et déclenche le même arrêt propre.

### Exigences moteur (nouvelles)
| Besoin | Mécanisme |
|---|---|
| Progression | `progress(event)` avec `{task, phase, index, total, item, status, message, elapsed}` ; appelé pour chaque set et chaque phase |
| Arrêt | `threading.Event` (`cancel`) passé à `analyze`, `propose`, `convert`, `restore` ; levée de `Cancelled` ; vérifications dans les boucles et entre les phases |
| Écriture sûre | `alsfile.save` écrit `.<nom>.tmp` puis `os.replace` ; nettoyage en cas d'exception ou d'arrêt |
| Une tâche à la fois | `JobManager` avec verrou ; une 2ᵉ demande renvoie « déjà en cours » |
| Reprise | règle `if_exists = skip` (déjà en place) |

## 4. Design visuel (pas de référence fournie)
**Direction : « calme et précise »** — l'outil modifie des projets de musique, il doit inspirer confiance.
- **Palette** : neutres chauds (gris très clair / presque noir), **un seul accent** (bleu-vert sobre) pour l'action principale ; couleurs d'état désaturées : vert (validé), ambre (attention), rouge (erreur), gris (non pris en charge). Toujours doublées d'une icône et d'un mot.
- **Typographie** : police système (SF Pro) ; chemins et noms de fichiers en police à chasse fixe ; échelle à 5 tailles ; interlignage 1,5.
- **Espacement** : grille de 8 px ; cartes aux coins arrondis 12 px ; beaucoup d'air autour du bouton principal.
- **Mouvement** : transitions de 150–200 ms, respect de `prefers-reduced-motion` ; la barre de progression anime sa valeur, pas de décor.
- **Accessibilité** : navigation clavier complète, focus visible, `aria-live` pour la progression, zones cliquables ≥ 44 px, contraste ≥ 4,5:1.
- **Icônes** : SVG en ligne, un seul jeu, pas d'emoji dans l'interface.

**Processus de design sans référence** (recommandé) :
1. Rédiger le **jeu de textes** (microcopy en français) et les **états** de chaque écran (vide, chargement, résultat, erreur, arrêt).
2. Demander à **Claude Design** deux ou trois pistes visuelles de l'écran principal (étapes ①, ②, ③ + bilan) en clair et en sombre.
3. Choisir une piste → en extraire des **jetons de design** (couleurs, rayons, espacements, ombres) dans un fichier CSS.
4. Implémenter l'interface sur ces jetons ; vérifier dans le navigateur intégré (clair, sombre, étroit) ; passer l'agent de revue d'ergonomie.

## 5. Fichiers
- Créer `src/reable/jobs.py` — `Job`, `JobManager`, `Cancelled`, événements de progression.
- Modifier `src/reable/alsfile.py` — écriture atomique.
- Modifier `src/reable/api.py`, `batch.py` — `progress`, `cancel`.
- Créer `src/reable/app/server.py` — serveur JSON local + fichiers statiques.
- Créer `src/reable/app/static/{index.html, app.css, app.js, tokens.css}`.
- Créer `src/reable/app/window.py` — fenêtre pywebview (sélecteur de dossier natif, Finder).
- Tests : `tests/test_jobs.py`, `tests/test_cancel.py`, `tests/test_server.py`.

## 6. Tâches
1. **Écritures atomiques + arrêt coopératif + progression dans le moteur** (TDD) : `alsfile.save` atomique ; `Cancelled` ; `progress`/`cancel` dans `analyze`, `run`, `restore`.
2. **JobManager** : une tâche à la fois, état interrogeable (`/api/jobs/<id>`), arrêt, historique court.
3. **Serveur local + API** : `/api/analyze`, `/api/plan`, `/api/convert`, `/api/restore`, `/api/jobs`, `/api/settings`, `/api/plugins`, `/api/reveal`.
4. **Jeu de textes et états** (document) puis **pistes visuelles via Claude Design** ; choix et **jetons CSS**.
5. **Squelette de l'interface** : en-tête à trois étapes, zone principale, panneau Réglages, étape ① (choix du dossier, glisser-déposer).
6. **Étape ② « Comprendre »** : résumé en phrases, tableau regroupé, « Pourquoi ? », essai à blanc.
7. **Étape ③ Suivi** : barre, phases, compteurs, journal, **Arrêter**, bilan, **Reprendre**.
8. **Panneau Réglages** : tous les choix de `ConvertOptions` avec aperçu en direct du nom ; profil enregistrable.
9. **Restauration et bilan** : annuler une conversion, ouvrir le dossier, copier la liste, checklist « que vérifier dans Live ».
10. **Onglet Plugins** : liste, statuts, ajouter, valider, exporter (aperçu bêta), synchroniser.
11. **Fenêtre pywebview** et lancement (`./run.sh app`), vérification sur le port 3000.
12. **Revue** : agent `ux-simplicity-reviewer`, tests dans le navigateur (clair/sombre/étroit/clavier), corrections.

## 7. Décisions prises (9 oct. 2026)
1. **Design** : exploration par Claude Design (recommandé). Brief de passation : `docs/design/HANDOVER-claude-design.md`.
2. **Fermeture de la fenêtre pendant une tâche** : confirmer, puis arrêter proprement.
3. **Pas de pause** : « Arrêter » + « Reprendre » suffisent.

## 8. (historique) Décisions proposées
1. **Design** : (a) piste « calme et précise » ci-dessus, explorée via Claude Design (recommandé) ; (b) design propre fait directement ici, sans exploration.
2. **Fermeture de la fenêtre pendant une tâche** : confirmer puis arrêter proprement (proposé).
3. **Pause** en plus de l'arrêt ? (non prévu : l'arrêt + « Reprendre » couvre le besoin sans complexité).
