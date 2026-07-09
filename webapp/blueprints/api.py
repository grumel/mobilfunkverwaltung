"""
api.py – JSON-API für das React-Frontend (Phase 3).

Läuft parallel zur bestehenden serverseitig gerenderten Oberfläche. Session-
Cookie-Auth (wie bisher). CSRF ist für dieses Blueprint ausgenommen (in
webapp/__init__.py per csrf.exempt) – Session genügt fürs Erste; produktiv
später Token-/SameSite-Absicherung ergänzen.

Datumsfelder werden als ISO-Strings (YYYY-MM-DD) übertragen – so wie gespeichert.
"""

from datetime import date, timedelta

from flask import Blueprint, request, jsonify
from sqlalchemy import func, or_, select, case, and_

from webapp.db import SessionLocal
from webapp.models import Participant, User, Task
from webapp.security import current_user, can
from webapp import service as svc
from modules.auth import verify_password

bp = Blueprint("api", __name__, url_prefix="/api")

# Kurzfassung für Listen
LIST_FIELDS = ["id", "master_id", "gsm", "name", "plant", "konto", "tarif",
               "vertragsende", "bemerkung", "verified", "provider"]
# Vollständig für die Detail-/Bearbeiten-Ansicht
DETAIL_FIELDS = LIST_FIELDS + ["telefon", "sim_nummer", "rahmenvertrag",
               "startdatum", "vertragsbeginn", "kuendigung", "syno", "start_syno",
               "syno2", "start_syno2", "pruefung_grund", "created_at", "updated_at"]
# Über die API beschreibbar (master_id + Zeitstempel bleiben außen vor)
EDITABLE = ["gsm", "name", "plant", "konto", "telefon", "tarif", "sim_nummer",
            "rahmenvertrag", "startdatum", "vertragsbeginn", "vertragsende",
            "kuendigung", "syno", "start_syno", "syno2", "start_syno2",
            "bemerkung", "pruefung_grund", "provider"]
SEARCH_FIELDS = ["name", "gsm", "plant", "konto", "tarif", "bemerkung"]
DERIVED = {"offen", "unvollstaendig", "duplikate"}


def _dict(p, fields):
    return {f: getattr(p, f) for f in fields}


def _apply_view(db, view, q):
    """Query passend zur Ansicht (Provider-Slug oder abgeleitete Sicht)."""
    P = Participant
    if view in svc.SLUG_TO_PROVIDER:
        query = db.query(P).filter(func.coalesce(P.provider, "Vodafone") == svc.SLUG_TO_PROVIDER[view])
    elif view == "offen":
        query = db.query(P).filter(P.verified == 0)
    elif view == "unvollstaendig":
        query = db.query(P).filter(or_(P.gsm.is_(None), P.gsm == "",
                                       P.plant.is_(None), P.plant == "",
                                       P.konto.is_(None), P.konto == ""))
    elif view == "duplikate":
        norm = func.lower(func.trim(P.name))
        dup = (select(norm).where(P.name.isnot(None), P.name != "")
               .group_by(norm).having(func.count() > 1))
        query = db.query(P).filter(norm.in_(dup))
    else:
        query = db.query(P).filter(func.coalesce(P.provider, "Vodafone") == "Vodafone")
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(*[getattr(P, f).ilike(like) for f in SEARCH_FIELDS]))
    return query.order_by(P.name)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.active == 1).first()
    finally:
        db.close()
    if user and verify_password(password, user.password_hash):
        from flask import session
        session["user"] = {"id": user.id, "username": user.username, "role": user.role}
        return jsonify(user=session["user"])
    return jsonify(error="Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch."), 401


@bp.post("/logout")
def logout():
    from flask import session
    session.clear()
    return jsonify(ok=True)


@bp.get("/me")
def me():
    u = current_user()
    if not u:
        return jsonify(error="nicht angemeldet"), 401
    return jsonify(user=u)


# --------------------------------------------------------------------------- #
# Teilnehmer – Liste / Detail / Schreiben
# --------------------------------------------------------------------------- #
@bp.get("/participants")
def participants():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    view = request.args.get("view", "vodafone")
    db = SessionLocal()
    try:
        rows = _apply_view(db, view, request.args.get("q", "")).all()
        out = [_dict(r, LIST_FIELDS) for r in rows]
    finally:
        db.close()
    return jsonify(participants=out, total=len(out), view=view)


