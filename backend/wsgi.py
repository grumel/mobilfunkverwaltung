"""Gemeinsamer WSGI-Einstiegspunkt für Gunicorn und Waitress."""

from webapp import create_app

app = create_app()
