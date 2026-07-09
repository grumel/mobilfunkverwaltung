# Server-Installation (Linux, Port 80)

Anleitung für einen kleinen Linux-Server (z. B. Lenovo ThinkPad mit Debian 12
oder Ubuntu Server) im eigenen Netz. Zwei getrennte Repos werden zusammengeführt:

- **Backend** (`mdwWeb`) – Flask, liefert die JSON-API. Läuft als **gunicorn**-Dienst.
- **Frontend** (`mdw-frontend`) – React, wird zu statischen Dateien **gebaut**
  (kein eigener Node-Prozess im Betrieb) und von **Caddy** ausgeliefert.

Caddy ist der einzige Dienst auf **Port 80**: `/api/*` reicht er an gunicorn
weiter, alles andere liefert er als statisches React-Bundle aus. Alles nur im
LAN erreichbar.

```
[Browser] --80--> [Caddy] ---> /api/*  --8000--> [gunicorn -> Flask-API] --> mobilfunk.db
                          \--> /*      --> statisches React-Bundle (mdw-frontend/dist)
```

> Hinweis: Man kann **kein** fertiges Windows-Verzeichnis auf den Linux-Server
> kopieren – `.venv/` (Backend) und `node_modules/` (Frontend) enthalten
> plattformgebundene Binaries. Stattdessen werden beide Repos direkt auf dem
> Server geklont und dort neu gebaut (der Installer erledigt das automatisch).

## Schnellweg: Automatischer Installer (empfohlen)

Auf einem frischen Debian/Ubuntu genügen drei Befehle:

```bash
sudo apt update && sudo apt install -y git
sudo git clone https://github.com/grumel/mdwWeb.git /opt/mobilfunk-web
sudo bash /opt/mobilfunk-web/deploy/install.sh            # optional: ... install.sh /pfad/zur/mobilfunk.db
```

`install.sh` erledigt **beide** Teile: Pakete, Benutzer `mobilfunk`,
`/var/lib/mobilfunk`, Backend-venv + Abhängigkeiten, zufälliges Secret,
systemd-Dienst (gunicorn) — **und** Node.js (falls nötig), klont
`mdw-frontend` nach `/opt/mobilfunk-frontend`, baut es (`npm install && npm run
build`) — sowie Caddy (Port 80) und Backup-Cron. Er ist **idempotent**
(mehrfach ausführbar; ruft er erneut auf, holt er beide Repos per `git pull`
und baut neu — das ist auch der **Update-Weg**).

Danach die Datenbank nach `/var/lib/mobilfunk/mobilfunk.db` bringen (falls
nicht als Argument übergeben) und `sudo systemctl restart mobilfunk-web`.

Aufruf danach: `http://<server-ip>/`

Optionen (Umgebungsvariablen vor dem Aufruf setzen):
- `SKIP_FRONTEND=1` — nur Backend/API einrichten, kein React-Build
- `FRONTEND_REPO=…` — abweichende Git-URL fürs Frontend
- `KEEP_SLEEP=1` — Ruhezustand nicht deaktivieren

> Die folgenden Abschnitte beschreiben dieselben Schritte **manuell** (falls du
> etwas anpassen willst oder der Installer nicht passt).

---

## 0. Voraussetzungen
- Debian 12 / Ubuntu Server frisch installiert, feste interne IP (z. B. 192.168.1.50)
- SSH-Zugang, sudo

## 1. Pakete
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git debian-keyring debian-archive-keyring apt-transport-https curl
# Caddy (offizielles Repo):
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
# Node.js 20 LTS (fuer den React-Build; Debian/Ubuntu-Standardpakete sind oft zu alt):
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

## 2. Benutzer und Ordner
```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin mobilfunk
sudo mkdir -p /opt/mobilfunk-web /var/lib/mobilfunk
```

## 3. Beide Repos auf den Server bringen
```bash
sudo git clone https://github.com/grumel/mdwWeb.git /opt/mobilfunk-web
sudo git clone https://github.com/grumel/mdw-frontend.git /opt/mobilfunk-frontend
sudo chown -R mobilfunk:mobilfunk /opt/mobilfunk-web /opt/mobilfunk-frontend
```

