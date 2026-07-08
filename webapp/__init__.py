"""
webapp – Flask-Anwendung (Web-Version der Mobilfunkverwaltung).

App-Factory: erzeugt die Flask-App, registriert Blueprints und stellt den
angemeldeten Benutzer in allen Templates bereit.
"""

import os

from flask import Flask

from webapp.config import SECRET_KEY
from webapp.security import current_user, can


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY

    # CSRF-Schutz (per Umgebungsvariable MOBILFUNK_CSRF=0 abschaltbar, z. B. für Tests)
    if os.environ.get("MOBILFUNK_CSRF", "1") != "0":
        from flask_wtf import CSRFProtect
        CSRFProtect(app)
    else:
        # Ohne CSRF trotzdem csrf_token() in Templates verfügbar halten (No-op)
        app.jinja_env.globals.setdefault("csrf_token", lambda: "")

    from webapp.blueprints.auth import bp as auth_bp
    from webapp.blueprints.participants import bp as participants_bp
    from webapp.blueprints.tabs import bp as tabs_bp
    from webapp.blueprints.imports import bp as imports_bp
    from webapp.blueprints.tasks import bp as tasks_bp
    from webapp.blueprints.reports import bp as reports_bp
    from webapp.blueprints.settings import bp as settings_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(participants_bp)
    app.register_blueprint(tabs_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)

    from webapp.service import NAV_PROVIDERS

    def _open_task_data():
        """(Menge Teilnehmer-IDs mit offener Aufgabe, Anzahl offener Aufgaben)."""
        if not current_user():
            return set(), 0
        from sqlalchemy import func
        from webapp.db import SessionLocal
        from webapp.models import Task
        db = SessionLocal()
        try:
            pids = {r[0] for r in db.query(Task.participant_id)
                    .filter(Task.erledigt == 0, Task.participant_id.isnot(None)).all()}
            cnt = db.query(func.count()).select_from(Task).filter(Task.erledigt == 0).scalar() or 0
        finally:
            db.close()
        return pids, cnt

    @app.context_processor
    def _inject():
        pids, cnt = _open_task_data()
        return {"current_user": current_user(), "can": can,
                "nav_providers": NAV_PROVIDERS,
                "open_task_pids": pids, "open_task_count": cnt}

    return app
