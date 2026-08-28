# Mobilfunkverwaltung – Installation unter Windows

Diese Anleitung beschreibt, wie du die Mobilfunkverwaltung als lokale Web‑App
unter Windows einrichtest und startest. Sie läuft im Browser unter
`http://127.0.0.1:8000/` – kein Setup‑EXE, kein Windows‑Dienst, keine
Administratorrechte nötig.

> Ausführliche Hintergründe: [`docs/WINDOWS.md`](docs/WINDOWS.md).

---

## Schnellstart (empfohlen)

1. **ZIP herunterladen** und entpacken:
   <https://github.com/grumel/mobilfunkverwaltung/releases/download/windows-latest/mobilfunkverwaltung-windows.zip>
2. Falls noch nicht vorhanden: **Python 3.12+** installieren
   (<https://www.python.org/downloads/>, beim Setup „Add Python to PATH" anhaken).
3. Im entpackten Ordner **`Mobilfunkverwaltung.cmd` doppelklicken.**

Beim ersten Start richtet sich alles selbst ein (einige Minuten), danach öffnet
sich der Browser unter `http://127.0.0.1:8000/`. Anmelden mit der mitgelieferten
Test-DB: **`admin` / `admin`** (siehe Abschnitt 4). Jeder weitere Start: einfach
wieder `Mobilfunkverwaltung.cmd` doppelklicken.

> **Node.js/Git sind nicht nötig** – der fertige Frontend‑Build liegt bereits im
> ZIP. Es genügt **Python**.

---

## 1. Voraussetzungen

- Windows 10/11 oder Windows Server 2019+ mit **PowerShell 5.1+**
- **Python 3.12+** – mehr nicht (der Frontend‑Build ist im ZIP enthalten).
- Nur wenn du **statt des ZIP klonst** und selbst baust: zusätzlich
  **Node.js 20 LTS** + **Git**.
- Optional: **Microsoft Word** (für die PDF‑Erzeugung bei Kündigung/Rücknahme).
  Unter Windows wird Word genutzt – LibreOffice ist **nicht** nötig.

> **Hinweis für gesperrte Firmen‑PCs:** Die Runtime startet `python.exe` bzw.
> PowerShell‑Skripte lokal. Auf einem per Gruppenrichtlinie (SRP) gesperrten
> Rechner kann das blockiert sein. Zum Testen einen normalen PC verwenden.

---

## 2. Code auf den Rechner bringen

Das immer aktuelle Paket liegt als ZIP im GitHub-Release **`windows-latest`**
(inkl. fertigem Frontend‑Build):

- Release-Seite: <https://github.com/grumel/mobilfunkverwaltung/releases/tag/windows-latest>
- Direkter Download: <https://github.com/grumel/mobilfunkverwaltung/releases/download/windows-latest/mobilfunkverwaltung-windows.zip>

ZIP entpacken und in den entpackten Ordner wechseln (dort, wo `backend\`,
`frontend\` und `Mobilfunkverwaltung.cmd` liegen).

**Nur für Entwickler** – klonen und selbst bauen (braucht Node.js + Git):

```powershell
git clone https://github.com/grumel/mobilfunkverwaltung.git
cd mobilfunkverwaltung
```

---

## 3. Installation

**Einfachster Weg:** `Mobilfunkverwaltung.cmd` doppelklicken – das erledigt
Installation **und** Start in einem Schritt.

Wer die Schritte lieber manuell ausführt:

```powershell
# Optional: nur prüfen, was fehlt (nichts wird installiert):
powershell -ExecutionPolicy Bypass -File .\deploy\windows\bootstrap.ps1 -CheckOnly

# Einrichten (venv + Python-Pakete + Datenordner + Secret):
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install.ps1
```

`install.ps1` legt die virtuelle Umgebung an, installiert die Python‑Pakete und
erstellt den Datenordner samt zufälligem Secret. Ist ein fertiger Frontend‑Build
vorhanden (ZIP‑Fall), wird `npm`/Node **übersprungen**; nur beim Bauen aus dem
Quellcode läuft `npm ci` + `npm run build`. Die Konfigdatei liegt danach unter:

```
%PROGRAMDATA%\Mobilfunkverwaltung\mobilfunk.env.ps1
```

---

## 4. Datenbank bereitstellen

Damit die App **sofort testbar** ist, wird beim Installieren automatisch eine
**Test-Datenbank** an den Standardort gelegt – **aber nur, wenn dort noch keine
`mobilfunk.db` existiert** (eine echte Datenbank wird nie überschrieben).

- Anmeldung in der Test-DB: **`admin` / `admin`** (nur zum Testen!). Weitere
  Benutzer: `schmidt` / `test1234` (Schreiben), `leser` / `test1234` (Lesen).
- Sie enthält ausgedachte Beispiel‑Teilnehmer, damit die Oberfläche gefüllt ist.
- **Für den Echtbetrieb** diese Datei durch deine richtige `mobilfunk.db`
  ersetzen bzw. die Passwörter ändern. Das automatische Einspielen lässt sich mit
  `install.ps1 -NoSampleData` abschalten.

Für den Produktivbetrieb legst du stattdessen deine eigene `mobilfunk.db` bereit
(z. B. eine Kopie einer bestehenden Datenbank; sie enthält Benutzer und Daten).
Beim ersten Start ergänzt die App fehlende Spalten (z. B. `imei`) automatisch.

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
