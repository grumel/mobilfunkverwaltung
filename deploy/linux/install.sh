#!/usr/bin/env bash
#
# Automatischer Installer – Mobilfunkverwaltung Web (Debian/Ubuntu, Port 80).
#
# Richtet Backend UND Frontend ein: Systempakete, Benutzer, venv + Abhaengigkeiten,
# Secret, systemd-Dienst (gunicorn), Node.js + React-Build (mdw-frontend),
# Reverse-Proxy Caddy (Port 80, React als UI + /api -> gunicorn), Backup-Cron
# und "Immer-an" (kein Ruhezustand, Deckel-zuklappen ignorieren) fuer Laptop-Server.
# Idempotent – kann gefahrlos mehrfach ausgefuehrt werden (auch fuer Updates:
# einfach erneut ausfuehren, holt beide Repos per 'git pull' und baut neu).
#
# Aufruf (aus dem geklonten Backend-Repo):
#     sudo bash deploy/linux/install.sh [/pfad/zur/mobilfunk.db]
#
# Umgebungsvariablen:
#     KEEP_SLEEP=1      Ruhezustand NICHT deaktivieren
#     SKIP_FRONTEND=1   React-Frontend NICHT einrichten (nur Backend/API)
#     FRONTEND_REPO=…   abweichende Git-URL des Frontend-Repos
#
set -euo pipefail

