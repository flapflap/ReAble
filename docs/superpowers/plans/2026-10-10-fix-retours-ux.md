# ReAble — Plan de correction : premier retour UX (10 oct. 2026)

Source : `docs/RETOURS-UX.md` (version testée 41c819c). Fichiers concernés : `src/reable/app/static/{app.js,app.css,tokens.css}`, `src/reable/app/{window.py,server.py,logic.py}`, `packaging/build_macos.sh`.
Branche proposée : `fix/retours-ux-1`. Tests : `pytest` + parcours dans le navigateur intégré (port 3000) + vérification dans la fenêtre native par Benoit.

## Lot A — Bugs (à corriger d'abord)
| # | Retour | Cause probable | Correction |
|---|---|---|---|
| A1 | Glisser-déposer sans effet ni message | Dans pywebview ≥ 5, `pywebviewFullPath` n'est fourni qu'aux gestionnaires **Python** (`window.dom.document.events.drop += DOMEventHandler(...)`), pas au JavaScript de la page. `f.pywebviewFullPath` est donc vide, et le message d'aide n'apparaît pas (ou disparaît). | Enregistrer un gestionnaire de dépôt dans `window.py`, récupérer le chemin, le passer à la page (`evaluate_js`) ; la page analyse le dossier. Si le dépôt est un fichier `.als`, prendre son dossier parent. Message d'erreur visible dans tous les cas (dépôt d'autre chose qu'un dossier). Test : ajouter à `tests/test_window.py` (sans fenêtre). **À valider par Benoit dans la fenêtre native.** |
| A2 | Étape « 3 · Convertir » illisible (texte sombre sur fond bleu) | Le style « désactivé » (`.nav.off`) l'emporte sur `.nav.on` quand l'étape active n'est pas cliquable. | CSS : `.nav.on` prioritaire, texte et icône blancs. Vérifier aussi le contraste en mode sombre. |
| A3 | Sous-titre permanent « Aucun dossier choisi » | Texte fixe de la vue « Choisir » (`frame("Aucun dossier choisi", …)`). | Supprimer la phrase et afficher le logo à la place (voir B1). |