@bp.get("/participants/<int:pid>")
def participant_detail(pid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        return jsonify(participant=_dict(p, DETAIL_FIELDS))
    finally:
        db.close()


def _write_fields(p, data):
    for f in EDITABLE:
        if f in data:
            v = data[f]
            setattr(p, f, (v.strip() or None) if isinstance(v, str) else v)
    if "verified" in data:
        p.verified = 1 if data["verified"] else 0
    if not (p.provider or "").strip():
        p.provider = "Vodafone"


@bp.post("/participants")
def participant_create():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    data = request.get_json(silent=True) or {}
    gsm = (data.get("gsm") or "").strip()
    if gsm and not svc.is_valid_gsm(gsm):
        return jsonify(error="GSM-Nummer ungültig (10–15 Ziffern, optional +/00)."), 400
    db = SessionLocal()
    try:
        p = Participant(master_id=svc.next_master_id(db), created_at=svc.now_str(),
                        verified=1)
        _write_fields(p, data)
        p.updated_at = svc.now_str()
        db.add(p)
        db.flush()
        svc.log_import(db, "INSERT", f"ID={p.id} GSM={p.gsm} (API)", participant_id=p.id)
        svc.log_audit(db, current_user(), "INSERT", f"Teilnehmer '{p.name or p.id}' angelegt (API)",
                      table_name="participants", record_id=p.id)
        db.commit()
        return jsonify(participant=_dict(p, DETAIL_FIELDS)), 201
    finally:
        db.close()


@bp.put("/participants/<int:pid>")
def participant_update(pid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    data = request.get_json(silent=True) or {}
    gsm = (data.get("gsm") or "").strip()
    if "gsm" in data and gsm and not svc.is_valid_gsm(gsm):
        return jsonify(error="GSM-Nummer ungültig (10–15 Ziffern, optional +/00)."), 400
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        _write_fields(p, data)
        p.updated_at = svc.now_str()
        svc.log_import(db, "UPDATE", f"ID={pid} (API)", participant_id=pid)
        svc.log_audit(db, current_user(), "UPDATE", f"Teilnehmer '{p.name or pid}' geändert (API)",
                      table_name="participants", record_id=pid)
        db.commit()
        return jsonify(participant=_dict(p, DETAIL_FIELDS))
    finally:
        db.close()


@bp.post("/participants/<int:pid>/verify")
def participant_verify(pid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        p.verified = 0 if p.verified else 1
        p.updated_at = svc.now_str()
        svc.log_import(db, "VERIFIED", f"ID={pid} verified={p.verified} (API)", participant_id=pid)
        db.commit()
        return jsonify(id=pid, verified=p.verified)
    finally:
        db.close()


@bp.post("/participants/<int:pid>/move")
def participant_move(pid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    provider = (request.get_json(silent=True) or {}).get("provider", "")
    if provider not in svc.PROVIDERS:
        return jsonify(error="unbekannter Provider"), 400
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        old = p.provider or "Vodafone"
        p.provider = provider
        p.updated_at = svc.now_str()
        svc.log_import(db, "PROVIDER", f"ID={pid} {old} → {provider} (API)", participant_id=pid)
        svc.log_audit(db, current_user(), "PROVIDER", f"ID={pid} {old} → {provider} (API)",
                      table_name="participants", record_id=pid)
        db.commit()
        return jsonify(id=pid, provider=provider)
    finally:
        db.close()


@bp.delete("/participants/<int:pid>")
def participant_delete(pid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("delete"):
        return jsonify(error="Löschen erfordert Admin-Rechte"), 403
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        name = p.name or f"ID {pid}"
        db.delete(p)
        svc.log_import(db, "DELETE", f"ID={pid} {name} gelöscht (API)", participant_id=pid)
        svc.log_audit(db, current_user(), "DELETE", f"Teilnehmer '{name}' gelöscht (API)",
                      table_name="participants", record_id=pid)
        db.commit()
        return jsonify(ok=True, id=pid)
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Summary (Nav-Zähler + rote Zeilenmarkierung), Aufgaben, Statistik
# --------------------------------------------------------------------------- #
@bp.get("/summary")
def summary():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    db = SessionLocal()
    try:
        pids = [r[0] for r in db.query(Task.participant_id)
                .filter(Task.erledigt == 0, Task.participant_id.isnot(None)).all()]
        cnt = db.query(func.count()).select_from(Task).filter(Task.erledigt == 0).scalar() or 0
    finally:
        db.close()
    return jsonify(open_tasks=cnt, open_task_pids=pids)


TASK_FIELDS = ["id", "participant_id", "name", "gsm", "plant", "konto", "tarif",
               "kommentar", "erledigt", "created_by", "created_at", "done_at",
               "faellig_am", "prioritaet"]


@bp.get("/tasks")
def tasks():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    show = request.args.get("show", "offen")
    db = SessionLocal()
    try:
        qy = db.query(Task)
        if show != "alle":
            qy = qy.filter(Task.erledigt == 0)
        no_due = case((Task.faellig_am.is_(None), 1), (Task.faellig_am == "", 1), else_=0)
        rows = qy.order_by(Task.erledigt, Task.prioritaet.desc(), no_due,
                           Task.faellig_am, Task.created_at.desc()).all()
        out = [_dict(t, TASK_FIELDS) for t in rows]
    finally:
        db.close()
    return jsonify(tasks=out, total=len(out))


@bp.post("/participants/<int:pid>/tasks")
def task_create(pid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        t = Task(participant_id=p.id, name=p.name, gsm=p.gsm, plant=p.plant,
                 konto=p.konto, tarif=p.tarif,
                 kommentar=(data.get("kommentar") or "").strip() or None,
                 faellig_am=(data.get("faellig_am") or "").strip() or None,
                 prioritaet=1 if data.get("prioritaet") else 0,
                 created_by=(current_user() or {}).get("username"),
                 created_at=svc.now_str(), erledigt=0)
        db.add(t)
        svc.log_import(db, "AUFGABE", f"Aufgabe für ID={pid} (API)", participant_id=pid)
        db.flush()
        tid = t.id
        db.commit()
        return jsonify(id=tid), 201
    finally:
        db.close()


@bp.post("/tasks/<int:tid>/done")
def task_done(tid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    db = SessionLocal()
    try:
        t = db.get(Task, tid)
        if not t:
            return jsonify(error="nicht gefunden"), 404
        t.erledigt = 0 if t.erledigt else 1
        t.done_at = svc.now_str() if t.erledigt else None
        db.commit()
        return jsonify(id=tid, erledigt=t.erledigt)
    finally:
        db.close()


@bp.delete("/tasks/<int:tid>")
def task_delete(tid):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    db = SessionLocal()
    try:
        t = db.get(Task, tid)
        if t:
            db.delete(t)
            db.commit()
        return jsonify(ok=True, id=tid)
    finally:
        db.close()


@bp.get("/stats")
def stats():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    today = date.today().isoformat()
    in30 = (date.today() + timedelta(days=30)).isoformat()
    in60 = (date.today() + timedelta(days=60)).isoformat()
    in90 = (date.today() + timedelta(days=90)).isoformat()
    P = Participant
    db = SessionLocal()
    try:
        def cnt(*crit):
            qy = db.query(func.count()).select_from(P)
            for cc in crit:
                qy = qy.filter(cc)
            return qy.scalar() or 0
        has_syno = or_(and_(P.syno.isnot(None), P.syno != ""),
                       and_(P.syno2.isnot(None), P.syno2 != ""))
        tiles = {
            "total":        cnt(),
            "verified":     cnt(P.verified == 1),
            "zur_pruefung": cnt(P.verified == 0),
            "ohne_gsm":     cnt(or_(P.gsm.is_(None), P.gsm == "")),
            "mit_syno":     cnt(has_syno),
            "abgelaufen":   cnt(P.vertragsende.isnot(None), P.vertragsende != "", P.vertragsende < today),
            "ablauf_30":    cnt(P.vertragsende >= today, P.vertragsende <= in30),
            "ablauf_60":    cnt(P.vertragsende > in30, P.vertragsende <= in60),
            "ablauf_90":    cnt(P.vertragsende > in60, P.vertragsende <= in90),
        }
        werk = func.coalesce(P.plant, "(kein Werk)")
        werke = [{"werk": w, "n": n} for w, n in
                 db.query(werk, func.count()).group_by(werk).order_by(func.count().desc()).all()]
        ablauf = [{"name": n, "gsm": g, "plant": pl, "vertragsende": ve, "provider": pr}
                  for n, g, pl, ve, pr in
                  db.query(P.name, P.gsm, P.plant, P.vertragsende, P.provider)
                    .filter(P.vertragsende >= today, P.vertragsende <= in90)
                    .order_by(P.vertragsende).all()]
    finally:
        db.close()
    return jsonify(tiles=tiles, werke=werke, ablauf=ablauf)
