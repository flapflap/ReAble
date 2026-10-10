# ReAble — pour les développeurs

## Depuis les sources
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"      # « app » = fenêtre native (pywebview)
python -m pytest                 # tests
```

## Lancer
```bash
./run.sh app                     # l'application (fenêtre native) ; --browser pour le navigateur
./run.sh convert ~/Music/MesSets --dry-run      # plan : convertible / bloqué (et pourquoi), rien n'est écrit
./run.sh convert ~/Music/MesSets --out ~/Sortie # écrit les copies
./run.sh restore "Set [ReAble].als"             # remet les plugins d'origine
./run.sh scan ~/Music/MesSets --out ~/Desktop   # rapport : plugins, presets, paramètres, automations
./run.sh plugins list                           # plugins connus et leur statut
```
`./run.sh` fonctionne sans activer le venv.

## Pour aller plus loin
- Architecture, pièges du format `.als`, état du projet : [CLAUDE.md](../CLAUDE.md)
- Évaluation technique : [EVALUATION.md](EVALUATION.md) · extensibilité : [EXTENSIBILITY.md](EXTENSIBILITY.md) · options : [OPTIONS.md](OPTIONS.md)
- Définitions de plugins (dépôt séparé) : [ReAble-library](https://github.com/flapflap/ReAble-library)
- Le serveur local de l'application n'écoute que sur 127.0.0.1, avec un jeton par lancement.
- Ancien nom : PlugRescue. Les copies `[PlugRescue]` restent reconnues et restaurables ; le dossier de réglages est migré automatiquement.
