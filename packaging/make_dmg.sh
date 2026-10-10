#!/bin/bash
# DMG avec fond d'image et icônes placées (flèche « glissez dans Applications »). Usage : make_dmg.sh ReAble.app sortie.dmg
# Repli : si la mise en forme par le Finder échoue (machine sans session graphique…), un DMG simple est créé.
set -uo pipefail
APP="$1"; DMG="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
VOL="ReAble"
STAGE="$(mktemp -d)"; RW="$(mktemp -u).dmg"
cleanup() { hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1 || true; rm -rf "$STAGE" "$RW"; }
trap cleanup EXIT

plain() { hdiutil create -volname "$VOL" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$DMG" >/dev/null; }

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
mkdir -p "$STAGE/.background"
if ! "$PY" "$HERE/make_dmg_background.py" "$STAGE/.background/background.png" 2>/dev/null; then
  echo "Fond du DMG non créé : DMG simple."; rm -rf "$STAGE/.background"; plain; exit 0
fi

hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1 || true
SIZE=$(( $(du -sm "$STAGE" | cut -f1) + 40 ))
hdiutil create -volname "$VOL" -srcfolder "$STAGE" -fs HFS+ -format UDRW -size "${SIZE}m" -ov "$RW" >/dev/null || { plain; exit 0; }
hdiutil attach "$RW" -readwrite -noverify -noautoopen -mountpoint "/Volumes/$VOL" >/dev/null || { plain; exit 0; }

osascript <<OSA &
tell application "Finder"
  tell disk "$VOL"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {200, 120, 860, 548}
    set opts to the icon view options of container window
    set arrangement of opts to not arranged
    set icon size of opts to 128
    set background picture of opts to file ".background:background.png"
    set position of item "ReAble.app" of container window to {165, 190}
    set position of item "Applications" of container window to {495, 190}
    update without registering applications
    delay 2
    close
  end tell
end tell
OSA
PID=$!
for _ in $(seq 1 90); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
if kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null; echo "Mise en forme du Finder trop longue : DMG simple."; hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1; plain; exit 0; fi
wait "$PID" || { echo "Mise en forme du Finder échouée : DMG simple."; hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1; plain; exit 0; }

sync; sleep 1
chmod -Rf go-w "/Volumes/$VOL" 2>/dev/null || true
# Éjection : le Finder garde parfois le volume occupé quelques secondes ; on réessaie, puis on force
for i in 1 2 3 4 5 6; do
  hdiutil detach "/Volumes/$VOL" >/dev/null 2>&1 && break
  sleep 3
  [ "$i" -ge 4 ] && hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1 && break
done
OK=0
for i in 1 2 3 4 5; do
  if hdiutil convert "$RW" -format UDZO -imagekey zlib-level=9 -ov -o "$DMG" >/dev/null 2>&1; then OK=1; break; fi
  sleep 4
done
if [ "$OK" != 1 ]; then echo "Conversion du DMG impossible : DMG simple."; hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1; plain; fi
[ -s "$DMG" ]
