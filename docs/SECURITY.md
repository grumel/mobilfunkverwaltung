# Sicherheitsleitfaden

## Aktueller Schutz

- Secrets liegen außerhalb des Repositories; die Produktions-Environment-Datei
  ist `root:root` mit Modus `0600`.
- Flask verwendet einen persistenten Secret Key und HttpOnly-/SameSite-
  Session-Cookies. `MOBILFUNK_HTTPS=1` aktiviert Secure-Cookies.
- Flask-WTF schützt HTML-Formulare per CSRF. Die JSON-Blueprints sind bewusst
  CSRF-exempt und verwenden Session-Authentifizierung; dieser Vertrag darf
  nicht ungeprüft geändert werden.
- Caddy setzt CSP, `X-Content-Type-Options`, `X-Frame-Options` und
  `Referrer-Policy`.
- SQL-Werte werden überwiegend parametrisiert bzw. über SQLAlchemy gebunden.
- Uploads nutzen `secure_filename`; Downloadnamen werden mit `basename`
  begrenzt.

## Befunde

- Datei- und Dokumentpfade werden an mehreren API-Stellen zusammengesetzt.
  Eine zentrale Allowlist der erlaubten Datenwurzeln wäre sicherer.
- Dynamische SQL-Spaltennamen in der Desktop-Schicht benötigen eine feste
  Allowlist und Regressionstests.
- `create_app()` verschluckt Fehler beim Schema-Check; das erschwert Erkennung
  eines inkonsistenten Datenbankschemas.
- Authentifizierte Upload-, Traversal- und Rollenprüfungen sind nicht als
  umfangreiche automatisierte Tests vorhanden.
- Logging ist nicht zentral klassifiziert; Eingabedaten dürfen nicht ungefiltert
  in Logs gelangen.

## Priorisierte Maßnahmen

1. P0: Upload-/Download- und Traversal-Fixtures mit temporärer Datenwurzel.
2. P0: Authentifizierte Rollen- und Session-Tests mit Testkonto/Fixture.
3. P1: Statische SQL-Feld-Allowlist und Tests für unbekannte Felder.
4. P1: Fehler beim Schema-Check strukturiert protokollieren, ohne Startverhalten
   ungeprüft zu verändern.
5. P2: Regelmäßiger Secret-/Dependency-Scan in CI.

Bis diese Tests existieren, werden keine Pfad- oder Sicherheitsabstraktionen in
produktiven Code verschoben.
