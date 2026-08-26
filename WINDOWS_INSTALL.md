# Mobilfunkverwaltung – Installation unter Windows

Diese Anleitung beschreibt, wie du die Mobilfunkverwaltung als lokale Web‑App
unter Windows einrichtest und startest. Sie läuft im Browser unter
`http://127.0.0.1:8000/` – kein Setup‑EXE, kein Windows‑Dienst, keine
Administratorrechte nötig.

> Ausführliche Hintergründe: [`docs/WINDOWS.md`](docs/WINDOWS.md).

---

## 1. Voraussetzungen

- Windows 10/11 oder Windows Server 2019+ mit **PowerShell 5.1+**
- **Python 3.12+**, **Node.js 20 LTS** (inkl. `npm`), **Git**
- Optional: **Microsoft Word** (für die PDF‑Erzeugung bei Kündigung/Rücknahme).
  Unter Windows wird Word genutzt – LibreOffice ist **nicht** nötig.

> **Hinweis für gesperrte Firmen‑PCs:** Die Runtime startet `python.exe` bzw.
> PowerShell‑Skripte lokal. Auf einem per Gruppenrichtlinie (SRP) gesperrten
> Rechner kann das blockiert sein. Zum Testen einen normalen PC verwenden.

---

## 2. Code auf den Rechner bringen

Entweder dieses ZIP entpacken (du liest ja bereits die enthaltene Anleitung),
**oder** – falls verfügbar – klonen:

```powershell
git clone https://github.com/grumel/mobilfunkverwaltung.git
cd mobilfunkverwaltung
```

Beim ZIP: entpacken und in den entpackten Ordner wechseln (dort, wo `backend\`
und `frontend\` liegen).

---

## 3. Voraussetzungen prüfen / installieren

```powershell
# Nur prüfen, was fehlt (nichts wird installiert):
powershell -ExecutionPolicy Bypass -File .\deploy\windows\bootstrap.ps1 -CheckOnly

# Fehlendes automatisch per winget nachinstallieren und danach installieren:
powershell -ExecutionPolicy Bypass -File .\deploy\windows\bootstrap.ps1 -Install
```

Ist alles schon vorhanden, genügt direkt:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install.ps1
```

`install.ps1` legt die virtuelle Umgebung an, installiert die Python‑Pakete,
baut das React‑Frontend (`npm ci` + `npm run build`) und erstellt den
Datenordner samt zufälligem Secret. Die Konfigdatei liegt danach unter:

```
%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.env.ps1
```

---

## 4. Datenbank bereitstellen

Auf einem frischen Rechner ist **keine Datenbank** vorhanden – die App legt sie
nicht selbst an. Ohne DB gibt es keine Benutzer, also kein Login. Lege deshalb
eine `mobilfunk.db` bereit (z. B. eine Kopie einer bestehenden Datenbank; sie
enthält Benutzer und Daten). Beim ersten Start ergänzt die App fehlende Spalten
(z. B. `imei`) automatisch.

### Standardort
Standardmäßig wird die DB hier erwartet:

```
%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.db
```

### Eigenen Speicherort verwenden (empfohlen, wenn die DB woanders liegt)
Die DB an den gewünschten Ort legen (z. B. `D:\Mobilfunk\mobilfunk.db`), dann
die Konfigdatei `%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.env.ps1` öffnen und
**eine** dieser Zeilen ergänzen:

```powershell
# Variante A – nur die Datenbank auslagern (Dokumente/Logs bleiben lokal):
$env:DATABASE_URL = "sqlite:///D:/Mobilfunk/mobilfunk.db"

# Variante B – kompletten Datenordner verlagern:
$env:MOBILFUNK_DATA_DIR      = "D:\Mobilfunk"
$env:MOBILFUNK_WEBCONFIG_DIR = "D:\Mobilfunk"
```

> SQLite‑URL: **drei** Schrägstriche und **Vorwärts**‑Slashes im Pfad, also
> `sqlite:///D:/Ordner/mobilfunk.db`.

Die App bestimmt die Datenbank in dieser Reihenfolge:
`DATABASE_URL` (Env) → Einstellungen‑Seite (`webconfig.json`) → Standardort.
Der DB‑Pfad lässt sich später auch in der App unter **⚙ Einstellungen** ändern.

---

## 5. Starten

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\start.ps1 -OpenBrowser
```

Öffnet `http://127.0.0.1:8000/`. Anmelden mit den gewohnten Zugangsdaten.

Weitere Skripte: `stop.ps1` (beenden), `update.ps1` (aktualisieren),
`backup.ps1` (DB sichern), `uninstall.ps1` (entfernt nur venv/Build/Caches –
Daten bleiben erhalten).

---

## 6. PDF‑Engine (optional)

Kündigung/Rücknahme füllen die Word‑Vorlage plattformneutral (docxtpl); nur die
PDF‑Erzeugung ist plattformabhängig:

| Variable | Wirkung |
| --- | --- |
| `MOBILFUNK_PDF_ENGINE` | `word` oder `soffice` erzwingen (Standard `auto`) |
| `MOBILFUNK_SOFFICE` | Pfad zu einer LibreOffice‑Installation/Portable |

Ist weder Word noch LibreOffice vorhanden, meldet die API einen klaren Fehler,
statt abzustürzen.

---

## 7. Fehlersuche

- **Skriptaufruf schlägt sofort fehl:** Die Ausführungsrichtlinie ist per
  Gruppenrichtlinie gesetzt; `-ExecutionPolicy Bypass` greift dann nicht. Dann
  müssen die Skripte signiert oder von der IT freigegeben werden.
- **`python`/`node`/`npm` nicht gefunden:** `bootstrap.ps1 -Install` ausführen
  oder manuell installieren, neues PowerShell‑Fenster öffnen.
- **Login nicht möglich:** Es liegt keine (gültige) `mobilfunk.db` am erwarteten
  Ort – siehe Abschnitt 4.
