# Mobilfunkverwaltung – React-Frontend

Neues Frontend (Phase 3 der [Roadmap](../Mobilfunk-WebApp/ROADMAP.md)). Spricht die
**JSON-API** der Flask-App (`Mobilfunk-WebApp`) an. Aktueller Stand: **Fundament** –
Login + Provider-Tabs/Vodafone-Liste mit Live-Suche. Wird Tab für Tab ausgebaut.

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
index.html            Einstieg
vite.config.js        Dev-Server + /api-Proxy
src/main.jsx          React-Bootstrap
src/api.js            API-Client (fetch)
src/App.jsx           Auth-Status + App-Shell
src/components/Login.jsx
src/components/Participants.jsx
src/index.css         Styling (Look der Web-App)
```
