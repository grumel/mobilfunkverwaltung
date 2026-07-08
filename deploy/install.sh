#!/usr/bin/env bash
#
# Automatischer Installer – Mobilfunkverwaltung Web (Debian/Ubuntu, Port 80).
#
# Richtet alles ein: Systempakete, Benutzer, venv + Abhaengigkeiten, Secret,
# systemd-Dienst (gunicorn), Reverse-Proxy Caddy (Port 80), Backup-Cron und
# "Immer-an" (kein Ruhezustand, Deckel-zuklappen ignorieren) fuer Laptop-Server.
# Idempotent – kann gefahrlos mehrfach ausgefuehrt werden.
#
# Aufruf (aus dem geklonten Repo):
#     sudo bash deploy/install.sh [/pfad/zur/mobilfunk.db]
#
# Umgebungsvariablen:
#     KEEP_SLEEP=1   Ruhezustand NICHT deaktivieren (Schritt 9 ueberspringen)
#
set -euo pipefail

APP_USER=mobilfunk
DATA_DIR=/var/lib/mobilfunk
ENV_FILE="$DATA_DIR/mobilfunk.env"
APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"   # Repo-Wurzel
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

[ "$(id -u)" -eq 0 ] || die "Bitte mit root/sudo ausfuehren:  sudo bash deploy/install.sh"
[ -f "$APP_DIR/requirements.txt" ] || die "requirements.txt nicht gefunden – Skript aus dem Repo heraus starten."

log "Programmverzeichnis: $APP_DIR"

log "1/9  Systempakete installieren"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip curl ca-certificates

if ! command -v caddy >/dev/null 2>&1; then
  log "     Caddy-Repository einrichten und installieren"
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https gnupg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

log "2/9  Benutzer '$APP_USER' und Datenverzeichnis '$DATA_DIR'"
id -u "$APP_USER" >/dev/null 2>&1 || \
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$DATA_DIR"

log "3/9  Virtuelle Umgebung + Abhaengigkeiten"
[ -x "$APP_DIR/.venv/bin/python" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-server.txt"

log "4/9  Datenbank pruefen"
if [ -n "$DB_SRC" ] && [ -f "$DB_SRC" ] && [ ! -f "$DATA_DIR/mobilfunk.db" ]; then
  cp "$DB_SRC" "$DATA_DIR/mobilfunk.db"
  log "     kopiert: $DB_SRC -> $DATA_DIR/mobilfunk.db"
fi
DB_MISSING=0
[ -f "$DATA_DIR/mobilfunk.db" ] || DB_MISSING=1

log "5/9  Environment-Datei + Secret ($ENV_FILE)"
if [ ! -f "$ENV_FILE" ]; then
  SECRET="$("$APP_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))')"
  cat > "$ENV_FILE" <<EOF
MOBILFUNK_DATA_DIR=$DATA_DIR
MOBILFUNK_WEBCONFIG_DIR=$DATA_DIR
MOBILFUNK_SECRET=$SECRET
EOF
  chmod 600 "$ENV_FILE"
  log "     erzeugt (mit zufaelligem Secret)"
else
  log "     vorhanden – unveraendert (Secret bleibt stabil)"
fi

log "6/9  Dateirechte setzen"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR" "$DATA_DIR"

log "7/9  systemd-Dienst 'mobilfunk-web'"
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

log "8/9  Reverse-Proxy Caddy (Port 80) + Backup-Cron"
install -m 644 "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl restart caddy

cat > /etc/cron.daily/mobilfunk-backup <<'EOF'
#!/bin/sh
d=/var/lib/mobilfunk/backups; mkdir -p "$d"
[ -f /var/lib/mobilfunk/mobilfunk.db ] && cp /var/lib/mobilfunk/mobilfunk.db "$d/mobilfunk_$(date +%F).db"
ls -1t "$d"/mobilfunk_*.db 2>/dev/null | tail -n +15 | xargs -r rm
EOF
chmod +x /etc/cron.daily/mobilfunk-backup

log "9/9  Immer-an: Ruhezustand deaktivieren (Laptop als Server)"
if [ "${KEEP_SLEEP:-0}" = "1" ]; then
  log "     uebersprungen (KEEP_SLEEP=1)"
else
  systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true
  set_logind HandleLidSwitch ignore
  set_logind HandleLidSwitchDocked ignore
  set_logind HandleLidSwitchExternalPower ignore
  systemctl restart systemd-logind >/dev/null 2>&1 || true
  log "     System-Schlaf deaktiviert, Deckel-zuklappen wird ignoriert"
  warn "Ubuntu-Desktop zusaetzlich: Einstellungen > Energie > 'Automatisches Ausschalten' = Nie"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
printf '\n\033[1;32m==================== FERTIG ====================\033[0m\n'
echo "  Aufruf:   http://${IP:-<server-ip>}/"
echo "  Dienst:   systemctl status mobilfunk-web"
echo "  Logs:     journalctl -u mobilfunk-web -e"
if systemctl is-active --quiet mobilfunk-web; then
  echo "  Status:   mobilfunk-web laeuft"
else
  warn "mobilfunk-web laeuft NICHT – bitte 'journalctl -u mobilfunk-web -e' pruefen."
fi
if [ "$DB_MISSING" -eq 1 ]; then
  warn "Keine Datenbank unter $DATA_DIR/mobilfunk.db!"
  echo "     Kopieren und Dienst neu starten, z. B.:"
  echo "       scp mobilfunk.db BENUTZER@$(hostname):$DATA_DIR/"
  echo "       sudo systemctl restart mobilfunk-web"
  echo "     (oder Installer erneut mit DB-Pfad: sudo bash deploy/install.sh /pfad/zur/mobilfunk.db)"
fi