## 4. Backend: venv + Abhängigkeiten
```bash
cd /opt/mobilfunk-web
sudo -u mobilfunk python3 -m venv .venv
sudo -u mobilfunk .venv/bin/pip install --upgrade pip
sudo -u mobilfunk .venv/bin/pip install -r requirements.txt -r requirements-server.txt
```

## 5. Frontend bauen
```bash
cd /opt/mobilfunk-frontend
sudo -u mobilfunk npm install
sudo -u mobilfunk npm run build          # erzeugt dist/ (statische Dateien)
```

## 6. Datenbank kopieren (getrennt vom Programm)
Die vorhandene `mobilfunk.db` vom Windows-PC auf den Server nach
`/var/lib/mobilfunk/mobilfunk.db` übertragen (scp/USB), dann:
```bash
sudo chown -R mobilfunk:mobilfunk /var/lib/mobilfunk
```
> Der Pfad ist später in der App unter **⚙ Einstellungen** änderbar.

## 7. Secret erzeugen und Backend-Dienst einrichten
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"     # Ausgabe merken
sudo cp deploy/mobilfunk-web.service /etc/systemd/system/
sudoedit /etc/systemd/system/mobilfunk-web.service            # MOBILFUNK_SECRET eintragen
sudo systemctl daemon-reload
sudo systemctl enable --now mobilfunk-web
sudo systemctl status mobilfunk-web                           # sollte "active (running)" zeigen
```

## 8. Reverse-Proxy (Port 80, React + API)
```bash
sudo cp /opt/mobilfunk-web/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

## 9. Testen
Im Browser eines anderen Rechners im Netz: **http://192.168.1.50/**
→ React-Login-Seite. Anmelden wie in der Desktop-App.

## 10. Zugang für weitere Nutzer
Kein Netzlaufwerk nötig: in der App unter **Benutzerverwaltung** ein Konto
anlegen/aktivieren (Rolle Lesen/Schreiben/Admin) und dem Nutzer die URL geben.

## 11. Backups (empfohlen)
Tägliche Kopie der Datenbank:
```bash
sudo tee /etc/cron.daily/mobilfunk-backup >/dev/null <<'EOF'
#!/bin/sh
d=/var/lib/mobilfunk/backups; mkdir -p "$d"
cp /var/lib/mobilfunk/mobilfunk.db "$d/mobilfunk_$(date +%F).db"
ls -1t "$d"/mobilfunk_*.db | tail -n +15 | xargs -r rm    # 14 Tage behalten
EOF
sudo chmod +x /etc/cron.daily/mobilfunk-backup
```

---

## Updates einspielen
Am einfachsten: Installer erneut ausführen (idempotent, holt beide Repos per
`git pull` und baut das Frontend neu):
```bash
cd /opt/mobilfunk-web && sudo git pull && sudo bash deploy/install.sh
```
Manuell äquivalent:
```bash
cd /opt/mobilfunk-web && sudo -u mobilfunk git pull && sudo systemctl restart mobilfunk-web
cd /opt/mobilfunk-frontend && sudo -u mobilfunk git pull && sudo -u mobilfunk npm install && sudo -u mobilfunk npm run build
```

## Später erweitern / tunen
Alles ohne Änderung am App-Code – nur am Server-/Proxy-Layer:

- **HTTPS**: in `/etc/caddy/Caddyfile` `:80` durch einen DNS-Namen ersetzen
  (siehe Kommentar in der Datei) → Caddy verwaltet das Zertifikat automatisch.
- **Mehr Leistung**: gunicorn `--workers` erhöhen.
- **PostgreSQL**: `psycopg[binary]` installieren und in **⚙ Einstellungen** eine
  `DATABASE_URL` (postgresql+psycopg://…) hinterlegen, Daten migrieren.
- **Alte Jinja-Oberfläche**: bleibt im Backend vorhanden, ist über Port 80 aber
  nicht mehr eingebunden (React ist die Standard-UI). Direkt auf dem Server
  erreichbar unter `http://127.0.0.1:8000/`.

## Diagnose
```bash
sudo journalctl -u mobilfunk-web -e      # Backend/API-Logs
sudo journalctl -u caddy -e              # Proxy-Logs
```
