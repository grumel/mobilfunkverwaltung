#!/usr/bin/env bash
# Baut ein sauberes Quell-ZIP des aktuellen HEAD (ohne .git, ohne node_modules,
# .venv, dist – da diese per .gitignore nicht getrackt sind) und legt es als
# GitHub-Release-Asset unter dem beweglichen Tag 'windows-latest' ab.
#
# Nutzung (nach jeder Änderung, nachdem auf main gepusht wurde):
#   bash scripts/publish-windows-zip.sh
#
# Voraussetzung: gh (GitHub CLI) ist angemeldet und Netz erreichbar (offenes
# Internet – im Umbrella-Firmennetz schlägt der Upload fehl).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TAG="windows-latest"
ZIP="$(mktemp -d)/mobilfunkverwaltung-windows.zip"

echo "==> Quell-ZIP aus HEAD bauen ($(git rev-parse --short HEAD))"
git archive --format=zip --prefix=mobilfunkverwaltung/ -o "$ZIP" HEAD
echo "    $(du -h "$ZIP" | cut -f1) – $ZIP"

echo "==> Auf GitHub-Release '$TAG' ablegen"
if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "$ZIP" --clobber
else
  gh release create "$TAG" "$ZIP" \
    --title "Mobilfunkverwaltung – Windows-Paket (immer aktueller main)" \
    --notes "Quellcode + Windows-Installationsanleitung. Nach dem Entpacken: **WINDOWS_INSTALL.md** lesen. Wird nach jeder Änderung neu erzeugt."
fi

echo "==> Fertig. Download:"
gh release view "$TAG" --json assets -q '.assets[].url' 2>/dev/null || true
