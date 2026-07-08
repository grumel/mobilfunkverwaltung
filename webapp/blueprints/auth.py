"""
auth.py – Login/Logout. Nutzt das bestehende Passwort-Hashing (modules/auth.py),
damit sich vorhandene Benutzer unverändert anmelden können.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from webapp.db import SessionLocal
from webapp.models import User
from modules.auth import verify_password

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        db = SessionLocal()
        try:
            user = (db.query(User)
                      .filter(User.username == username, User.active == 1)
                      .first())
        finally:
            db.close()
        if user and verify_password(password, user.password_hash):
            session["user"] = {"id": user.id, "username": user.username,
                               "role": user.role}
            nxt = request.args.get("next") or url_for("participants.index")
            return redirect(nxt)
        flash("Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch.")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