APP_USER=mobilfunk
DATA_DIR=/var/lib/mobilfunk
ENV_FILE="$DATA_DIR/mobilfunk.env"
APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)"   # Backend-Repo-Wurzel
FRONTEND_DIR=/opt/mobilfunk-frontend
FRONTEND_REPO="${FRONTEND_REPO:-https://github.com/grumel/mdw-frontend.git}"
DB_SRC="${1:-}"

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\n\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31m[X] %s\033[0m\n' "$*" >&2; exit 1; }

# Setzt einen Schluessel in /etc/systemd/logind.conf (ersetzt auch auskommentierte).
set_logind() {
  local key="$1" val="$2" f=/etc/systemd/logind.conf
  [ -f "$f" ] || return 0
  if grep -qE "^#?${key}=" "$f"; then
    sed -i -E "s|^#?${key}=.*|${key}=${val}|" "$f"
  else
    echo "${key}=${val}" >> "$f"
  fi
}

[ "$(id -u)" -eq 0 ] || die "Bitte mit root/sudo ausfuehren:  sudo bash deploy/linux/install.sh"
[ -f "$APP_DIR/requirements.txt" ] || die "requirements.txt nicht gefunden – Skript aus dem Backend-Repo heraus starten."

log "Backend-Verzeichnis: $APP_DIR"

# 0/11  Backend-Repo selbst aktualisieren (sonst haengt das Backend bei Updates
# zurueck – der Installer zog frueher nur das Frontend). Aendert sich dabei der
# Installer selbst, wird er einmalig mit dem neuen Stand neu gestartet.
if [ "${SKIP_SELF_UPDATE:-0}" != "1" ] && [ -d "$APP_DIR/.git" ]; then
  log "0/11  Backend aktualisieren (git pull)"
  git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
  before="$(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || echo none)"
  if git -C "$APP_DIR" pull --ff-only; then
    after="$(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || echo none)"
    if [ "$before" != "$after" ] && [ "${SELF_UPDATED:-0}" != "1" ]; then
      log "      Neue Version geladen – Installer wird mit neuem Stand neu gestartet"
      export SELF_UPDATED=1
      exec bash "$APP_DIR/deploy/linux/install.sh" "$@"
    fi
  else
    warn "Backend 'git pull' fehlgeschlagen – fahre mit vorhandenem Stand fort."
  fi
fi

log "1/11  Systempakete installieren"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl ca-certificates

if ! command -v caddy >/dev/null 2>&1; then
  log "      Caddy-Repository einrichten und installieren"
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

log "2/11  Benutzer '$APP_USER' und Datenverzeichnis '$DATA_DIR'"
id -u "$APP_USER" >/dev/null 2>&1 || \
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$DATA_DIR"

log "3/11  Virtuelle Umgebung + Abhaengigkeiten (Backend)"
[ -x "$APP_DIR/.venv/bin/python" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-server.txt"

log "4/11  Datenbank pruefen"
if [ -n "$DB_SRC" ] && [ -f "$DB_SRC" ] && [ ! -f "$DATA_DIR/mobilfunk.db" ]; then
  cp "$DB_SRC" "$DATA_DIR/mobilfunk.db"
  log "      kopiert: $DB_SRC -> $DATA_DIR/mobilfunk.db"
fi
DB_MISSING=0
[ -f "$DATA_DIR/mobilfunk.db" ] || DB_MISSING=1

log "5/11  Environment-Datei + Secret ($ENV_FILE)"
if [ ! -f "$ENV_FILE" ]; then
  SECRET="$("$APP_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"
  cat > "$ENV_FILE" <<EOF
MOBILFUNK_DATA_DIR=$DATA_DIR
MOBILFUNK_WEBCONFIG_DIR=$DATA_DIR
MOBILFUNK_SECRET=$SECRET
EOF
  chmod 600 "$ENV_FILE"
  log "      erzeugt (mit zufaelligem Secret)"
else
  log "      vorhanden – unveraendert (Secret bleibt stabil)"
fi

log "6/11  Dateirechte setzen (Backend)"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR" "$DATA_DIR"

log "7/11  systemd-Dienst 'mobilfunk-web' (gunicorn, Backend-API)"
cat > /etc/systemd/system/mobilfunk-web.service <<EOF
[Unit]
Description=Mobilfunkverwaltung Web (gunicorn)
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$APP_DIR/.venv/bin/gunicorn --chdir $APP_DIR --workers 2 --bind 127.0.0.1:8000 "webapp:create_app()"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now mobilfunk-web
systemctl restart mobilfunk-web

FRONTEND_BUILT=0
if [ "${SKIP_FRONTEND:-0}" = "1" ]; then
  log "8/11  React-Frontend uebersprungen (SKIP_FRONTEND=1)"
else
  log "8/11  Node.js + React-Frontend ($FRONTEND_REPO)"
  NODE_OK=0
  if command -v node >/dev/null 2>&1; then
    NODE_MAJOR="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
    [ "${NODE_MAJOR:-0}" -ge 18 ] && NODE_OK=1
  fi
  if [ "$NODE_OK" -eq 0 ]; then
    log "      Node.js 20 LTS installieren (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
    apt-get install -y nodejs
  fi

  if [ -d "$FRONTEND_DIR/.git" ]; then
    log "      Frontend aktualisieren (git pull)"
    git -C "$FRONTEND_DIR" pull --ff-only
  else
    log "      Frontend klonen"
    git clone "$FRONTEND_REPO" "$FRONTEND_DIR"
  fi

  log "      npm install + Produktions-Build"
  ( cd "$FRONTEND_DIR" && npm install --no-fund --no-audit && npm run build )
  chown -R "$APP_USER":"$APP_USER" "$FRONTEND_DIR"
  FRONTEND_BUILT=1
fi

log "9/11  Reverse-Proxy Caddy (Port 80)"
install -m 644 "$APP_DIR/deploy/linux/Caddyfile" /etc/caddy/Caddyfile
systemctl restart caddy

log "10/11  Backup-Cron"
cat > /etc/cron.daily/mobilfunk-backup <<'EOF'
#!/bin/sh
d=/var/lib/mobilfunk/backups; mkdir -p "$d"
[ -f /var/lib/mobilfunk/mobilfunk.db ] && cp /var/lib/mobilfunk/mobilfunk.db "$d/mobilfunk_$(date +%F).db"
ls -1t "$d"/mobilfunk_*.db 2>/dev/null | tail -n +15 | xargs -r rm
EOF
chmod +x /etc/cron.daily/mobilfunk-backup

log "11/11  Immer-an: Ruhezustand deaktivieren (Laptop als Server)"
if [ "${KEEP_SLEEP:-0}" = "1" ]; then
  log "       uebersprungen (KEEP_SLEEP=1)"
else
  systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true
  set_logind HandleLidSwitch ignore
  set_logind HandleLidSwitchDocked ignore
  set_logind HandleLidSwitchExternalPower ignore
  systemctl restart systemd-logind >/dev/null 2>&1 || true
  log "       System-Schlaf deaktiviert, Deckel-zuklappen wird ignoriert"
  warn "Ubuntu-Desktop zusaetzlich: Einstellungen > Energie > 'Automatisches Ausschalten' = Nie"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
printf '\n\033[1;32m==================== FERTIG ====================\033[0m\n'
echo "  Aufruf:   http://${IP:-<server-ip>}/"
echo "  Backend:  systemctl status mobilfunk-web   |  journalctl -u mobilfunk-web -e"
echo "  Proxy:    systemctl status caddy           |  journalctl -u caddy -e"
if systemctl is-active --quiet mobilfunk-web; then
  echo "  Status:   mobilfunk-web laeuft"
else
  warn "mobilfunk-web laeuft NICHT – bitte 'journalctl -u mobilfunk-web -e' pruefen."
fi
if [ "$FRONTEND_BUILT" -eq 1 ]; then
  if [ -f "$FRONTEND_DIR/dist/index.html" ]; then
    echo "  Frontend: gebaut ($FRONTEND_DIR/dist)"
  else
    warn "Frontend-Build unvollstaendig – $FRONTEND_DIR/dist/index.html fehlt."
  fi
fi
if [ "$DB_MISSING" -eq 1 ]; then
  warn "Keine Datenbank unter $DATA_DIR/mobilfunk.db!"
  echo "     Kopieren und Dienst neu starten, z. B.:"
  echo "       scp mobilfunk.db BENUTZER@$(hostname):$DATA_DIR/"
  echo "       sudo systemctl restart mobilfunk-web"
  echo "     (oder Installer erneut mit DB-Pfad: sudo bash deploy/linux/install.sh /pfad/zur/mobilfunk.db)"
fi
echo ""
echo "  Update spaeter (holt beide Repos automatisch + Neubau):"
echo "       sudo bash $APP_DIR/deploy/linux/install.sh"
