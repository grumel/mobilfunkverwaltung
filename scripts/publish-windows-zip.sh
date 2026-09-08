#!/usr/bin/env bash
# Baut ein Windows-ZIP des aktuellen HEAD und legt es als GitHub-Release-Asset
# unter dem beweglichen Tag 'windows-latest' ab.
#
# Der Frontend-Build (frontend/dist) UND ein vorinstalliertes Python-Bundle
# (backend/python-embed: Python-Embeddable + alle Abhaengigkeiten aus
# requirements.txt/requirements-server.txt) werden hier erzeugt und MIT ins
# ZIP gepackt. Dadurch braucht der Zielrechner WEDER Node.js/Git NOCH Python
# NOCH Internetzugang fuer pip – nur das ZIP entpacken und
# Mobilfunkverwaltung.cmd doppelklicken. install.ps1 erkennt beides und
# ueberspringt npm ci/npm build bzw. venv/pip-install entsprechend.
#
# Nutzung (nach jeder Änderung, nachdem auf main gepusht wurde):
#   bash scripts/publish-windows-zip.sh
#
# Voraussetzung: gh (angemeldet), node/npm (für den Frontend-Build), lokales
# Python 3.12.x (fuer das Bundle - siehe Windows-Host-Pruefung unten), curl
# und Netz (Upload – im Umbrella-Firmennetz schlägt der Upload fehl).
#
# WICHTIG: muss auf einem echten Windows-Host laufen (z. B. Git Bash unter
# Windows), NICHT unter WSL/Linux/macOS. Grund: requirements.txt/
# requirements-server.txt enthalten "platform_system"-Marker (pywin32 nur
# Windows, waitress statt gunicorn nur Windows); pip wertet diese Marker
# beim Cross-Bau NICHT fuer die Zielplattform aus, sondern fuer den
# aktuell laufenden Host - auf einem falschen Host wuerde das Bundle sonst
# unbemerkt die falschen Pakete enthalten.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TAG="windows-latest"
STAGE="$(mktemp -d)"
ZIP="$(mktemp -d)/mobilfunkverwaltung-windows.zip"
PREFIX="mobilfunkverwaltung"
PYTHON_BIN="${PYTHON_BIN:-python}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || PYTHON_BIN="python3"
trap 'rm -rf "$STAGE"' EXIT

echo "==> Host pruefen (Python-Bundle braucht einen echten Windows-Host)"
HOST_OS="$("$PYTHON_BIN" -c 'import platform; print(platform.system())')"
if [ "$HOST_OS" != "Windows" ]; then
  echo "FEHLER: dieses Skript muss auf einem Windows-Host laufen (erkannt: $HOST_OS)." >&2
  echo "Grund: platform_system-Marker in requirements*.txt wuerden sonst falsch aufgeloest" >&2
  echo "(z. B. gunicorn statt waitress, pywin32 fehlt) - siehe Kommentar am Skriptanfang." >&2
  exit 1
fi
PY_VERSION="$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')"
case "$PY_VERSION" in
  3.12.*) ;;
  *)
    echo "FEHLER: lokales Python ist $PY_VERSION, fuer das Bundle wird 3.12.x benoetigt" >&2
    echo "(ABI-Kompatibilitaet zum eingebetteten Python 3.12)." >&2
    exit 1
    ;;
esac

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

echo "==> Windows-only Anforderungsliste ableiten (Marker aufloesen, siehe Host-Pruefung oben)"
WIN_REQUIREMENTS="$(mktemp)"
"$PYTHON_BIN" - "$WIN_REQUIREMENTS" <<'PY'
import sys

out = []
for path in ("backend/requirements.txt", "backend/requirements-server.txt"):
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ";" in line:
                pkg, marker = (part.strip() for part in line.split(";", 1))
                if marker == 'platform_system == "Windows"':
                    out.append(pkg)
                elif marker == 'platform_system != "Windows"':
                    continue  # nur fuer Linux (z. B. gunicorn) - im Windows-Bundle nicht noetig
                else:
                    sys.exit(f"Unbekannter Marker in {path}, Skript pruefen: {line}")
            else:
                out.append(line)

with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
PY

echo "==> Python-Embeddable herunterladen (Version $PY_VERSION, passend zum lokalen Python)"
EMBED_DIR="$STAGE/$PREFIX/backend/python-embed"
EMBED_ZIP="$(mktemp -d)/python-embed.zip"
EMBED_URL="https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-embed-amd64.zip"
curl -fsSL -o "$EMBED_ZIP" "$EMBED_URL"
mkdir -p "$EMBED_DIR"
"$PYTHON_BIN" - "$EMBED_ZIP" "$EMBED_DIR" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
    z.extractall(sys.argv[2])
PY

echo "==> site-packages im eingebetteten Python aktivieren"
# Embeddable Python deaktiviert "import site" per Default und kennt
# Lib\site-packages nicht - beides fuer unsere Abhaengigkeiten noetig.
# Wichtig: Eintraege in der ._pth-Datei sind relativ zum Ordner der Datei
# selbst (python-embed\), NICHT zum Arbeitsverzeichnis des Aufrufers. "."
# zeigt also auf python-embed\ - deshalb zusaetzlich ".." (= backend\)
# eintragen, sonst findet Python wsgi.py/platform_support/webapp/modules
# beim Start nicht (per echtem Waitress-Start verifiziert).
PTH_FILE="$(ls "$EMBED_DIR"/python3*._pth)"
{
  head -n 2 "$PTH_FILE"
  echo '..'
  echo 'Lib\site-packages'
  echo 'import site'
} > "$PTH_FILE.new"
mv "$PTH_FILE.new" "$PTH_FILE"

echo "==> Abhaengigkeiten in das Bundle installieren (kein venv - direkt als site-packages)"
"$PYTHON_BIN" -m pip install --no-cache-dir --upgrade \
  --target "$EMBED_DIR/Lib/site-packages" -r "$WIN_REQUIREMENTS"
echo "    Bundle-Groesse: $(du -sh "$EMBED_DIR" | cut -f1)"

echo "==> ZIP schnüren"
"$PYTHON_BIN" - "$STAGE" "$ZIP" "$PREFIX" <<'PY'
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
    --notes "Enthält den fertigen Frontend-Build und ein vorinstalliertes Python-Bundle – auf dem Zielrechner ist nichts vorauszusetzen. Nach dem Entpacken **Mobilfunkverwaltung.cmd** doppelklicken (oder WINDOWS_INSTALL.md lesen). Wird nach jeder Änderung neu erzeugt."
fi

echo "==> Fertig. Download:"
gh release view "$TAG" --json assets -q '.assets[].url' 2>/dev/null || true
