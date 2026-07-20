"""
run_webapp.py – Startet die Web-Version lokal (Flask-Entwicklungsserver).

Nur für PoC/Entwicklung. Läuft auf der bestehenden SQLite-DB; für PostgreSQL
die Umgebungsvariable DATABASE_URL setzen (siehe webapp/config.py).
"""

import sys
from pathlib import Path

# Pfade: WebApp/ (enthält das Paket 'webapp') und Projektwurzel (enthält 'modules')
_HERE = Path(__file__).resolve().parent      # …/WebApp
_ROOT = _HERE.parent                          # Projektwurzel
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

from run import app, main

if __name__ == "__main__":
    main()
