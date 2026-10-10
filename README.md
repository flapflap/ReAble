# ReAble

L'assistant des projets Ableton Live : il repère les plugins qui manquent, remplace ceux qui ont disparu par leur version VST3 ou plus récente, et garde autant que possible les réglages, les presets et les automations.

> Statut : en développement actif, usage personnel de l'auteur. Les conversions validées dans Live 12 sont listées dans le dépôt **[ReAble-library](https://github.com/flapflap/ReAble-library)** ; tout le reste est bloqué par défaut.

## Ce que ça fait
- **Analyse** un dossier de projets (`.als`) et dit, pour chaque plugin tiers, s'il est installé, manquant, ou disponible dans un autre format ou une version plus récente.
- **Convertit** (AU/VST2 → VST3, ancienne version → nouvelle) en écrivant des **copies** `… [ReAble].als` à côté des originaux. Les originaux ne sont jamais modifiés.
- **Duplique** la piste (l'original reste, en sourdine) ou la remplace ; renomme les pistes avec un modèle ; écrit un texte d'information sur la piste.
- **Suit** la progression en direct et peut être **arrêtée à tout moment** (écriture atomique : un fichier est complet ou absent).
- **Annule** : met les copies à la corbeille, ou restaure les plugins d'origine depuis la note de traçabilité.

## Installation
**Application Mac (Apple Silicon)** : télécharge `ReAble.dmg` dans la [dernière version](https://github.com/flapflap/ReAble/releases/tag/latest) (reconstruite à chaque poussée sur `main`), ouvre-le et glisse ReAble dans Applications. L'application n'est pas signée par un développeur Apple : au premier lancement, clic droit sur ReAble > Ouvrir (ou `xattr -dr com.apple.quarantine /Applications/ReAble.app`).

**Depuis les sources** :
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"      # « app » = fenêtre native (pywebview)
```

## Utilisation
```bash
./run.sh app                     # l'application (fenêtre native) ; --browser pour le navigateur
./run.sh convert ~/Music/MesSets --dry-run      # plan : convertible / bloqué (et pourquoi), rien n'est écrit
./run.sh convert ~/Music/MesSets --out ~/Sortie # écrit les copies
./run.sh restore "Set [ReAble].als"             # remet les plugins d'origine
./run.sh scan ~/Music/MesSets --out ~/Desktop   # rapport lisible : plugins, presets, paramètres, automations
./run.sh plugins list                           # plugins connus et leur statut
```
`./run.sh` fonctionne sans activer le venv. Voir [CLAUDE.md](CLAUDE.md) pour l'architecture, les pièges du format `.als` et l'état du projet.

## Définitions de plugins
Le code ne contient aucune définition : elles vivent dans un dépôt séparé, **[ReAble-library](https://github.com/flapflap/ReAble-library)**. Un plugin non validé est **bloqué**. Tu peux ajouter et valider tes plugins en local (`./run.sh plugins add|validate`), puis partager le résultat, de façon anonyme, dans le programme bêta. Voir [docs/EXTENSIBILITY.md](docs/EXTENSIBILITY.md).

## Sécurité et données
- Aucun projet d'origine n'est modifié ; chaque copie est restaurable.
- Le serveur local n'écoute que sur 127.0.0.1, avec un jeton par lancement.
- Rien n'est envoyé hors de ta machine sans action explicite.

## Compatibilité avec l'ancien nom
Le projet s'appelait PlugRescue. Les copies `[PlugRescue]` déjà écrites restent reconnues, restaurables et ignorées par l'analyse ; le dossier de réglages est migré automatiquement.

## Licence
[MIT](LICENSE). Ableton et Ableton Live sont des marques d'Ableton AG ; ce projet n'est ni affilié ni approuvé par Ableton.
