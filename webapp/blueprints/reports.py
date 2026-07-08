"""
reports.py – Statistik-Dashboard und Protokoll-Ansichten (Import-Log, Audit-Log).
Alles read-only. Audit-Log nur für Administratoren.
"""

from datetime import date, timedelta

from flask import Blueprint, render_template
from sqlalchemy import func, or_, and_

from webapp.db import SessionLocal
from webapp.models import Participant, ImportLog, AuditLog, Task
from webapp.security import login_required, require

bp = Blueprint("reports", __name__)


def _count(db, *criteria):
    q = db.query(func.count()).select_from(Participant)
    for c in criteria:
        q = q.filter(c)
    return q.scalar() or 0


@bp.route("/statistik")
@login_required
def statistik():
    today = date.today().isoformat()
    in30 = (date.today() + timedelta(days=30)).isoformat()
    in60 = (date.today() + timedelta(days=60)).isoformat()
    in90 = (date.today() + timedelta(days=90)).isoformat()
    db = SessionLocal()
    try:
        P = Participant
        has_syno = or_(and_(P.syno.isnot(None), P.syno != ""),
                       and_(P.syno2.isnot(None), P.syno2 != ""))
        stats = {
            "total":        _count(db),
            "verified":     _count(db, P.verified == 1),
            "zur_pruefung": _count(db, P.verified == 0),
            "ohne_gsm":     _count(db, or_(P.gsm.is_(None), P.gsm == "")),
            "mit_syno":     _count(db, has_syno),
            "abgelaufen":   _count(db, P.vertragsende.isnot(None), P.vertragsende != "",
                                   P.vertragsende < today),
            "ablauf_30":    _count(db, P.vertragsende >= today, P.vertragsende <= in30),
            "ablauf_60":    _count(db, P.vertragsende > in30, P.vertragsende <= in60),
            "ablauf_90":    _count(db, P.vertragsende > in60, P.vertragsende <= in90),
        }
        werk = func.coalesce(P.plant, "(kein Werk)")
        werke = (db.query(werk.label("werk"), func.count().label("n"))
                   .group_by(werk).order_by(func.count().desc()).all())
        ablauf = (db.query(P.name, P.gsm, P.plant, P.vertragsende, P.provider)
                    .filter(P.vertragsende >= today, P.vertragsende <= in90)
                    .order_by(P.vertragsende).all())
    finally:
        db.close()
    return render_template("reports/stats.html", stats=stats, werke=werke,
                           ablauf=ablauf, active_tab="statistik")


@bp.route("/protokoll")
@login_required
def import_log():
    db = SessionLocal()
    try:
        rows = (db.query(ImportLog).order_by(ImportLog.zeitpunkt.desc())
                  .limit(500).all())
    finally:
        db.close()
    return render_template("reports/importlog.html", rows=rows, active_tab="protokoll")


@bp.route("/audit")
@require("admin")
def audit_log():
    db = SessionLocal()
    try:
        rows = (db.query(AuditLog).order_by(AuditLog.zeitpunkt.desc())
                  .limit(500).all())
    finally:
        db.close()
    return render_template("reports/audit.html", rows=rows, active_tab="audit")
