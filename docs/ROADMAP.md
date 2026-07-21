# Roadmap

## Version 1.0 – abgeschlossen

- Monorepo aus Backend und Frontend
- Linux-Produktivbetrieb mit systemd, Gunicorn und Caddy
- Rückrollbare Produktionsmigration und dokumentierte Backups

## Version 1.1 – Qualität und Sicherheit

1. P0: Authentifizierte Test-Fixtures für Login, Rollen und Sessions.
2. P0: Upload-/Dokumenten- und Path-Traversal-Tests.
3. P1: Testabdeckung für Teilnehmer, Aufgaben, Geräte, Importe und Exporte.
4. P1: Zentraler, getesteter Pfad-Resolver ohne API- oder UI-Änderung.
5. P1: Transparente Fehlerbehandlung beim Schema-Check und redigiertes Logging.
6. P2: Performance- und Bundle-Baselines.

## Version 1.2 – kontrollierte interne Konsolidierung

- Nach grünen Regressionstests kleine Extraktionen aus großen Blueprints.
- Verantwortungsgrenzen zwischen Desktop-SQLite und Web-SQLAlchemy schärfen.
- Konfigurations- und Startpfade vereinheitlichen, ohne öffentliche Verträge zu
  ändern.
- Optionale PostgreSQL- und Backup-Strategie separat testen.

## Windows-Unterstützung

Die vorhandenen Dateien unter `deploy/windows/` bleiben experimentell. Vor
Produktionsfreigabe sind ein eigener Testhost, Dienst-/Prozessmodell,
Datenpfad-, Rechte-, Caddy- und LibreOffice-Tests erforderlich. Windows darf
die Linux-Konfiguration und das gemeinsame API-Verhalten nicht ungeprüft
beeinflussen.
