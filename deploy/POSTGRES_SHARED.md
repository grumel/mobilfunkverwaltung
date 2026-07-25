# Gemeinsame PostgreSQL-Datenbank für mehrere Windows-Arbeitsplätze

Diese Anleitung beschreibt den Mehrbenutzerbetrieb: mehrere Windows-PCs
betreiben jeweils lokal die Web-App (Waitress, siehe
[`deploy/windows/`](windows/README.md)) und greifen gemeinsam auf **eine**
zentrale PostgreSQL-Datenbank zu.

```text
PC 1  Waitress+Flask ─┐
PC 2  Waitress+Flask ─┤   LAN    ┌───────────────────────────┐
PC 3  Waitress+Flask ─┼────────► │ PostgreSQL-Host :5432      │
 …                    ─┘         │ Datenbank "mobilfunk"      │
                                 └───────────────────────────┘
```

PostgreSQL ist für gleichzeitigen Mehrfachzugriff ausgelegt. Damit entfällt der
Grund, weshalb SQLite hier nicht auf ein Netzlaufwerk oder SharePoint durfte:
Statt eine Datei zu teilen, sprechen alle Clients denselben Datenbankdienst an,
der Sperren und Transaktionen selbst koordiniert.

## 1. Der Datenbank-Host

Die Datenbank braucht **eine dauerhaft laufende, im Netz erreichbare Maschine**.
Ein normaler Arbeitsplatz-PC ist ungeeignet: Ist er aus, hat niemand mehr eine
Datenbank. Geeignet sind

- der geplante Linux-Server (ThinkPad) – bevorzugt, Installation siehe
  [`deploy/linux/POSTGRES.md`](linux/POSTGRES.md), oder
- ein dedizierter Windows-Rechner bzw. Windows Server, der immer läuft.

Es genügt **ein** Postgres-Host für alle Arbeitsplätze.

### PostgreSQL unter Windows installieren

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --exact --silent
```

Danach Datenbank und Benutzer anlegen (in „SQL Shell (psql)" oder per
`psql -U postgres`):

```sql
CREATE USER mobilfunk WITH PASSWORD 'BITTE-AENDERN';
CREATE DATABASE mobilfunk OWNER mobilfunk;
```

Für Linux gelten die Schritte aus [`deploy/linux/POSTGRES.md`](linux/POSTGRES.md)
unverändert.

## 2. PostgreSQL für den Netzwerkzugriff öffnen

Standardmäßig lauscht Postgres nur lokal. Zwei Dateien im Datenverzeichnis
(`postgresql.conf`, `pg_hba.conf`) anpassen:

`postgresql.conf`:

```conf
listen_addresses = '*'
```

`pg_hba.conf` – **nur das eigene Büro-Subnetz** freigeben, niemals `0.0.0.0/0`:

```conf
# TYP   DB          USER        ADRESSE            METHODE
hostssl mobilfunk   mobilfunk   192.168.10.0/24    scram-sha-256
```

Danach den Dienst neu starten und Port 5432 in der Firewall nur für dieses
Subnetz öffnen. `hostssl` erzwingt eine verschlüsselte Verbindung – wichtig,
weil hier **personenbezogene Daten** (Namen, Rufnummern) durchs Netz gehen. Ohne
eingerichtetes Serverzertifikat übergangsweise `host` statt `hostssl`, dann aber
zeitnah TLS nachrüsten.

## 3. Daten einmalig migrieren

Die Migration läuft **einmal** von einem beliebigen Rechner gegen die aktuelle
produktive SQLite-Datei. Die SQLite-Datei wird nur gelesen und bleibt als
Fallback erhalten.

```powershell
backend\.venv\Scripts\python.exe deploy\linux\migrate_to_postgres.py `
    --sqlite "C:\ProgramData\Mobilfunkverwaltung\mobilfunk.db" `
    --postgres "postgresql+psycopg://mobilfunk:BITTE-AENDERN@DBHOST:5432/mobilfunk"
```

Das Skript gibt je Tabelle die kopierte Zeilenzahl aus. Danach automatisch
prüfen (Zeilenzahlen **und** id-Sequenzen), **bevor** sich jemand anmeldet:

```powershell
backend\.venv\Scripts\python.exe deploy\verify_migration.py `
    --sqlite "C:\ProgramData\Mobilfunkverwaltung\mobilfunk.db" `
    --postgres "postgresql+psycopg://mobilfunk:BITTE-AENDERN@DBHOST:5432/mobilfunk"
```

Exit-Code 0 = alle Tabellen zeilengleich und Sequenzen korrekt. `DBHOST` ist der
Name oder die IP des Datenbank-Hosts.

## 4. Jeden Arbeitsplatz auf die gemeinsame Datenbank zeigen lassen

Auf **jedem** PC in der Laufzeitkonfiguration
`%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.env.ps1` dieselbe Zeile ergänzen:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://mobilfunk:BITTE-AENDERN@DBHOST:5432/mobilfunk?sslmode=require'
```

`DATABASE_URL` hat Vorrang vor allem anderen (siehe `webapp/config.py`). Nach dem
Ergänzen `start.ps1` neu starten. Wichtig:

- Die URL ist auf allen PCs **identisch**.
- `MOBILFUNK_SECRET` bleibt **pro PC** wie vom Installer erzeugt – jede lokale
  Web-App verwaltet ihre eigenen Sitzungscookies auf `127.0.0.1`.
- Das Passwort steht damit im Klartext in einer lokalen Datei; sie liegt unter
  `%PROGRAMDATA%` außerhalb des Git-Checkouts und sollte entsprechend geschützt
  sein.

## 5. Sicherung

Backups laufen jetzt **zentral auf dem Datenbank-Host**, nicht mehr pro PC. Das
bisherige SQLite-Backup vor jedem Import entfällt bei Postgres automatisch.

```bash
pg_dump -U mobilfunk mobilfunk | gzip > mobilfunk_$(date +%F).sql.gz
```

Unter Windows als geplante Aufgabe (Task Scheduler) einrichten, unter Linux per
Cron. Diese `.sql.gz`-Sicherung ist eine vollständige, in sich konsistente Kopie
und eignet sich auch als Ablage auf SharePoint – anders als die frühere
Live-SQLite-Datei.

## 6. Zurückrollen

Auf einem PC genügt es, die `DATABASE_URL`-Zeile aus `mobilfunk.env.ps1` zu
entfernen und neu zu starten – dann nutzt dieser PC wieder seine lokale
SQLite-Datei. Das ist allerdings nur zur Fehlersuche sinnvoll: Ohne gemeinsame
`DATABASE_URL` sieht dieser Arbeitsplatz die geteilten Daten nicht mehr.

## Was dieser Schritt nicht ändert

- Kein Code-Umbau nötig: Modelle, API, Import und Backups sind bereits
  DB-neutral (SQLAlchemy). Aktiviert wurde nur der Treiber `psycopg` in
  `backend/requirements-server.txt`.
- Die lokale Windows-Runtime (Installer, Start, Stopp) bleibt unverändert; sie
  bekommt lediglich die zusätzliche `DATABASE_URL`.
