# Mobilfunkverwaltung – Benutzerhandbuch

Webbasierte Verwaltung von Mobilfunkteilnehmern, Verträgen, Geräten, Importen,
Dokumenten und Aufgaben. Dieses Handbuch deckt Installation, Start und
Benutzung ab – für die technische Projektdokumentation siehe
[README.md](../README.md) und [WINDOWS_INSTALL.md](../WINDOWS_INSTALL.md).

## Inhalt

1. [Installation – der einfachste Weg](#1-installation--der-einfachste-weg)
2. [Start und Beenden](#2-start-und-beenden)
3. [Erste Anmeldung](#3-erste-anmeldung)
4. [Benutzung](#4-benutzung)
5. [Rollen und Rechte](#5-rollen-und-rechte)
6. [Datensicherung](#6-datensicherung)
7. [Fehlerbehebung](#7-fehlerbehebung)

---

## 1. Installation – der einfachste Weg

Die Mobilfunkverwaltung läuft als lokale Web-App im Browser – **kein
Setup-Programm, kein Windows-Dienst, keine Administratorrechte nötig.**

1. **ZIP herunterladen:**
   <https://github.com/grumel/mobilfunkverwaltung/releases/download/windows-latest/mobilfunkverwaltung-windows.zip>
2. **Entpacken** (z. B. per Rechtsklick → „Alle extrahieren…").
3. Im entpackten Ordner **`Mobilfunkverwaltung.cmd` doppelklicken.**

Das war's. Python und alle Abhängigkeiten liegen bereits fertig im Paket –
**nichts muss vorher installiert werden.** Beim allerersten Start richtet
sich in wenigen Sekunden der Datenordner ein (kurz ein Konsolenfenster
sichtbar), danach öffnet sich automatisch der Browser.

> **Hinweis für gesperrte Firmen-PCs:** Startet nichts, obwohl Windows
> geöffnet wird? Dann blockiert vermutlich eine Gruppenrichtlinie
> (Softwarerichtlinie/SRP) die Ausführung. In dem Fall bei der IT nachfragen
> oder auf einem anderen PC testen.

### Eine Desktop-Verknüpfung anlegen

Wird beim ersten Start automatisch erstellt (**„Mobilfunkverwaltung"** auf dem
Desktop) – damit reicht künftig ein Doppelklick auf das Symbol.

---

## 2. Start und Beenden

**Start:** Doppelklick auf die Desktop-Verknüpfung oder auf
`Mobilfunkverwaltung.cmd`.

Es erscheint ein kleines **Statusfenster**:

| Symbol | Bedeutung |
| --- | --- |
| 🟠 orange | Server startet gerade |
| 🟢 grün | läuft, im Browser erreichbar (Browser öffnet sich automatisch) |
| 🔴 rot | gestoppt |

Im Statusfenster gibt es zwei Knöpfe:
- **„Im Browser öffnen"** – öffnet `http://127.0.0.1:8000/` erneut.
- **„Beenden"** – stoppt den Server sauber. Auch das Schließen des Fensters
  beendet den Server.

**Wichtig:** Die App läuft **lokal auf diesem Rechner** – wird der Rechner
heruntergefahren oder das Statusfenster geschlossen, ist die Anwendung nicht
mehr erreichbar.

---

## 3. Erste Anmeldung

Nach der Installation liegt eine **Test-Datenbank** mit Beispieldaten bereit:

| Benutzer | Passwort | Rolle |
| --- | --- | --- |
| `admin` | `admin` | Admin |
| `schmidt` | `test1234` | Schreiben |
| `leser` | `test1234` | Lesen |

> Diese Zugangsdaten sind **nur zum Testen** gedacht. Für den echten Betrieb
> die richtige Datenbank einspielen (siehe [WINDOWS_INSTALL.md](../WINDOWS_INSTALL.md),
> Abschnitt „Datenbank bereitstellen") und/oder die Passwörter ändern.

Nach der Anmeldung: oben rechts **„Passwort"**, um das eigene Passwort zu
ändern.

---

## 4. Benutzung

### 4.1 Reiter und Suche

Die Reiter **Vodafone / Telekom / O2 / Ohne SIM / Frei** zeigen die
Teilnehmer je Anbieter. Zusätzlich gibt es abgeleitete Ansichten:

- **Prüfungen** – noch nicht geprüfte (offene) Einträge
- **Unvollständig** – fehlende Pflichtfelder
- **Duplikate** – doppelte Namen
- **Overhead** – manuell markierte Sondereinträge
- **Archiv** – archivierte Teilnehmer (siehe unten)

Die **globale Suche** oben durchsucht *alle* Reiter gleichzeitig, unabhängig
vom gerade gewählten Reiter, mit Live-Trefferzähler. Ein Klick auf einen
**Spaltenkopf** sortiert die Liste; erneuter Klick kehrt die Richtung um.

### 4.2 Teilnehmer bearbeiten, neu anlegen, kopieren

- **Doppelklick** auf eine Zeile öffnet den Bearbeiten-Dialog (per Titelleiste
  frei verschiebbar).
- **„+ Neu"** legt einen leeren Teilnehmer an.
- **Rechtsklick → „Kopieren (als neuer Teilnehmer)"** erstellt einen neuen
  Teilnehmer, bei dem alle Felder der angeklickten Zeile bereits ausgefüllt
  sind (Werk, Konto, Tarif, Geräte, Rahmenvertrag, …) – praktisch, wenn eine
  weitere Person dieselbe Ausstattung wie ein bestehender Eintrag bekommen
  soll. Im sich öffnenden Dialog einfach Name und GSM-Nummer anpassen und
  speichern; der ursprüngliche Eintrag bleibt unverändert.
- **Werk** und **Konto** füllen sich bei festen Zuordnungen gegenseitig
  automatisch aus.
- **CSV-Export** exportiert die aktuell angezeigte (gefilterte/sortierte)
  Liste für Excel.

### 4.3 Rechtsklick-Aktionen

Rechtsklick auf eine Zeile öffnet das Aktionsmenü:

| Aktion | Wirkung |
| --- | --- |
| Bearbeiten | öffnet den Bearbeiten-Dialog |
| Kopieren (als neuer Teilnehmer) | siehe 4.2 |
| Zu Aufgabe … | legt eine Aufgabe mit Kommentar zu diesem Teilnehmer an |
| Als geprüft/offen markieren | Prüfstatus umschalten |
| Zu Overhead schieben/entfernen | Sondermarkierung umschalten |
| Kündigung erstellen/zurücknehmen | siehe 4.6 |
| → nach [Anbieter] | in einen anderen Reiter verschieben |
| Archivieren/Wiederherstellen | siehe 4.2, nur Admin |
| Löschen | endgültig entfernen, nur Admin |

### 4.4 Zusammenführen

„Zusammenführen" aktiviert einen Auswahlmodus: mehrere Zeilen anklicken
(mindestens zwei), dann zusammenführen. Leere Felder des ältesten Eintrags
werden aus den anderen ergänzt, die übrigen Einträge werden anschließend
gelöscht.

### 4.5 Geräte (Syno) und IMEI

Je Teilnehmer lassen sich bis zu zwei Syno-Geräte samt „seit"-Datum und
IMEI-Nummer erfassen. Im Bearbeiten-Dialog steht außerdem ein
**Einzel-Abgleich**-Knopf zur Verfügung: eine Vodafone- oder Syno-Exportdatei
auswählen, die passende Zeile (per GSM-Nummer bzw. Name) wird automatisch in
die Felder übernommen – vor dem Speichern bitte prüfen.

### 4.6 Kündigung, Rücknahme und Neuvertrag (Dokumente)

- **Kündigung erstellen / zurücknehmen** (Rechtsklick auf einen Teilnehmer):
  erzeugt ein **PDF zum Download** aus der Word-Vorlage sowie einen
  **Mailtext zum Kopieren** – in Outlook einfügen, PDF anhängen, senden.
- **„Neuvertrag"**: Name, Werk (Konto füllt sich automatisch) und Tarif
  eingeben – legt einen neuen, noch ungeprüften Teilnehmer an und erzeugt
  einen Mailtext.
- Alle erzeugten Dokumente liegen zusätzlich gesammelt im Reiter
  **„Dokumente"**.

### 4.7 Importe (nur Admin)

Über **„Import"** in der Kopfzeile:

- **Vodafone**: Exportdatei hochladen, Änderungen in einer Vorschau prüfen,
  dann bestätigen.
- **Syno**: Geräte-Exportdatei importieren, optional mit automatischer
  Neuanlage fehlender Teilnehmer. Vor dem eigentlichen Import lässt sich die
  Datei zusätzlich **anreichern**.

### 4.8 Aufgaben

Wiedervorlagen mit Fälligkeitsdatum. Überfällige Aufgaben erscheinen rot,
heute fällige gelb; die Anzahl offener Aufgaben steht als Zähler neben dem
Reiter „Aufgaben".

### 4.9 Statistik und Datenqualität

Kennzahlen und Verteilungen, mit anklickbaren Kacheln, die direkt in die
passende gefilterte Ansicht springen (z. B. „Ohne GSM", „Ablauf < 30 Tage").
Ein eigener Abschnitt zeigt einen Datenqualitäts-Überblick.

### 4.10 Notizen

Der Knopf **„Notizen"** oben rechts öffnet ein persönliches Notizfeld – nur
für den eigenen Account sichtbar, speichert automatisch beim Tippen. Gedacht
für fortlaufende persönliche Vermerke, unabhängig von den Teilnehmerdaten.

### 4.11 Audit-Log

Der Reiter **„Audit"** (nur Admin) zeigt alle Änderungen als lesbare Karten:
wer hat wann was geändert. Bei vielen Einträgen zeigt eine Karte einen
**„↶ Rückgängig"**-Knopf, mit dem sich genau diese Änderung zurücknehmen
lässt. Der Knopf erscheint nur bei Einträgen, die genügend Informationen für
eine Rücknahme mitgeloggt haben – bei sehr alten Einträgen kann er fehlen.

### 4.12 Benutzerverwaltung (nur Admin)

Unter **„Benutzer"**: Konten anlegen/bearbeiten, Rolle setzen (Lesen /
Schreiben / Admin), Konto aktivieren/deaktivieren, Passwort zurücksetzen.

### 4.13 Einstellungen (nur Admin)

Unter **„Einstellungen"**: Datenbank-Pfad bzw. volle Datenbank-URL,
Backup-Download. **Wichtig:** Nach einer Änderung hier muss die Web-App neu
gestartet werden, damit sie wirksam wird (Statusfenster → „Beenden", dann
erneut starten).

> SQLite-Datenbanken gehören **nie** auf ein Netzlaufwerk oder SharePoint –
> das führt zuverlässig zu Fehlern („Benutzer-Tabelle fehlt" o. Ä.), weil
> SQLite Netzwerkspeicher nicht zuverlässig unterstützt. Netzlaufwerke sind
> nur als Backup-Ziel geeignet.

### 4.14 Design und App-Installation

Der Knopf **🌙/☀️** oben schaltet zwischen hellem und dunklem Design um; die
Wahl bleibt gespeichert. In Microsoft Edge lässt sich die Seite über
Menü „…" → **Apps** → „Diese Website als App installieren" als eigenständiges
Fenster mit App-Symbol einrichten.

---

## 5. Rollen und Rechte

| Rolle | Darf |
| --- | --- |
| **Lesen** | alle Daten ansehen, nichts ändern |
| **Schreiben** | zusätzlich bearbeiten, importieren, Dokumente erzeugen |
| **Admin** | zusätzlich Benutzer verwalten, Einstellungen ändern, archivieren/löschen, Audit-Log einsehen |

---

## 6. Datensicherung

- Unter **⚙ Einstellungen** lässt sich jederzeit ein Backup der Datenbank
  herunterladen.
- Bei der Windows-Runtime übernimmt zusätzlich `deploy\windows\backup.ps1`
  eine vollständige Sicherung (Datenbank, Dokumente, Logs) unter
  `%PROGRAMDATA%\Mobilfunkverwaltung\backups\<Zeitstempel>`.
- Empfehlung: vor größeren Änderungen (Import, Zusammenführen vieler
  Einträge, Umstellung der Datenbank) immer erst ein Backup ziehen.

---

## 7. Fehlerbehebung

| Problem | Lösung |
| --- | --- |
| Doppelklick auf `Mobilfunkverwaltung.cmd` tut nichts / Fehler | Meist eine Gruppenrichtlinie (Ausführungsrichtlinie/SRP) – IT kontaktieren oder auf anderem PC testen. |
| „Keine gültige Datenbank gefunden (Benutzer-Tabelle fehlt)" beim Anmelden | Die konfigurierte Datenbank ist nicht erreichbar oder leer – häufigste Ursache: DB-Pfad zeigt auf ein Netzlaufwerk. In ⚙ Einstellungen auf einen lokalen Pfad zurückstellen und neu starten. |
| Login schlägt fehl, obwohl Zugangsdaten stimmen | Nach mehreren Fehlversuchen greift eine kurze Login-Bremse – einige Minuten warten. |
| Änderung in ⚙ Einstellungen wirkt nicht | Web-App muss nach Einstellungsänderungen neu gestartet werden (Statusfenster „Beenden", dann erneut starten). |
| Kündigung/Rücknahme erzeugt kein PDF | Weder Word noch LibreOffice gefunden – die Datei wird dann als `.docx` erzeugt statt als PDF. |
| Mailtext öffnet sich nicht automatisch in Outlook | Kein Outlook installiert – der Mailtext wird stattdessen angezeigt, zum manuellen Kopieren. |

---

*Diese Anleitung wird bei Änderungen an Funktionsumfang oder Bedienung
laufend aktualisiert. Technische Details zu Installation und Betrieb stehen
in [WINDOWS_INSTALL.md](../WINDOWS_INSTALL.md), [docs/WINDOWS.md](WINDOWS.md)
und [README.md](../README.md).*
