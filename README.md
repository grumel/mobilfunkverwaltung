# Mobilfunkverwaltung – React-Frontend

Neues Frontend (Phase 3 der [Roadmap](https://github.com/grumel/mdwWeb/blob/main/ROADMAP.md)).
Spricht die **JSON-API** der Flask-App (`mdwWeb` / `Mobilfunk-WebApp`) an.

Aktueller Stand: Login, alle Provider-Tabs + abgeleitete Ansichten (Prüfungen/
Unvollständig/Duplikate), Bearbeiten-Dialog, Rechtsklick-Aktionen (geprüft/
verschieben/löschen, rollenbasiert), Aufgaben (mit Zähler-Badge, Markierung in
Listen), Statistik (Kennzahlen, Werk-Balken, ablaufende Verträge). Wird Tab für
Tab weiter ausgebaut (Import, Einstellungen folgen).

## Voraussetzung
- Node.js (LTS)
- Die Flask-App muss laufen (Port **5001**): im `Mobilfunk-WebApp`-Ordner `run_webapp.bat`

## Entwicklung starten
```bat
npm install
npm run dev
```
Dann Browser auf **http://localhost:5173** — anmelden wie in der Web-/Desktop-App.

Der Vite-Dev-Server proxyt `/api` automatisch auf die Flask-App (`http://127.0.0.1:5001`),
dadurch same-origin → kein CORS, Session-Cookie funktioniert.

## Produktion (später)
`npm run build` erzeugt ein statisches Bundle in `dist/`, das Caddy ausliefert;
die API bleibt hinter demselben Reverse-Proxy.

## Struktur
```
index.html                     Einstieg
vite.config.js                 Dev-Server + /api-Proxy
src/main.jsx                   React-Bootstrap
src/api.js                     API-Client (fetch)
src/App.jsx                    Auth-Status
src/components/Login.jsx
src/components/Shell.jsx       App-Shell, Tab-Leiste, Summary-Polling
src/components/Participants.jsx  Liste, Suche, Rechtsklick-Aktionen
src/components/EditModal.jsx   Bearbeiten-/Neu-Dialog
src/components/Tasks.jsx       Aufgaben
src/components/Stats.jsx       Statistik
src/index.css                  Styling (Look der Web-App)
```
