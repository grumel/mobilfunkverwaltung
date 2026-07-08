"""
run_webapp.py – Startet die Web-Version lokal (Flask-Entwicklungsserver).

Nur für PoC/Entwicklung. Läuft auf der bestehenden SQLite-DB; für PostgreSQL
die Umgebungsvariable DATABASE_URL setzen (siehe webapp/config.py).
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path

# Pfade: WebApp/ (enthält das Paket 'webapp') und Projektwurzel (enthält 'modules')
_HERE = Path(__file__).resolve().parent      # …/WebApp
_ROOT = _HERE.parent                          # Projektwurzel
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

from webapp import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    if os.environ.get("MOBILFUNK_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
