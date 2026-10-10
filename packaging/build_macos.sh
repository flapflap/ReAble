#!/bin/bash
# Construit ReAble.app (PyInstaller) puis ReAble-<version>.dmg (hdiutil). Usage : packaging/build_macos.sh [version]
#
# Signature (facultative) : SIGN_IDENTITY="Developer ID Application: Nom (TEAMID)" -> runtime renforcé + horodatage.
#   Sans SIGN_IDENTITY : signature « ad hoc » (l'application se lance mais macOS affiche un avertissement).
# Notarisation (facultative, exige SIGN_IDENTITY) : NOTARY_PROFILE="nom-du-profil" (xcrun notarytool store-credentials)
#   ou NOTARY_APPLE_ID + NOTARY_PASSWORD (mot de passe d'application) + NOTARY_TEAM_ID.
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
  --icon "$ROOT/packaging/ReAble.icns" \
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
SIGNED=0
if [ -n "${SIGN_IDENTITY:-}" ] && [ "$SIGN_IDENTITY" != "-" ]; then
  # Signature de développeur : chaque binaire d'abord (du plus profond au plus haut), puis le paquet, avec le runtime renforcé
  while IFS= read -r f; do
    codesign --force --timestamp --options runtime --entitlements "$ROOT/packaging/entitlements.plist" --sign "$SIGN_IDENTITY" "$f"
  done < <(find "$APP" -type f \( -name "*.dylib" -o -name "*.so" -o -perm -u+x \) -exec sh -c 'file "$1" | grep -q "Mach-O" && echo "$1"' _ {} \;)
  codesign --force --timestamp --options runtime --entitlements "$ROOT/packaging/entitlements.plist" --sign "$SIGN_IDENTITY" "$APP"
  codesign --verify --deep --strict --verbose=1 "$APP"
  SIGNED=1
else
  # Signature « ad hoc » (obligatoire pour qu'un binaire arm64 se lance ; ce n'est PAS une signature de développeur)
  codesign --force --deep --sign - "$APP"
  [ "${SIGN_IDENTITY:-}" = "-" ] && codesign --force --options runtime --entitlements "$ROOT/packaging/entitlements.plist" --sign - "$APP"   # essai du chemin « runtime renforcé » sans certificat
fi

# 3. Le DMG : l'application + un raccourci vers Applications
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="$OUT/ReAble-${VERSION}.dmg"
hdiutil create -volname "ReAble" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG" >/dev/null
rm -rf "$STAGE"
if [ "$SIGNED" = 1 ]; then
  codesign --force --timestamp --sign "$SIGN_IDENTITY" "$DMG"
  NOTARY_ARGS=()
  if [ -n "${NOTARY_PROFILE:-}" ]; then NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
  elif [ -n "${NOTARY_APPLE_ID:-}" ] && [ -n "${NOTARY_PASSWORD:-}" ] && [ -n "${NOTARY_TEAM_ID:-}" ]; then
    NOTARY_ARGS=(--apple-id "$NOTARY_APPLE_ID" --password "$NOTARY_PASSWORD" --team-id "$NOTARY_TEAM_ID"); fi
  if [ ${#NOTARY_ARGS[@]} -gt 0 ]; then
    echo "Notarisation en cours (quelques minutes)…"
    xcrun notarytool submit "$DMG" "${NOTARY_ARGS[@]}" --wait --output-format json > "$OUT/notarisation.json"
    cat "$OUT/notarisation.json"
    grep -q '"status" *: *"Accepted"' "$OUT/notarisation.json" || { echo "ERREUR : notarisation refusée (voir notarisation.json)"; exit 1; }
    xcrun stapler staple "$DMG"
    xcrun stapler validate "$DMG"
    spctl --assess --type open --context context:primary-signature -v "$DMG" 2>&1 || true
    echo "NOTARISÉ : $DMG"
  else
    echo "Signé mais NON notarisé (aucun identifiant de notarisation fourni)."
  fi
fi
echo "OK : $DMG ($(du -h "$DMG" | cut -f1))"
