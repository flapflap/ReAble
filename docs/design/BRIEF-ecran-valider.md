# Brief Claude Design — écran « Valider » (étape 2)

Contexte : ReAble, utilitaire Mac (direction B v2 « utilitaire Mac », voir `docs/design/claude-design-v2/` et les jetons `src/reable/app/static/tokens.css`). Fenêtre 1100 × 720, barre latérale d'étapes (Choisir · Valider · Convertir, puis Bibliothèque : Plugins, Réglages).

Problème (retour de test) : l'écran est brouillon. La même information apparaît à plusieurs endroits (résumé du haut, lignes du tableau, barre d'état, phrases d'aide, panneau de droite) ; les actions sont des liens texte dispersés.

## À produire
Une seule maquette, 2 états :
1. **Écran « Valider »** avec 6 groupes de conversion : « Massive → Massive X (VST3) · Validé · 12 projets », « Kontakt 5 → Kontakt 8 · Validé · 4 », « Ozone 9 → Ozone 10 · Réglages par défaut · 3 », « Neutron · Gabarit requis · 2 », « Projets Live trop anciens · Action requise · 5 », « Plugins sans équivalent · 7 plugins ».
2. Le même écran avec un groupe déplié (liste des projets).

## Structure imposée (de haut en bas)
1. **La liste des conversions** (tableau : case à cocher, plugin, état, nombre de projets, bouton « Voir les projets »). Les groupes bloqués n'ont pas de case ; leur action est un **bouton** (« Ajouter un dossier de gabarits… », « Copier la liste »).
2. **Les options de conversion**, en dessous, en une colonne simple (plus de panneau latéral) : Piste d'origine (dupliquer / remplacer) · Nom des pistes converties (+ aperçu) · Texte d'information sur la piste · Où écrire les copies · Si la copie existe déjà.
3. **Les actions**, en pied de page fixe : Réanalyser · Essai à blanc · **Convertir N projets** (principal).

## Contraintes
- Un chiffre = un seul endroit (pas de répétition dans la barre d'état, le résumé et le tableau). Un résumé d'une ligne au plus, sinon le tableau suffit.
- Boutons, pas de liens texte, pour toutes les actions.
- Textes en français, ton simple et didactique ; pas de jargon (« gabarit » expliqué par une info-bulle).
- Clair et sombre ; contrastes lisibles (état actif de la barre latérale en blanc sur bleu).
- Livrer HTML/CSS réutilisable avec les jetons `--pr-*` existants.
