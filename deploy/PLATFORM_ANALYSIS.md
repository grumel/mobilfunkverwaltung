# Plattformanalyse

Stand dieser Analyse ist die gemeinsame Codebasis vor Einführung der zentralen
Plattformsschicht. Die genannten Duplikate und Altdateien werden bewusst nicht
gelöscht, weil diese Änderung ausschließlich die Architektur vorbereitet.

## Linux-spezifische Abhängigkeiten

| Bereich | Fundstelle | Bindung |
| --- | --- | --- |
| WSGI-Server | `requirements-server.txt`, `deploy/linux/mobilfunk-web.service`, `deploy/linux/install.sh` | `gunicorn` |
| Dienstverwaltung | `deploy/linux/install.sh`, `deploy/linux/INSTALL.md`, `deploy/linux/POSTGRES.md` | `systemctl`, systemd-Units und `/etc/systemd` |
| Installer | `deploy/linux/install.sh` | Bash, `apt-get`, `curl`, `grep`, `sed`, `awk`, `hostname`, `git`, `npm` |
| Rechte | `deploy/linux/install.sh`, `deploy/linux/INSTALL.md` | `chmod`, `chown`, Unix-Benutzer und Gruppen |
| Reverse-Proxy | `deploy/linux/Caddyfile`, Installer und Installationsanleitung | `/etc/caddy`, Caddy-Dienst |
| Dateisystem | Linux-Deploymentdateien | `/opt/mobilfunkverwaltung/backend`, `/opt/mobilfunkverwaltung/frontend`, `/var/lib/mobilfunk`, `/etc/cron.daily` |
| Datensicherung | `deploy/linux/install.sh`, `deploy/linux/INSTALL.md` | Cron und POSIX-Shell-Kommandos |
| Laptop-Betrieb | `deploy/linux/install.sh` | systemd-Sleep-Targets und `/etc/systemd/logind.conf` |
| PDF-Erzeugung | `modules/kuendigung.py` | `subprocess.run()` mit LibreOffice/`soffice`, temporäres `HOME` |
| PostgreSQL-Werkzeuge | `deploy/linux/POSTGRES.md` | `sudo`, `psql`, `pg_dump`, gzip |

Diese Bindungen bleiben unter `deploy/linux` beziehungsweise im bereits
vorhandenen Linux-PDF-Adapter. Sie werden nicht in gemeinsam ausgeführte
Windows-Deploymentpfade übernommen.

## Windows-spezifische Abhängigkeiten

| Bereich | Fundstelle | Bindung |
| --- | --- | --- |
| Lokaler Starter | `run_webapp.bat` | Batch, `.venv\\Scripts\\python.exe`, aktuell hart gesetzter Benutzerpfad |
| Konfigurationsort | `webapp/webconfig.py` | `%LOCALAPPDATA%` |
| PDF und E-Mail | `modules/kuendigung.py` | `win32com`, Microsoft Word und Outlook |
| Desktop-Neustart | `modules/ui_main.py` | `subprocess.Popen([sys.executable, ...])`, grundsätzlich plattformneutral, aber Desktop-Kontext |

## Plattformneutrale Prozess- und Temp-Verwendung

- `webapp/blueprints/api.py` ruft `git` per `subprocess.check_output()` auf, um
  eine optionale Buildnummer zu ermitteln. Ohne Git wird bereits kontrolliert
  auf leere Versionsdaten zurückgefallen.
- `webapp/blueprints/api.py` und `webapp/blueprints/imports.py` erzeugen Uploads
  mit `tempfile.mkstemp()` und löschen sie anschließend.
- `modules/kuendigung.py` nutzt `tempfile.TemporaryDirectory()` für ein isoliertes
  LibreOffice-Profil.
- Es wurden keine Aufrufe von `os.system()` und keine Verwendung von
  `shell=True` gefunden.

## Verteilte Konfiguration

- Datenwurzel und Ressourcenwurzel: `modules/paths.py`
- Datenbank-URL und Standard-Datenbankpfad: `webapp/config.py`
- persistente Web-Konfiguration und Session-Secret: `webapp/webconfig.py`
- Logverzeichnis: `modules/orchestrator.py` (`DATA_DIR / "logs"`)
- Dokumentvorlagen und Exporte: `modules/kuendigung.py`
- Syno-Exporte: `webapp/blueprints/api.py`
- temporäre Uploads: Betriebssystem-Standard aus `tempfile`
- Linux-Betriebspfade: systemd-Unit und `deploy/linux/install.sh`
- Windows-Entwicklungspfad: `run_webapp.bat`

Die neue Plattformsschicht zentralisiert ausschließlich stabile Basispfade und
Betriebssystemerkennung. Fachliche Unterverzeichnisse bleiben vorerst an ihren
bisherigen Stellen, damit kein Laufzeitverhalten verändert wird.

## Erkannte Duplikate und mögliche Altlasten

- `_save_upload()` existiert sowohl in `webapp/blueprints/api.py` als auch in
  `webapp/blueprints/imports.py`; beide bedienen unterschiedliche Oberflächen.
- SQLite-Konfiguration liegt für die gemeinsame Desktop-Logik in
  `modules/database.py` und für Flask/SQLAlchemy in `webapp/config.py`.
- `run_webapp.py` und `run_webapp.bat` starten denselben Entwicklungsserver auf
  unterschiedlichen Ebenen.
- `convert_to_pdf()` und `convert_to_pdf_soffice()` sind parallele
  Plattformadapter und keine versehentliche Duplikation.
- Die Jinja-Oberfläche bleibt neben dem React-Frontend als dokumentierter
  Fallback bestehen.
- `modules/ui_*`, `modules/theme.py` und `modules/orchestrator.py` gehören zur
  übernommenen Desktop-Logik; ihre weitere Nutzung durch dieses Repository muss
  separat geprüft werden.

Keiner dieser Punkte wird in dieser Architekturvorbereitung entfernt oder
fachlich zusammengeführt.
