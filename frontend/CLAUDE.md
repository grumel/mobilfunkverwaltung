# Projektkontext für Claude (Mobilfunkverwaltung – React-Frontend)

Sprache: Deutsch. Ausführlicher Kontext (Backend, Deployment, Roadmap) steht in
`CLAUDE.md` / `ROADMAP.md` im **Backend-Repo**: github.com/grumel/mdwWeb.

## Was
React-Frontend (Vite) für die Mobilfunkverwaltung. Spricht ausschließlich die
**JSON-API** des Backends an (Präfix `/api`, Session-Cookie-Auth). Kein eigener
Server-State — alles lebt in der Flask-App (mdwWeb-Repo) + der Datenbank.

## Architektur
- `src/api.js` — einziger Ort mit `fetch`-Aufrufen (`req()` für JSON, `upload()`
  für Datei-Uploads/multipart). Alle Komponenten rufen nur `api.*`.
- `src/App.jsx` — prüft `/api/me`, zeigt `Login` oder `Shell`.
- `src/components/Shell.jsx` — Tab-Leiste + Routing zwischen den Ansichten
  (kein react-router, einfacher `useState`-View-Switch reicht bisher).
- Je Bereich eine Komponente: `Participants`, `EditModal`, `Tasks`, `Stats`,
  `Import`, `Settings`.
- Styling: einfaches CSS (`src/index.css`), am Look der alten Jinja-UI orientiert
  (gleiche Farbvariablen/Klassennamen wie `mdwWeb/webapp/static/app.css`).

## Entwicklung
- Backend muss laufen (Port 5001): im `mdwWeb`/`Mobilfunk-WebApp`-Repo `run_webapp.bat`.
- `npm install && npm run dev` → http://localhost:5173. `vite.config.js` proxyt
  `/api` auf `http://127.0.0.1:5001` (same-origin, kein CORS, Session-Cookie
  funktioniert automatisch).
- Vor jedem Commit sollte `npm run build` fehlerfrei durchlaufen (Produktions-Build,
  keine separate Test-Suite bisher).

## Deployment
Wird **nicht** als eigener Node-Prozess betrieben. Auf dem Server: `npm run build`
→ statisches `dist/`, ausgeliefert von **Caddy** (Backend-Repo `deploy/Caddyfile`,
`deploy/install.sh`). Details dort.

## Stand & offene Punkte
Fertig: Login, alle Provider-Tabs + abgeleitete Ansichten (Prüfungen/
Unvollständig/Duplikate), Bearbeiten/Neu, Rechtsklick-Aktionen (geprüft/
verschieben/löschen, rollenbasiert), Aufgaben (Zähler-Badge, rote Markierung),
Statistik, Import (Vodafone Vorschau/Bestätigen, Syno), Einstellungen (DB-Pfad).

Fehlt noch (existiert im alten Jinja-UI, aber nicht in React):
- **Zusammenführen** (Merge-Modus für mehrere Teilnehmer)
- **Protokoll/Audit-Log**-Ansicht

## Konventionen
- Sprache Deutsch (UI-Texte, Kommentare, Commits).
- Commits: `feat:` / `fix:` / `chore:`, am Ende `Co-Authored-By`-Trailer.
- Keine neue Abhängigkeit ohne Grund — bisher bewusst schlank (React, react-dom,
  react-router-dom ist installiert aber noch ungenutzt).
