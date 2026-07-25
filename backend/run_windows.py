"""Lokaler Windows-Webserver: Waitress und React auf einem Port."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from waitress import serve

from wsgi import app

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = Path(os.environ.get("MOBILFUNK_FRONTEND_DIST", ROOT / "frontend" / "dist"))


class SpaApplication:
    """Reicht API-Anfragen an Flask und übrige Anfragen an das SPA weiter."""

    def __init__(self, flask_app, frontend_dist: Path):
        self.flask_app = flask_app
        self.frontend_dist = frontend_dist

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path == "/api" or path.startswith("/api/"):
            return self.flask_app(environ, start_response)
        relative = path.lstrip("/")
        candidate = (self.frontend_dist / relative).resolve()
        try:
            candidate.relative_to(self.frontend_dist.resolve())
        except ValueError:
            start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Not found"]
        if not candidate.is_file():
            candidate = self.frontend_dist / "index.html"
        if not candidate.is_file():
            start_response("503 Service Unavailable", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Frontend build not found"]
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(body)))])
        return [body]


def main() -> None:
    host = os.environ.get("MOBILFUNK_HOST", "127.0.0.1")
    port = int(os.environ.get("MOBILFUNK_PORT", os.environ.get("PORT", "8000")))
    if not FRONTEND_DIST.joinpath("index.html").is_file():
        raise SystemExit(f"Frontend-Build fehlt: {FRONTEND_DIST / 'index.html'}")
    serve(SpaApplication(app, FRONTEND_DIST), host=host, port=port,
          threads=int(os.environ.get("WAITRESS_THREADS", "8")))


if __name__ == "__main__":
    main()