## Lot B — Structure et vocabulaire de l'interface
| # | Retour | Décision proposée |
|---|---|---|
| B1 | Logo en haut à gauche | Réutiliser `packaging/ReAble-icon-1024.png` (réduit) dans la barre de titre, à côté de « ReAble ». |
| B2 | Bouton Analyser éloigné du sélecteur | Sur l'écran « Choisir » : le bouton **Analyser** est placé sur la même ligne que le champ et « Choisir… » (le champ, puis Choisir…, puis Analyser). Plus de bouton Analyser dans la barre du haut. |
| B3 | « Comprendre » → « Valider » | Renommer l'étape 2 dans la barre latérale, les textes d'aide et la doc. |
| B4 | Hiérarchie de l'information brouillonne ; informations répétées | Réorganiser l'écran « Valider », de haut en bas : **1. la liste des conversions**, **2. les options de conversion** (aujourd'hui dans le panneau de droite), **3. les actions** (Réanalyser, Essai à blanc, Convertir). Le résumé en haut, la barre d'état et les phrases d'aide ne répètent plus les mêmes chiffres : un chiffre = un seul endroit. Le panneau de droite disparaît ; les options passent sous la liste, en colonne simple. |
| B5 | Boutons plutôt que liens texte | Remplacer les liens (« Voir les projets », « Voir lesquels », « Copier la liste », « Afficher dans le Finder », « Ajouter un dossier de gabarits… ») par de petits boutons (style secondaire). |

> Pour B4, je recommande de passer par Claude Design pour une maquette courte de l'écran « Valider » avant de coder (même méthode que pour la direction B). À décider.

## Lot C — Onglet Plugins et réglages
| # | Retour | Décision proposée |
|---|---|---|
| C1 | Capitaliser les noms de plugins | Afficher le `name` lisible de la définition (« Massive X », « Ozone 10 ») plutôt que l'identifiant (`ozone-10`). Si absent, capitaliser. |
| C2 | Colonne « Source » incompréhensible | Remplacer par une colonne « Origine » avec des mots clairs : « Fournie avec ReAble », « Bibliothèque », « Ajoutée par vous ». Info-bulle de légende. |
| C3 | Message « plugins validate » sans action possible | Écran de **validation d'un plugin** : pour un plugin « Expérimental · bloqué », bouton « Tester ce plugin », avec des instructions pas à pas (1. ReAble crée un projet de test, 2. ouvrez-le dans Live, 3. répondez : « Le son et les réglages sont identiques ? Oui / Non / Il manque des réglages »). Le résultat est enregistré en local (validation personnelle) ; l'envoi anonyme reste optionnel et explicite. Il faut un nouveau point d'entrée de l'API (`/api/plugins/test`, `/api/plugins/validate`), qui s'appuie sur `registry.py` et `rewrite_file`. |
| C4 | Onglet Réglages | Nouvel onglet « Réglages » dans « Bibliothèque » : options par défaut (reprend les options de conversion), dossiers de plugins supplémentaires (champ facultatif, avec explication : utile seulement si les plugins ne sont pas dans les dossiers du système), dossiers de gabarits, dossier de la bibliothèque de définitions. Stockage dans le dossier utilisateur. Question ouverte : les dossiers de plugins sont-ils vraiment nécessaires ? Live les lit déjà ; on ne les ajoute que si un test réel le justifie. |

## Lot D — Installation, menu, finitions
| # | Retour | Décision proposée |
|---|---|---|
| D1 | DMG sans indication de glisser vers Applications | Fond d'image dans le DMG (flèche, texte « Glissez ReAble dans Applications »), fenêtre à taille fixe et icônes positionnées (création avec `create-dmg` ou AppleScript Finder dans `build_macos.sh`). Je cherche des exemples de fonds usuels avant de dessiner. |
| D2 | Menu : version simplifiée utile aux rapports de bug | Menu « ReAble » : **À propos de ReAble** (version, commit, date de construction, version de macOS, version de Live détectée, nombre de définitions) avec un bouton **Copier les informations** à coller dans un rapport de bug. J'interprète « version simplifiée » comme ce bloc de diagnostic ; à confirmer. |
| D3 | Icône peu professionnelle | Hors bêta : noté dans la feuille de route. Piste : demander une proposition à Claude Design ou à un illustrateur. |

## Ordre d'exécution
1. **A1–A3** (bugs) : 0,5 jour. Livrable testable dans la fenêtre native.
2. **B1–B5** (structure, vocabulaire, boutons) : 1 jour, après maquette si validée.
3. **C1–C2** (affichage plugins) : 0,25 jour.
4. **D1–D2** (DMG, À propos) : 0,5 jour.
5. **C3–C4** (validation d'un plugin, Réglages) : 1,5 jour. C'est le plus gros chantier et il conditionne l'intérêt de la bêta (un testeur doit pouvoir valider un plugin).
6. Chaque lot : tests automatiques, vérification dans le navigateur intégré, DMG reconstruit, retour de Benoit.

## Décisions de Benoit (10 oct. 2026)
1. Maquette courte (Claude Design) pour l'écran « Valider » avant de coder B4 : brief dans `docs/design/BRIEF-ecran-valider.md`.
2. D2 : « À propos » = un simple numéro de version (type 0.1) pour savoir quelle version de ReAble est utilisée ; pas de bloc de diagnostic détaillé.
3. C4 : pas besoin de dossiers de plugins personnalisés, sauf si l'on peut savoir ce que Live lit (inutile sinon).
4. C3 : validation d'un plugin en local seulement pour la bêta ; envoi anonyme plus tard.

## Avancement
- ✅ Lot A (branche `fix/retours-ux-1`) : A1 dépôt natif côté Python, A2 contraste de l'étape active, A3 + B1 + B2 (logo, bouton Analyser sur la ligne du champ). Tests : 109 verts ; écran « Choisir » vérifié dans le navigateur ; le dépôt est à valider par Benoit dans la fenêtre native.
