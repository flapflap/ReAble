#!/bin/bash
# Lanceur ReAble : utilise le Python du projet sans dépendre de l'installation pip.
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
[ -x "$PY" ] || PY=python3
PYTHONPATH="$DIR/src${PYTHONPATH:+:$PYTHONPATH}" exec "$PY" -m reable "$@"
