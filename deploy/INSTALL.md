# Server-Installation (Linux, Port 80)

Anleitung für einen kleinen Linux-Server (z. B. Lenovo ThinkPad mit Debian 12
oder Ubuntu Server) im eigenen Netz. Die App läuft über **Port 80** hinter dem
Reverse-Proxy **Caddy**; darunter **gunicorn**. Alles nur im LAN erreichbar.

```
[Browser] --80--> [Caddy] --8000--> [gunicorn -> webapp] --> mobilfunk.db
```

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
```

## 2. Benutzer und Ordner
```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin mobilfunk
sudo mkdir -p /opt/mobilfunk-web /var/lib/mobilfunk
```

## 3. Programm auf den Server bringen
Repo nach `/opt/mobilfunk-web` kopieren (per git oder scp). Beispiel git:
```bash
sudo git clone <REPO-URL> /opt/mobilfunk-web        # oder Dateien hierher kopieren
sudo chown -R mobilfunk:mobilfunk /opt/mobilfunk-web
```

## 4. Virtuelle Umgebung + Abhängigkeiten
```bash
cd /opt/mobilfunk-web
sudo -u mobilfunk python3 -m venv .venv
sudo -u mobilfunk .venv/bin/pip install --upgrade pip
sudo -u mobilfunk .venv/bin/pip install -r requirements.txt -r requirements-server.txt
```

## 5. Datenbank kopieren (getrennt vom Programm)
Die vorhandene `mobilfunk.db` vom Windows-PC auf den Server nach
`/var/lib/mobilfunk/mobilfunk.db` übertragen (scp/USB), dann:
```bash
sudo chown -R mobilfunk:mobilfunk /var/lib/mobilfunk
```
> Der Pfad ist später in der App unter **⚙ Einstellungen** änderbar.

## 6. Secret erzeugen und Dienst einrichten
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"     # Ausgabe merken
sudo cp deploy/mobilfunk-web.service /etc/systemd/system/
sudoedit /etc/systemd/system/mobilfunk-web.service            # MOBILFUNK_SECRET eintragen
sudo systemctl daemon-reload
sudo systemctl enable --now mobilfunk-web
sudo systemctl status mobilfunk-web                           # sollte "active (running)" zeigen
```

## 7. Reverse-Proxy (Port 80)
```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

## 8. Testen
Im Browser eines anderen Rechners im Netz: **http://192.168.1.50/**
→ Login-Seite. Anmelden wie in der Desktop-App.

## 9. Zugang für weitere Nutzer
Kein Netzlaufwerk nötig: in der App unter **Benutzerverwaltung** ein Konto
anlegen/aktivieren (Rolle Lesen/Schreiben/Admin) und dem Nutzer die URL geben.

## 10. Backups (empfohlen)
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

## Später erweitern / tunen
Alles ohne Änderung am App-Code – nur am Server-/Proxy-Layer:

- **HTTPS**: in `/etc/caddy/Caddyfile` `:80` durch einen DNS-Namen ersetzen
  (siehe Kommentar in der Datei) → Caddy verwaltet das Zertifikat automatisch.
- **Mehr Leistung**: gunicorn `--workers` erhöhen.
- **PostgreSQL**: `psycopg[binary]` installieren und in **⚙ Einstellungen** eine
  `DATABASE_URL` (postgresql+psycopg://…) hinterlegen, Daten migrieren.
- **Updates einspielen**: `git pull` in `/opt/mobilfunk-web`, dann
  `sudo systemctl restart mobilfunk-web`.

## Diagnose
```bash
sudo journalctl -u mobilfunk-web -e      # App-Logs
sudo journalctl -u caddy -e              # Proxy-Logs
```
