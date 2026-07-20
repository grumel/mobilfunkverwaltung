"""Gemeinsamer plattformneutraler Einstiegspunkt für den lokalen Betrieb.

Produktive Linux-Deployments verwenden weiterhin gunicorn mit der App-Factory.
Ein produktiver Windows-Dienst wird erst in einer späteren Portierungsphase
ergänzt.
"""

import os
import threading
import webbrowser

from webapp import create_app


app = create_app()


def main() -> None:
    port = int(os.environ.get("PORT", "5001"))
    if os.environ.get("MOBILFUNK_NO_BROWSER") != "1":
        threading.Timer(
            1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")
        ).start()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
