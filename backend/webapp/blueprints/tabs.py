"""
tabs.py – Abgeleitete Listen (keine eigenen Register, sondern gefilterte Sichten):
Offene Prüfungen, Unvollständig, Duplikate, Nicht zugeordnet, Werk-Übersicht.
"""

from flask import (Blueprint, render_template, request, Response, url_for, abort)
from sqlalchemy import func, or_, select, case

from webapp.db import SessionLocal
from webapp.models import Participant, UnmatchedDevice
from webapp.security import login_required
from webapp import service as svc
from webapp.blueprints.participants import COLUMNS, SEARCH_FIELDS

bp = Blueprint("tabs", __name__)

DERIVED = {
    "offen":          "Offene Prüfungen",
    "unvollstaendig": "Unvollständig",
    "duplikate":      "Duplikate",
}


def _apply_search(query, q):
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(*[getattr(Participant, f).ilike(like)
                                   for f in SEARCH_FIELDS]))
    return query


def load_derived(db, key, q):
    if key == "offen":
        query = db.query(Participant).filter(Participant.verified == 0)
    elif key == "unvollstaendig":
        query = db.query(Participant).filter(or_(
            Participant.gsm.is_(None),   Participant.gsm == "",
            Participant.plant.is_(None), Participant.plant == "",
            Participant.konto.is_(None), Participant.konto == ""))
    elif key == "duplikate":
        norm = func.lower(func.trim(Participant.name))
        dup = (select(norm)
               .where(Participant.name.isnot(None), Participant.name != "")
               .group_by(norm).having(func.count() > 1))
        query = db.query(Participant).filter(norm.in_(dup))
    else:
        abort(404)
    return _apply_search(query, q).order_by(Participant.name).all()


@bp.route("/t/<key>")
@login_required
def derived(key):
    if key not in DERIVED:
        abort(404)
    q = request.args.get("q", "")
    db = SessionLocal()
    try:
        rows = load_derived(db, key, q)
    finally:
        db.close()
    return render_template("participants/list.html",
                           columns=COLUMNS, rows=rows, total=len(rows), q=q,
                           title=DERIVED[key], provider=None, slug=None,
                           active_provider="", active_tab=key,
                           rows_url=url_for("tabs.derived_rows", key=key),
                           providers=svc.PROVIDERS)


@bp.route("/t/<key>/rows")
@login_required
def derived_rows(key):
    if key not in DERIVED:
        abort(404)
    db = SessionLocal()
    try:
        rows = load_derived(db, key, request.args.get("q", ""))
    finally:
        db.close()
    html = render_template("participants/_rows.html", columns=COLUMNS, rows=rows)
    return Response(html, mimetype="text/html")


@bp.route("/nicht-zugeordnet")
@login_required
def unmatched():
    db = SessionLocal()
    try:
        rows = (db.query(UnmatchedDevice)
                  .order_by(UnmatchedDevice.importdatum.desc()).all())
    finally:
        db.close()
    return render_template("tabs/unmatched.html", rows=rows, active_tab="unmatched")


@bp.route("/werke")
@login_required
def werke():
    werk = func.coalesce(Participant.plant, "(kein Werk)")
    db = SessionLocal()
    try:
        rows = (db.query(
                    werk.label("werk"),
                    func.count().label("gesamt"),
                    func.sum(case((Participant.verified == 0, 1), else_=0)).label("ungeprueft"),
                    func.sum(case((func.coalesce(Participant.vodafone_aktiv, 0) == 0, 1), else_=0)).label("ohne_vf"))
                  .group_by(werk).order_by(werk).all())
    finally:
        db.close()
    return render_template("tabs/werke.html", rows=rows, active_tab="werke")
