#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-mobilfunk-web}"
CADDY_SERVICE_NAME="${CADDY_SERVICE_NAME:-caddy}"
CADDY_BACKUP="${CADDY_BACKUP:-/etc/caddy/Caddyfile.pre-monorepo}"
SERVICE_BACKUP="${SERVICE_BACKUP:-/etc/systemd/system/mobilfunk-web.service.pre-monorepo}"
APP_LINK="${APP_LINK:-/opt/mobilfunkverwaltung}"
PREVIOUS_APP_DIR="${PREVIOUS_APP_DIR:-}"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

[ "$(id -u)" -eq 0 ] || fail "Rollback muss als root ausgeführt werden."
[ -f "$CADDY_BACKUP" ] || fail "Caddy-Backup fehlt: $CADDY_BACKUP"
[ -f "$SERVICE_BACKUP" ] || fail "systemd-Backup fehlt: $SERVICE_BACKUP"

if [ -n "$PREVIOUS_APP_DIR" ]; then
  [ -d "$PREVIOUS_APP_DIR" ] || fail "Vorheriges Anwendungsverzeichnis fehlt: $PREVIOUS_APP_DIR"
  [ -L "$APP_LINK" ] || fail "$APP_LINK ist kein Symlink; automatisches Umschalten wird verweigert."
fi

printf '[INFO] Stoppe %s und %s.\n' "$CADDY_SERVICE_NAME" "$SERVICE_NAME"
systemctl stop "$CADDY_SERVICE_NAME" "$SERVICE_NAME"

install -m 644 "$CADDY_BACKUP" /etc/caddy/Caddyfile
install -m 644 "$SERVICE_BACKUP" "/etc/systemd/system/${SERVICE_NAME}.service"

if [ -n "$PREVIOUS_APP_DIR" ]; then
  ln -sfn "$PREVIOUS_APP_DIR" "$APP_LINK"
  printf '[INFO] Anwendungssymlink zeigt wieder auf %s.\n' "$PREVIOUS_APP_DIR"
fi

systemctl daemon-reload
systemctl start "$SERVICE_NAME" "$CADDY_SERVICE_NAME"

printf '[PASS] Konfiguration zurückgerollt. Datenbank und Datenverzeichnisse wurden nicht verändert.\n'
