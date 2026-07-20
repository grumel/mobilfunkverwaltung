"""Gemeinsamer plattformneutraler Einstiegspunkt.

Produktive Linux-Deployments verwenden weiterhin gunicorn mit der App-Factory.
Unter Windows startet dieses Modul Waitress. Auf anderen Plattformen bleibt
der bisherige lokale Flask-Entwicklungsstart erhalten.
"""

import logging
import os
import threading
import webbrowser
from logging.handlers import RotatingFileHandler

from platform_support import get_log_directory, is_windows
from webapp import create_app


app = create_app()


def _configure_windows_logging() -> None:
    log_dir = get_log_directory()
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "mobilfunk-web.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _serve_waitress(host: str, port: int) -> None:
    from waitress import serve

    _configure_windows_logging()
    serve(
        app,
        host=host,
        port=port,
        threads=int(os.environ.get("WAITRESS_THREADS", "8")),
        connection_limit=int(os.environ.get("WAITRESS_CONNECTION_LIMIT", "100")),
        channel_timeout=int(os.environ.get("WAITRESS_CHANNEL_TIMEOUT", "120")),
    )


def main() -> None:
    port = int(os.environ.get("PORT", "5001"))
    if os.environ.get("MOBILFUNK_NO_BROWSER") != "1":
        threading.Timer(
            1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")
        ).start()
    if is_windows() and os.environ.get("MOBILFUNK_SERVER") != "flask":
        _serve_waitress(os.environ.get("HOST", "127.0.0.1"), port)
        return
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
