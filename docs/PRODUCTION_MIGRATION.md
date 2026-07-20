# Rückrollbare Linux-Produktionsmigration

Diese Anleitung stellt eine bestehende Installation aus den getrennten
Checkouts auf das Monorepository unter `/opt/mobilfunkverwaltung` um. Sie führt
keine Schemaänderung durch. Produktive Daten bleiben unter
`/var/lib/mobilfunk`; die bisherigen Anwendungsverzeichnisse werden bis zur
Abnahme nicht gelöscht.

## Zielbild

```text
/opt/mobilfunkverwaltung/
├── backend/                 Flask und backend/.venv
├── frontend/                React-Quellen und frontend/dist
└── deploy/linux/            Caddy- und systemd-Referenzdateien

/var/lib/mobilfunk/
├── mobilfunk.db             produktive SQLite-Datenbank
├── mobilfunk.env            Secret und Laufzeitpfade, root:root 0600
├── Dokumente/               Vorlagen und erzeugte Dokumente
├── logs/
└── backups/
```

Die Anwendung läuft weiterhin als Benutzer `mobilfunk`. Caddy lauscht auf Port
80 und leitet `/api/*` an Gunicorn auf `127.0.0.1:8000` weiter.

## 1. Vorprüfung

Alle Befehle auf dem Produktionsserver ausführen. Zunächst Ist-Zustand und
ausgelieferte Pfade protokollieren:

```bash
sudo systemctl status mobilfunk-web caddy --no-pager
sudo systemctl cat mobilfunk-web
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo readlink -f /proc/$(pgrep -o -f 'gunicorn.*webapp')/cwd
curl -fsS http://127.0.0.1:8000/api/version
curl -fsS http://127.0.0.1/ >/dev/null
```

Vorher sicher feststellen, wo `mobilfunk.db`, die aktuelle Environment-Datei,
Dokumente und Upload-/Importdaten liegen. Nichts verschieben, solange diese
Pfade nicht eindeutig sind.

## 2. Backups anlegen

Ein unveränderliches Migrationsverzeichnis erzeugen:

```bash
stamp=$(date +%Y%m%d-%H%M%S)
backup=/var/backups/mobilfunk-migration/$stamp
sudo install -d -m 700 "$backup"
sudo cp -a /etc/caddy/Caddyfile "$backup/Caddyfile"
sudo cp -a /etc/systemd/system/mobilfunk-web.service "$backup/mobilfunk-web.service"
sudo cp -a /etc/caddy/Caddyfile /etc/caddy/Caddyfile.pre-monorepo
sudo cp -a /etc/systemd/system/mobilfunk-web.service \
  /etc/systemd/system/mobilfunk-web.service.pre-monorepo
```

SQLite online konsistent sichern, sofern die Datenbank bereits unter dem
Standardpfad liegt:

```bash
sudo sqlite3 /var/lib/mobilfunk/mobilfunk.db \
  ".backup '$backup/mobilfunk.db'"
sudo sqlite3 "$backup/mobilfunk.db" 'PRAGMA integrity_check;'
```

Die Ausgabe muss `ok` sein. Wenn `sqlite3` nicht installiert ist, den
Backenddienst kurz stoppen, die DB einschließlich vorhandener `-wal`/`-shm`
Dateien gemeinsam kopieren und den Dienst wieder starten.

Bestehende Anwendung und Daten zusätzlich archivieren, ohne sie zu löschen:

```bash
sudo tar --exclude='.venv' --exclude='node_modules' --exclude='dist' \
  -C /opt -czf "$backup/legacy-applications.tar.gz" \
  mobilfunk-web mobilfunk-frontend
sudo tar -C /var/lib -czf "$backup/mobilfunk-data.tar.gz" mobilfunk
sudo chmod 600 "$backup"/*
```

Nicht vorhandene alte Verzeichnisse aus dem `tar`-Befehl entfernen. Das Backup
außerhalb des Servers zusätzlich sichern.

## 3. Monorepository klonen und bauen

Bis zum Merge wird der veröffentlichte Migrationsbranch verwendet. Nach dem
Merge kann `--branch main` eingesetzt werden.

```bash
sudo git clone --branch chore/monorepo-migration --single-branch \
  https://github.com/grumel/mobilfunkverwaltung.git \
  /opt/mobilfunkverwaltung
sudo chown -R mobilfunk:mobilfunk /opt/mobilfunkverwaltung

sudo -u mobilfunk python3 -m venv /opt/mobilfunkverwaltung/backend/.venv
sudo -u mobilfunk /opt/mobilfunkverwaltung/backend/.venv/bin/pip install --upgrade pip
sudo -u mobilfunk /opt/mobilfunkverwaltung/backend/.venv/bin/pip install \
  -r /opt/mobilfunkverwaltung/backend/requirements.txt \
  -r /opt/mobilfunkverwaltung/backend/requirements-server.txt

cd /opt/mobilfunkverwaltung/frontend
sudo -u mobilfunk npm ci
sudo -u mobilfunk npm run build
test -f /opt/mobilfunkverwaltung/frontend/dist/index.html
```

Falls `/opt/mobilfunkverwaltung` bereits von einem fehlgeschlagenen Versuch
existiert, nicht überschreiben oder löschen, sondern mit Zeitstempel umbenennen
und die Ursache zuvor dokumentieren.

## 4. Persistente Laufzeitdaten vorbereiten

