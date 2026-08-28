#!/usr/bin/env bash
# Baut ein Windows-ZIP des aktuellen HEAD und legt es als GitHub-Release-Asset
# unter dem beweglichen Tag 'windows-latest' ab.
#
# NEU: Der Frontend-Build (frontend/dist) wird hier erzeugt und MIT ins ZIP
# gepackt. Dadurch braucht der Zielrechner KEIN Node.js/Git mehr – nur Python.
# install.ps1 erkennt den vorhandenen Build und überspringt npm ci/npm build.
#
# Nutzung (nach jeder Änderung, nachdem auf main gepusht wurde):
#   bash scripts/publish-windows-zip.sh
#
# Voraussetzung: gh (angemeldet), node/npm (für den Build) und Netz (Upload –
# im Umbrella-Firmennetz schlägt der Upload fehl).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TAG="windows-latest"
STAGE="$(mktemp -d)"
ZIP="$(mktemp -d)/mobilfunkverwaltung-windows.zip"
PREFIX="mobilfunkverwaltung"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Frontend-Build erzeugen (frontend/dist)"
if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend ci --no-fund --no-audit
fi
npm --prefix frontend run build
test -f frontend/dist/index.html || { echo "FEHLER: frontend/dist/index.html fehlt nach dem Build"; exit 1; }

echo "==> Quellstand aus HEAD auschecken ($(git rev-parse --short HEAD))"
git archive --format=tar --prefix="$PREFIX/" HEAD | tar -x -C "$STAGE"

echo "==> Fertigen Frontend-Build ins Paket legen"
mkdir -p "$STAGE/$PREFIX/frontend/dist"
cp -r frontend/dist/. "$STAGE/$PREFIX/frontend/dist/"

echo "==> ZIP schnüren"
python3 - "$STAGE" "$ZIP" "$PREFIX" <<'PY'
import os, sys, zipfile
stage, zip_path, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
root = os.path.join(stage, prefix)
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            full = os.path.join(dirpath, f)
            arc = os.path.relpath(full, stage)  # behält den prefix-Ordner
            z.write(full, arc)
print("   ", zip_path)
PY
echo "    Größe: $(du -h "$ZIP" | cut -f1)"

echo "==> Auf GitHub-Release '$TAG' ablegen"
if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "$ZIP" --clobber
else
  gh release create "$TAG" "$ZIP" \
    --title "Mobilfunkverwaltung – Windows-Paket (immer aktueller main)" \
    --notes "Enthält den fertigen Frontend-Build – auf dem Zielrechner ist **nur Python** nötig. Nach dem Entpacken **Mobilfunkverwaltung.cmd** doppelklicken (oder WINDOWS_INSTALL.md lesen). Wird nach jeder Änderung neu erzeugt."
fi

echo "==> Fertig. Download:"
gh release view "$TAG" --json assets -q '.assets[].url' 2>/dev/null || true
