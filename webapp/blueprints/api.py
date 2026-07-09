"""
api.py – JSON-API für das React-Frontend (Phase 3).

Läuft parallel zur bestehenden serverseitig gerenderten Oberfläche. Session-
Cookie-Auth (wie bisher). CSRF ist für dieses Blueprint ausgenommen (wird in
webapp/__init__.py per csrf.exempt gesetzt) – für den Anfang genügt die
Session; produktiv später Token-/SameSite-Absicherung ergänzen.
"""

from flask import Blueprint, request, jsonify, session
from sqlalchemy import func, or_

from webapp.db import SessionLocal
from webapp.models import Participant, User
from webapp.security import current_user
from webapp import service as svc
from modules.auth import verify_password

bp = Blueprint("api", __name__, url_prefix="/api")

# Felder, die die Teilnehmer-API zurückgibt
FIELDS = ["id", "master_id", "gsm", "name", "plant", "konto", "tarif",
          "vertragsende", "bemerkung", "verified", "provider"]
SEARCH_FIELDS = ["name", "gsm", "plant", "konto", "tarif", "bemerkung"]


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    db = SessionLocal()
    try:
        user = (db.query(User)
                  .filter(User.username == username, User.active == 1).first())
    finally:
        db.close()
    if user and verify_password(password, user.password_hash):
        session["user"] = {"id": user.id, "username": user.username, "role": user.role}
        return jsonify(user=session["user"])
    return jsonify(error="Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch."), 401


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
def me():
    u = current_user()
    if not u:
        return jsonify(error="nicht angemeldet"), 401
    return jsonify(user=u)


@bp.get("/participants")
def participants():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    provider = svc.SLUG_TO_PROVIDER.get(request.args.get("provider", "vodafone"), "Vodafone")
    q = (request.args.get("q") or "").strip()
    db = SessionLocal()
    try:
        query = db.query(Participant).filter(
            func.coalesce(Participant.provider, "Vodafone") == provider)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(*[getattr(Participant, f).ilike(like)
                                       for f in SEARCH_FIELDS]))
        rows = query.order_by(Participant.name).all()
        out = [{f: getattr(r, f) for f in FIELDS} for r in rows]
    finally:
        db.close()
    return jsonify(participants=out, total=len(out), provider=provider)
