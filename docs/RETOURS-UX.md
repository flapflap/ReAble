# Retours UX — test de ReAble (version signée et notarisée)

> Traitement : voir `docs/superpowers/plans/2026-10-10-fix-retours-ux.md`

Version testée : 41c819c  (commit : ______)   Date : 10/09/2026

Comment remplir : une ligne par remarque, en vrac. Écran concerné, ce que tu faisais, ce que tu attendais. Gravité : 🔴 bloquant · 🟠 gênant · 🟡 détail · 💡 idée. Colle les captures dans `docs/retours/` et cite le nom du fichier.

## Installation et premier lancement
- [x] Ouverture sans avertissement macOS :
- [x] Fenêtre, icône du Dock, menu : manque une version simplifiée dans le menu (utile pour remontée de bug)
- Remarques : Quand on ouvre le dmg on pourrait avoir une indication qu'il faut glisser le app dans le raccourci Applications (très courant), trouvez des exemples sur le web
- L'icone ne fait pas très pro. A retravailler, pas important pour la beta

## Choix du dossier (sélecteur, glisser-déposer)
- Le glisser-déposer n'a pas fonctionné, pas de message d'erreur, le sélecteur ok
- En haut à gauche sour le titre, la phrase dit en permanence "Aucun dossier choisi" info inutile, supprimer, mettre le logo

## Analyse (progression, groupes, inspecteur)
- Le bouton Analyser est en haut à droite top éloigné du selecteur de dossier

## Conversion (options, progression, résultat)
- Renommer "Comprendre" en "Valider" dans les étapes de gauche
- La hierarchie des informations et l'information design globale est brouiloonne. Ré organiser les informations par groupe logique et ne pas multiplier la même info à plusieurs endroits. Garder un ordre logique: De haut en bas: 1. la liste des conversions. 2. Les options de conversions 3. les actions
En général: utiliser des boutons plutôt que des liens texte sur les actions (Voir les projets, etc.)

## Arrêter / Reprendre / Annuler
-

## Copies dans Live (ouverture, plugins, états, automations)
-![alt text](<Capture d’écran 2026-10-10 à 10.55.11.png>)
Le texte n'est pas lisible

## Onglet Plugins et réglages
- pas d'onglet réglages pourrait être utile pour indiquer les paramètres par défaut mais aussi indiquer les dossiers de plugin si différents des systèmes (nécessaires ?)
- l'onglet Plugin:
  - Capitaliser le nom des plugin
  - L'onglet source est incompréhensible tel quel
  - cet indication n'a aucun sens si l'utilisateur ne peut pas faire l'action, il faut un écran pour pouvoir valider un plugin avec des instructions
  ![alt text](<Capture d’écran 2026-10-10 à 10.57.45.png>)


## Textes et vocabulaire (compréhensible ? trop technique ?)
-

## Idées et fonctions manquantes
-

## Bugs (étapes pour reproduire)
-

## Verdict avant la bêta
- Prêt pour des testeurs ? oui / non / avec réserves :
- 3 priorités :
  1.
  2.
  3.