```bash
sudo install -d -o mobilfunk -g mobilfunk -m 750 \
  /var/lib/mobilfunk /var/lib/mobilfunk/logs /var/lib/mobilfunk/backups
```

Eine vorhandene Environment-Datei und insbesondere `MOBILFUNK_SECRET`
übernehmen. Ein neues Secret würde alle bestehenden Sessions ungültig machen.

```bash
sudo install -o root -g root -m 600 /PFAD/ZUR/BISHERIGEN/mobilfunk.env \
  /var/lib/mobilfunk/mobilfunk.env
sudoedit /var/lib/mobilfunk/mobilfunk.env
```

Sie muss mindestens enthalten:

```text
MOBILFUNK_DATA_DIR=/var/lib/mobilfunk
MOBILFUNK_WEBCONFIG_DIR=/var/lib/mobilfunk
MOBILFUNK_SECRET=<bestehender-geheimer-wert>
```

Die Datei niemals in Git aufnehmen oder ihren Inhalt in Logs ausgeben.

Liegt die bisherige Datenbank oder ein Datenverzeichnis noch an einem anderen
Ort, die Anwendung vor dem Kopieren stoppen und Quelle sowie Ziel einzeln
prüfen. `mobilfunk.db`, `Dokumente/`, Logs, Einstellungen und Importdaten
gehören unter `/var/lib/mobilfunk`. Keine vorhandene Zieldatei ungeprüft
überschreiben.

```bash
sudo systemctl stop mobilfunk-web
# Beispiel erst nach manueller Pfadprüfung:
# sudo rsync -a --ignore-existing /ALTER/DATENPFAD/ /var/lib/mobilfunk/
sudo chown -R mobilfunk:mobilfunk /var/lib/mobilfunk
sudo chown root:root /var/lib/mobilfunk/mobilfunk.env
sudo chmod 600 /var/lib/mobilfunk/mobilfunk.env
```

Den konfigurierten Datenbankpfad kontrollieren:

```bash
sudo bash -c 'set -a
. /var/lib/mobilfunk/mobilfunk.env
set +a
cd /opt/mobilfunkverwaltung/backend
exec .venv/bin/python -c "from webapp.config import DATABASE_URL; print(DATABASE_URL)"'
```

Nur den resultierenden Datenbankpfad protokollieren; die Environment-Datei und
das Secret dürfen nicht in Terminalausgaben oder Tickets kopiert werden.

## 5. systemd und Caddy umstellen

Die Referenzdateien verwenden bereits die Monorepo-Pfade:

- `WorkingDirectory=/opt/mobilfunkverwaltung/backend`
- Gunicorn unter `/opt/mobilfunkverwaltung/backend/.venv/bin/gunicorn`
- Caddy-Root `/opt/mobilfunkverwaltung/frontend/dist`

```bash
sudo install -m 644 /opt/mobilfunkverwaltung/deploy/linux/mobilfunk-web.service \
  /etc/systemd/system/mobilfunk-web.service
sudo install -m 644 /opt/mobilfunkverwaltung/deploy/linux/Caddyfile \
  /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl daemon-reload
sudo systemctl enable mobilfunk-web caddy
sudo systemctl restart mobilfunk-web
sudo systemctl restart caddy
```

## 6. Smoke-Tests und Abnahme

```bash
sudo systemctl is-active --quiet mobilfunk-web
sudo systemctl is-active --quiet caddy
cd /opt/mobilfunkverwaltung
./scripts/smoke-test-linux.sh
```

Optional einen dedizierten Testbenutzer verwenden, ohne Zugangsdaten in die
Shell-Historie oder das Repository zu schreiben:

```bash
read -r -p 'Smoke-Benutzer: ' SMOKE_USERNAME
read -r -s -p 'Smoke-Passwort: ' SMOKE_PASSWORD; echo
export SMOKE_USERNAME SMOKE_PASSWORD
./scripts/smoke-test-linux.sh
unset SMOKE_USERNAME SMOKE_PASSWORD
```

Danach im Browser Login, Teilnehmerliste, Bearbeiten, Importvorschau,
Dokumentliste, Aufgaben und Statistik prüfen. Datenbankanzahl und relevante
Dokumente mit dem Stand vor der Migration vergleichen.

## 7. Rollback

Bei Fehlern zuerst Logs sichern:

```bash
sudo journalctl -u mobilfunk-web -u caddy --since '-15 minutes' \
  > /tmp/mobilfunk-migration-failure.log
```

Die vorbereiteten Konfigurationsbackups können ohne Datenbankänderung
zurückgespielt werden:

```bash
cd /opt/mobilfunkverwaltung
sudo ./scripts/rollback-linux.sh
```

Das Skript stoppt Dienste, stellt nur Caddy- und systemd-Konfiguration wieder
her und startet die Dienste. Es löscht oder überschreibt keine Datenbank. Wenn
`/opt/mobilfunkverwaltung` bewusst als Symlink betrieben wird, kann zusätzlich
atomar auf ein früheres Release umgeschaltet werden:

```bash
sudo PREVIOUS_APP_DIR=/opt/mobilfunkverwaltung-releases/<vorheriges-release> \
  APP_LINK=/opt/mobilfunkverwaltung ./scripts/rollback-linux.sh
```

Bei einem normalen Verzeichnis verweigert das Skript diese Umschaltung. Die
alten Checkouts und Backups erst nach mehrtägiger erfolgreicher Abnahme separat
und bewusst archivieren; diese Anleitung löscht sie nicht.
