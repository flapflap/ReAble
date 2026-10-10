#!/bin/bash
# Construit ReAble.app (PyInstaller) puis ReAble-<version>.dmg (hdiutil). Usage : packaging/build_macos.sh [version]
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
VERSION="${1:-$(git describe --tags --always 2>/dev/null || echo dev)}"
PY="${PYTHON:-.venv/bin/python}"
OUT="dist"
rm -rf build "$OUT" packaging/_snapshot
mkdir -p "$OUT"

# 1. Définitions livrées avec l'application : instantané de la bibliothèque (ReAble-library)
#    LIBRARY_DIR = clone de ReAble-library ; à défaut, la copie de test du dépôt (même contenu au moment de sa mise à jour).
mkdir -p packaging/_snapshot
if [ -n "${LIBRARY_DIR:-}" ] && [ -d "$LIBRARY_DIR/definitions" ]; then
  cp -R "$LIBRARY_DIR/definitions/." packaging/_snapshot/
  echo "Définitions : instantané de $LIBRARY_DIR"
else
  cp tests/definitions_fixture/test-definitions.json packaging/_snapshot/definitions.json
  echo "Définitions : copie du dépôt (tests/definitions_fixture)"
fi

# 2. L'application
"$PY" -m PyInstaller --noconfirm --clean --windowed --name ReAble \
  --osx-bundle-identifier io.github.flapflap.reable \
  --paths "$ROOT/src" \
  --add-data "$ROOT/src/reable/app/static:reable/app/static" \
  --add-data "$ROOT/packaging/_snapshot:reable/definitions_snapshot" \
  --collect-submodules reable \
  --collect-all webview \
  --distpath "$ROOT/$OUT" --workpath "$ROOT/build" --specpath "$ROOT/build" \
  "$ROOT/packaging/reable_app.py"

APP="$OUT/ReAble.app"
# Version lisible dans Finder (Informations)
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString ${VERSION#v}" "$APP/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion ${VERSION#v}" "$APP/Contents/Info.plist" 2>/dev/null || true
# Signature « ad hoc » (obligatoire pour qu'un binaire arm64 se lance ; ce n'est PAS une signature de développeur)
xattr -cr "$APP"          # retire les attributs étendus (Finder, provenance) : codesign les refuse
codesign --force --deep --sign - "$APP"

# 3. Le DMG : l'application + un raccourci vers Applications
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="$OUT/ReAble-${VERSION}.dmg"
hdiutil create -volname "ReAble" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG" >/dev/null
rm -rf "$STAGE"
echo "OK : $DMG ($(du -h "$DMG" | cut -f1))"
