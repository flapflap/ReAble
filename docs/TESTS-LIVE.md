# Tests à faire dans Ableton Live

But : combler les limites du prototype `rewrite` (voir la discussion du 7 oct. 2026).
**Convention :** un set par test, dans `ReAble/tests-live/`, nommé `Tnn - titre.als`
(le dossier est hors Git). Pour chaque test, note dans le nom de piste ce que tu as réglé.
Ne sauvegarde pas par-dessus un set : un fichier par état (avant / après).
Priorité : ★★★ très utile · ★★ utile · ★ confort.

| # | Prio | Durée | Test | Ce que j'en tire |
|---|---|---|---|---|
| T1 | ★★★ | 10 min | **Automations** — Massive X AU et VST3, même preset. Dans chacun, configure 4 paramètres (ex. Macros 1 à 4) puis automatise-en 2 en arrangement et 1 en enveloppe de clip. Configure en plus **un 5ᵉ paramètre dans l'AU seulement**, et automatise-le. Sauve `T1 - automations.als`. | Comment Live nomme/identifie les paramètres entre formats, et si le « 5ᵉ paramètre » est bien perdu. Permet de réparer le remapping (créer le paramètre dans le gabarit au lieu de le perdre). |
| T2 | ★★★ | 10 min | **Rack et instances multiples** — Massive X AU dans un Instrument Rack (2 chaînes), un 2ᵉ Massive X AU (autre preset) sur une autre piste, un 3ᵉ sur la piste Return. Sauve `T2 - racks.als`. Puis `T2b` : la même chose avec un gabarit VST3 sur une piste séparée. | Si `rewrite` convertit correctement toutes les instances (rack, return, plusieurs presets) et garde chaque état distinct. |
| T3 | ★★★ | 15 min | **Autres plugins NI, même preset en AU et en VST3** — Battery 4 (kit chargé), Kontakt 8 (1 instrument chargé, un réglage modifié), FM8. Une piste AU + une piste VST3 par plugin. Sauve `T3 - NI.als`. | Si le bloc d'état est le même qu'avec Massive X (alors `rewrite` marche pour toute la famille NI) ou s'il faut un décodeur par plugin. Battery 4 et Kontakt pèsent beaucoup dans tes sets (362 + 21 occurrences). |
| T4 | ★★★ | 15 min | **Autres éditeurs, AU vs VST3** — 3 plugins d'éditeurs différents installés dans les deux formats (ex. Phase Plant, Snap Heap, Reason Rack Plugin, Opus). Même preset, 2-3 réglages modifiés. Sauve `T4 - autres editeurs.als`. | Si le principe « copier le bloc d'état » s'étend hors de NI, ou si le format d'état AU diffère du VST3 (alors `rewrite` est limité à NI). |
| T5 | ★★★ | 10 min | **VST2 vs VST3** — Massive (le premier), Kontakt (VST2 « Ni$D » et Kontakt 7/8 VST3), Replika ou FM8 en VST2 et VST3, même preset. Sauve `T5 - VST2.als`. | Le gros du travail : 764 de tes plugins manquants sont des VST2. Montre si VST2 → VST3 est faisable. |
| T6 | ★★★ | 10 min | **Rendu audio** — Dans le set de test déjà réécrit (`[ReAble]`) : mets le même clip MIDI (une note tenue 4 s + un accord) sur les pistes AU d'origine et VST3 converti. Exporte chaque piste solo en WAV (même durée, sans normalisation), dans `tests-live/audio/`. | Je soustrais les deux WAV : si la différence est quasi nulle, la conversion est **audiblement** fidèle (au-delà de « les valeurs sont égales »). |
| T7 | ★★ | 10 min | **Réglages du device** — Sur un Massive X AU : active MPE, renomme le device, désactive-le, replie-le, règle un sidechain (ex. sur Ozone/Neutron) et mets-le en Freeze sur une 2ᵉ piste. Sauve `T7 - reglages.als`. | Quels réglages propres au device `rewrite` perd aujourd'hui (il prend ceux du gabarit) et lesquels recopier de l'AU. |
| T8 | ★★ | 10 min | **Nom de preset et navigateur** — Charge un preset via le navigateur de Live, un autre via le navigateur interne du plugin, un 3ᵉ via « Hot-Swap ». Ajoute un « Save as default » sur un Massive X. Sauve `T8 - presets.als`. | D'où vient l'étiquette de preset affichée par Live (`PresetRef`, `Name`) pour la reproduire correctement dans le set réécrit. |
| T9 | ★★ | 5 min | **Notes et noms (pour la traçabilité)** — Sur une piste et sur un device : écris un texte d'info (clic droit sur le titre → « Edit Info Text »), renomme la piste avec un repère (ex. « Lead [AU→VST3] »), ajoute un commentaire de clip. Sauve `T9 - notes.als`. | Où Live stocke ces textes (`Annotation`), leur longueur max, si les accents/retours à la ligne passent. Sert à écrire la note de sauvegarde. |
| T10 | ★★ | 10 min | **Anciennes versions de Live** — Ouvre un vieux set (Live 9/10) qui contient Massive en VST2, puis sauvegarde-le sous un autre nom dans Live 12 (`T10 - ancien set resauve.als`). Envoie-moi aussi l'original. | Comment Live 12 réécrit lui-même un plugin VST2 : schéma des anciens sets, utile pour que `rewrite` gère les 365 sets de MesProjets (Live 8 à 12). |
| T11 | ★★ | 5 min | **Plugin absent** — Avec un plugin que tu peux désinstaller sans risque (ou renomme temporairement le `.vst3`/`.component` d'un plugin gratuit), ouvre un set qui l'utilise puis sauve-le. `T11 - plugin absent.als`. | Ce que Live garde pour un plugin manquant (placeholder, état conservé ?). Cela dit si l'état est récupérable même sans le plugin. |
| T12 | ★ | 5 min | **Même preset, deux fois** — Charge le même preset de Massive X en AU deux fois, sans rien toucher. `T12 - determinisme.als`. | Si deux états du même preset sont identiques octet par octet (sinon, la comparaison d'états doit ignorer du « bruit » comme des horodatages). |

## Ordre conseillé
1. T6 et T1 (valident la fidélité audio et les automations, les deux gros risques).
2. T5 puis T3 et T4 (étendent à VST2 et aux autres plugins).
3. T2, T7, T9 (robustesse et traçabilité).
4. T8, T10, T11, T12.

## Ce que je fais de chaque envoi
Je lance `./run.sh scan` et `./run.sh compare` sur le set, j'ajoute les résultats à `docs/EVALUATION.md`, puis je dis ce qui devient possible (plugins pris en charge, limites levées) et ce qu'il reste à tester.

---

# Fichiers de test générés par ReAble (dans `tests-live/`)

Générés à partir de **vrais sets de MesProjets** (copies : les originaux ne sont pas touchés).
Pour chacun : ouvre-le dans Live, note ce qui se passe, **ne sauvegarde pas** par-dessus (ou « Enregistrer sous… »),
puis dis-moi le résultat. Si Live signale un problème (message, plugin manquant, set refusé), recopie le texte exact.

| Fichier | Ce qui a été fait | À vérifier dans Live |
|---|---|---|
| `Projet B [ReAble G1 Massive VST2-VST3].als` | 2 × Massive (VST2) → Massive (VST3) | S'ouvre sans erreur ? Les 2 Massive se chargent en VST3 avec leur preset et leurs réglages d'origine (compare avec l'original) ? Même son ? |
| `Projet D [ReAble G2 Kontakt VST2-Kontakt8].als` | Kontakt (VST2) → Kontakt 8 (VST3) | Kontakt 8 charge-t-il l'instrument et les samples de la piste ? Le patch sonne-t-il pareil ? (set de Live 11.0.2 : teste aussi qu'il s'ouvre) |
| `Projet E [ReAble G2b Kontakt VST2-Kontakt8].als` | 2 × Kontakt (VST2) → Kontakt 8 | Même chose, avec 2 instances de contenus différents |
| `Projet C [ReAble G3 Kontakt5-Kontakt8].als` | Kontakt 5 (VST2, id `NiO5`) → Kontakt 8 (VST3) | Kontakt 8 relit-il un état de Kontakt 5 ? (Les 2 enveloppes « sans cible » signalées existaient déjà dans l'original.) |
| `Test Plugins AU VST3 [ReAble G5 notes et noms].als` | Notes de device (texte long, accents, JSON, emoji, retours à la ligne) et noms de piste avec `[AU→VST3]`, emoji, guillemets | Le nom des 2 pistes s'affiche-t-il correctement ? Les notes de device (clic droit sur le titre → *Edit Info Text*) sont-elles lisibles, entières ? Le set se sauvegarde-t-il sans les perdre ? |

## Ce que ces fichiers remplacent
- **T5 (VST2 vs VST3)** et une partie de **T3** : G1 à G3 testent directement la conversion, sans que tu aies à créer des sets.
- **T9 (notes et noms)** : G5. Piste : les pistes n'ont pas de champ de note dans Live 12.4, seuls les devices en ont (`Annotation`).

## Ce qui ne peut pas être généré (il faut Live)
T1 (automations configurées côté Live), T4 (autres éditeurs en AU), T6 (rendu audio), T7, T8, T11, T12.

## Limites constatées pendant la génération
- **Anciens sets** (Live 9/10, sans `Pointee`/`NextPointeeId`) : refusés. Leur XML est trop différent du gabarit Live 12 ; il faudra d'abord les ouvrir et les sauvegarder dans Live 12 (voir T10).
- **Ozone 8 (VST2) → Ozone 10 (VST3)** : refusé par le garde-fou. Le conteneur d'état d'iZotope a les mêmes champs dans un autre ordre entre VST2 et VST3 ; il faudra un adaptateur dédié.

---

# Lot G6 — `reable convert` sur MesProjets (dans `tests-live/batch/`)

Généré par : `./run.sh convert ~/Music/MesProjets --all --tag-track --out tests-live/batch`
(7 sets de Live 11/12, 12 devices ; les 90 sets de Live ≤ 10 contenant des plugins convertibles sont **bloqués** :
ils doivent d'abord être ouverts et enregistrés dans Live 12 ; leur liste est dans `tests-live/batch-report.json`).

Ce qui change par rapport à G1–G5 : chaque device converti porte une **note ReAble** (JSON, avec l'original
embarqué si ≤ 100 Ko) et chaque piste concernée est **renommée** `… [VST2→VST3]`.

| Set | Conversion | À vérifier dans Live |
|---|---|---|
| `Projet B` | 2 × Massive (VST2) → VST3 | Notes de 8–9 Ko lisibles (*Edit Info Text*) ; pistes renommées ; le set s'ouvre et se sauvegarde. |
| `Projet G` | 4 devices (dont une note de 72 Ko) | Une **note de 72 Ko** est-elle acceptée, lisible et conservée après sauvegarde dans Live ? |
| `Projet C` | Kontakt 5 → Kontakt 8 | Chargement de l'instrument ; nom de piste. |
| `Projet D`, `Projet E`, `Projet F`, `Projet 26` | Kontakt → Kontakt 8 | Chargement des instruments/samples ; Projet 26 et 00126 ont 3 devices chacun. |

Restauration (à tester aussi) : `./run.sh restore "<set [ReAble].als>"` produit `… [Restauré].als` ;
si la note n'embarque pas l'original (trop gros) : `--original "<set d'origine>"`.


---

# Lot H — options de workflow (dans `tests-live/options/`)

| Dossier | Réglages | À vérifier dans Live |
|---|---|---|
| `H1-test-massivex` | `duplicate_track`, nom `{track} — {preset}` | La piste d'origine `1-Massive X [original]` est **mutée** et garde son AU ; la copie `1-Massive X — Abstract City` joue en VST3 avec les mêmes réglages. Les deux ont leurs clips. Pas de message d'erreur à l'ouverture. |
| `H2-projets-duplicate` | `duplicate_track`, nom `{track} [{from}→{to}]` (7 sets) | Mêmes vérifications sur de vrais sets : pistes dupliquées au bon endroit, volumes/sends/routages identiques sur la copie, groupes respectés. |
| `H3-projets-replace-preset` | remplacement, nom `{track} — {preset}`, `--missing-preset plugin` | Noms du type `Horns — Kontakt 8` (le preset de Kontakt n'est pas décodé → nom du plugin). |

Points sensibles de `duplicate_track` : routage de sortie vers un groupe, sends, automations de piste, clips de session et d'arrangement, couleur. Dis-moi tout écart avec la piste d'origine.

**Incident (9 oct. 2026) — H1 refusé par Live** : « corrupt (non-unique Pointee IDs) ». Cause : la duplication de piste ne renouvelait que
`Pointee`/`AutomationTarget`/`ModulationTarget`, alors que l'espace d'Id global de Live comprend aussi les `ControllerTargets.N` et toutes les
cibles `…ModulationTarget`. Corrigé (`is_pointee`), test de régression ajouté, et un doublon d'Id **bloque** désormais l'écriture d'un set.
Les fichiers du lot H ont été régénérés : à rouvrir.

**Incident 2 (9 oct. 2026) — H1 refusé par Live** : « Unknown attribute 'Id' (line 12987) ». Cause : la règle « toute balise finissant par
`Target` a un Id » ajoutait un `Id` à `<Target Value="AudioIn/None"/>` (routage du sidechain). Corrigé ; ajout d'un **contrôle de schéma** :
après conversion, aucun élément ne peut porter un attribut que son type n'avait pas dans le set d'origine ou le gabarit. Une violation bloque l'écriture.
Les lots G (déjà validés), G6 et H ont tous été revérifiés contre les attributs de 77 sets de Live 11/12 : aucun écart.

**Correction** : les pistes ont bien un texte d'info (`MidiTrack/Name/Annotation`, en bas à gauche dans Live) — mon constat « pas de champ de note sur les pistes » était faux.
H1 (duplication) validé dans Live le 9 oct.

| Dossier | À vérifier |
|---|---|
| `options/H4-track-info` | Piste 1 avec le texte « Test » : après conversion, ce texte est conservé et suivi d'un bloc « Converti par ReAble le … / Massive X : AU → VST3 / Preset : Abstract City / Piste d'origine : … ». La copie et l'originale (mutée) ont chacune leur texte. |

---

# Lot O — mise à niveau d'Ozone vers Ozone 10 (dans `tests-live/ozone/`)

Générés par `./run.sh convert <set> --family ozone --templates "Test Plugins AU VST3 Project" --state-mode <mode> --replace-mode duplicate_track`.
Les Ozone de ces sets sont sur la **piste principale** : elle ne peut pas être dupliquée, donc `keep_device` s'applique
automatiquement (le nouveau Ozone 10 est inséré **avant** l'ancien, qui reste désactivé et renommé `… [ancien]`).

Trois modes par source (dossiers `transfer/`, `header/`, `none/`), quatre sources chacun (12 sets) :
| Mode | Ce qui est injecté dans Ozone 10 |
|---|---|
| `transfer` | l'état de l'ancien Ozone, conteneur ré-emballé, identifiant d'origine conservé |
| `header` | idem, avec l'identifiant et la version du conteneur d'Ozone 10 |
| `none` | rien : Ozone 10 démarre avec ses réglages par défaut (l'ancien preset reste noté dans le texte d'info) |

Sources : `Oz7-VST2` (Ozone 7, Projet C), `Oz9-VST2` (Projet 26), `Oz9-VST3` (Projet 24), `Oz8-VST3` (Projet G).
Pour chaque set, dis-moi : (1) s'il s'ouvre, (2) si Ozone 10 charge sans erreur, (3) si les modules et réglages correspondent à l'ancienne chaîne
(compare avec l'original ; Ozone 9 et 8 ne sont pas installés sur ce Mac), (4) pour `none`, si le plugin démarre bien avec ses réglages par défaut (état vide).
Hypothèses : Ozone 9 → 10 devrait fonctionner en `transfer` (même identifiant de conteneur) ; Ozone 8 et 7 peuvent exiger `header` ou échouer.

## Lot O — que regarder (repères mesurés dans les états d'origine)
Ozone 10 sur la piste principale, nouveau device actif avant l'ancien (grisé, `… [ancien]`). Comparer **`transfer`** et **`header`** à **`none`** (réglages par défaut) :
si les valeurs ne sont pas celles de `none`, l'état a été repris.

| Set | Module | Paramètre | Ancien | Par défaut Ozone 10 (`none`) |
|---|---|---|---|---|
| `Oz9-VST3` (Projet 24) | Dynamic EQ | Band 4 Gain | −3,49 dB | 0 dB |
| | Dynamic EQ | Band 4 Threshold | −50,1 dB | −30 dB |
| | Dynamic EQ | Band 3 Gain / Threshold | +0,5 / 0 dB | 0 / −30 dB |
| | Dynamics | Band 1 Comp Threshold | −20 dB | −12 dB |
| `Oz9-VST2` (Projet 26) | Vintage Compressor | Ratio / Threshold | 4:1 / −18 dB | 1,5:1 / −12 dB |
| | Vintage Limiter | Threshold | −6 dB | −2 dB |
| `Oz8-VST3`, `Oz7-VST2` | — | seulement 82 / 0 paramètres communs avec Ozone 10 | — | transfert improbable ; vérifier surtout qu'il n'y a pas d'erreur |

Enregistrer le résultat : `./run.sh plugins validate ozone --result ok|ko --variant transfer|header|none --live 12.4`.

**Incident 3 (9 oct. 2026) — lot O refusé par Live** : « corrupt (Non-unique list ids) ». Cause : en `keep_device`, le nouveau device reprenait l'`Id` de liste de
l'ancien (`Id="0"`) dans la même liste `Devices` ; Live exige des `Id` distincts entre enfants d'une même liste. Corrigé (Id = max + 1) et contrôle généralisé
`check_list_ids` : appliqué à toutes les listes, vérifié sur les 365 sets d'origine (aucun écart) ; un doublon bloque l'écriture.
Les 12 sets du lot O ont été régénérés ; les 42 fichiers de `tests-live/` passent les contrôles Id globaux, Id de liste et schéma.

**Résultat (9 oct. 2026)** : avec l'état écrit **aussi dans `ControllerState`** (comme le font Ozone 8 et 9 en VST3), Ozone 10 affiche des paramètres repris.
Sans cela, il démarre avec ses réglages par défaut. C'est désormais le comportement par défaut de la famille Ozone (`copy_controller_state` dans la définition).
Le lot `tests-live/ozone/` a été régénéré dans cette configuration (3 modes × 4 sources).

## Vérifier une mise à niveau sans l'ancien plugin : `reable verify`
Si l'ancien plugin n'est plus installé (Ozone 9, 8, 7), on ne peut pas comparer à l'œil. À la place : ouvrir le set converti dans Live, **l'enregistrer sous un autre nom**
(Live redemande alors son état au nouveau plugin), puis comparer cet état à celui de l'original :
`./run.sh verify <original> <re-sauvegardé> --plugin "Ozone 9" --target "Ozone 10" --default-from <set avec Ozone 10 par défaut>`.
Verdicts : « repris » (≥ 80 % des réglages qui diffèrent du défaut sont conservés), « non repris (réglages par défaut) », « partiellement repris »,
« indéterminé » (moins de 10 réglages comparables, typiquement Ozone 8/7 dont la structure diffère d'Ozone 10).
Dossier de dépôt : `tests-live/saved/`.

## Résultats du lot Ozone (9 oct. 2026), mesurés par `reable verify` sur les sets re-sauvegardés dans Live
| Source → cible | Résultat |
|---|---|
| Ozone 9 VST3 → Ozone 10 | **repris** : 65 réglages sur 65 |
| Ozone 9 VST2 → Ozone 10 | **repris** : 63 réglages sur 64 (seule la sélection de bande « Dynamics / Active Band » a changé : 2 → 3) |
| Ozone 8 VST3 → Ozone 10 | **ignoré** : Ozone 10 ré-enregistre exactement ses réglages par défaut (0 écart sur 1346 valeurs) |
| Ozone 7 VST2 → Ozone 10 | **ignoré** : idem |
Condition pour Ozone 9 : l'état doit aussi être écrit dans `ControllerState` (défini dans la définition). Ozone 8 et 7 : conversion en réglages par défaut + ancien nom de preset en note.
