"""
api.py – JSON-API für das React-Frontend (Phase 3).

Läuft parallel zur bestehenden serverseitig gerenderten Oberfläche. Session-
Cookie-Auth (wie bisher). CSRF ist für dieses Blueprint ausgenommen (in
webapp/__init__.py per csrf.exempt) – Session genügt fürs Erste; produktiv
später Token-/SameSite-Absicherung ergänzen.

Datumsfelder werden als ISO-Strings (YYYY-MM-DD) übertragen – so wie gespeichert.
"""

import os
import tempfile
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify, session
from sqlalchemy import func, or_, select, case, and_
from werkzeug.utils import secure_filename

from pathlib import Path

from webapp.db import SessionLocal
from webapp.models import Participant, User, Task, ImportLog, AuditLog, UnmatchedDevice
from modules import vodafone_import, syno_import
from modules import database as ddb
from webapp import webconfig
from webapp import config as appconfig
from webapp.security import current_user, can
from webapp import service as svc
from modules.auth import verify_password, hash_password, ROLES

bp = Blueprint("api", __name__, url_prefix="/api")

# Kurzfassung für Listen
LIST_FIELDS = ["id", "master_id", "gsm", "name", "plant", "konto", "tarif",
               "sim_nummer", "vertragsbeginn", "vertragsende", "kuendigung",
               "rahmenvertrag", "syno", "start_syno", "bemerkung", "verified",
               "provider", "overhead"]
# Vollständig für die Detail-/Bearbeiten-Ansicht
DETAIL_FIELDS = LIST_FIELDS + ["telefon", "startdatum",
               "syno2", "start_syno2", "pruefung_grund", "created_at", "updated_at"]
# Über die API beschreibbar (master_id + Zeitstempel bleiben außen vor)
EDITABLE = ["gsm", "name", "plant", "konto", "telefon", "tarif", "sim_nummer",
            "rahmenvertrag", "startdatum", "vertragsbeginn", "vertragsende",
            "kuendigung", "syno", "start_syno", "syno2", "start_syno2",
            "bemerkung", "pruefung_grund", "provider"]
SEARCH_FIELDS = ["name", "gsm", "plant", "konto", "tarif", "bemerkung"]
DERIVED = {"offen", "unvollstaendig", "duplikate", "overhead"}


def _dict(p, fields):
    return {f: getattr(p, f) for f in fields}


def _apply_view(db, view, q):
    """Query passend zur Ansicht (Provider-Slug oder abgeleitete Sicht).

    Bei aktiver Suche (q gesetzt) wird reiterübergreifend über alle
    Teilnehmer gesucht — der Reiter-Filter entfällt dann bewusst.
    """
    P = Participant
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        return (db.query(P).filter(or_(*[getattr(P, f).ilike(like) for f in SEARCH_FIELDS]))
                .order_by(P.name))
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
    elif view == "overhead":
        query = db.query(P).filter(P.overhead == 1)
    elif view == "ohne_gsm":
        query = db.query(P).filter(or_(P.gsm.is_(None), P.gsm == ""))
    elif view == "ohne_name":
        query = db.query(P).filter(or_(P.name.is_(None), P.name == ""))
    elif view == "ohne_werk":
        query = db.query(P).filter(or_(P.plant.is_(None), P.plant == ""))
    elif view == "ohne_konto":
        query = db.query(P).filter(or_(P.konto.is_(None), P.konto == ""))
    elif view == "verified":
        query = db.query(P).filter(P.verified == 1)
    elif view == "mit_syno":
        query = db.query(P).filter(or_(and_(P.syno.isnot(None), P.syno != ""),
                                       and_(P.syno2.isnot(None), P.syno2 != "")))
    elif view in ("abgelaufen", "ablauf_30", "ablauf_60", "ablauf_90"):
        today = date.today().isoformat()
        in30 = (date.today() + timedelta(days=30)).isoformat()
        in60 = (date.today() + timedelta(days=60)).isoformat()
        in90 = (date.today() + timedelta(days=90)).isoformat()
        if view == "abgelaufen":
            query = db.query(P).filter(P.vertragsende.isnot(None), P.vertragsende != "",
                                       P.vertragsende < today)
        elif view == "ablauf_30":
            query = db.query(P).filter(P.vertragsende >= today, P.vertragsende <= in30)
        elif view == "ablauf_60":
            query = db.query(P).filter(P.vertragsende > in30, P.vertragsende <= in60)
        else:
            query = db.query(P).filter(P.vertragsende > in60, P.vertragsende <= in90)
    elif view == "alle":
        query = db.query(P)
    else:
        query = db.query(P).filter(func.coalesce(P.provider, "Vodafone") == "Vodafone")
    return query.order_by(P.name)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
# Einfache Brute-Force-Bremse: pro Client-IP zählen; nach zu vielen
# Fehlversuchen innerhalb des Zeitfensters wird kurz gesperrt (in-memory).
_LOGIN_MAX = 8
_LOGIN_WINDOW = 300      # Sekunden, in denen Fehlversuche zählen
_login_fails = {}        # ip -> (anzahl, erster_versuch_ts)


def _login_blocked(ip):
    import time
    count, first = _login_fails.get(ip, (0, 0.0))
    if time.time() - first > _LOGIN_WINDOW:
        return False
    return count >= _LOGIN_MAX


def _login_note_fail(ip):
    import time
    now = time.time()
    count, first = _login_fails.get(ip, (0, now))
    if now - first > _LOGIN_WINDOW:
        count, first = 0, now
    _login_fails[ip] = (count + 1, first)


@bp.post("/login")
def login():
    from flask import session
    ip = request.remote_addr or "?"
    if _login_blocked(ip):
        return jsonify(error="Zu viele Fehlversuche – bitte einige Minuten warten."), 429

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.active == 1).first()
        if user and verify_password(password, user.password_hash):
            _login_fails.pop(ip, None)
            user.last_login = svc.now_str()
            svc.log_audit(db, {"id": user.id, "username": user.username},
                          "LOGIN", f"Anmeldung erfolgreich (IP {ip})")
            db.commit()
            force = bool(user.force_pw_change)
            session.clear()                    # Session-Fixation vermeiden
            session["user"] = {"id": user.id, "username": user.username, "role": user.role}
            return jsonify(user=session["user"], force_pw_change=force)
    finally:
        db.close()

    _login_note_fail(ip)
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
    db = SessionLocal()
    try:
        row = db.get(User, u["id"])
        force = bool(row.force_pw_change) if row else False
    finally:
        db.close()
    return jsonify(user=u, force_pw_change=force)


@bp.post("/me/password")
def me_change_password():
    """Eigenes Passwort ändern (jeder angemeldete Benutzer)."""
    u = current_user()
    if not u:
        return jsonify(error="nicht angemeldet"), 401
    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new = data.get("new_password") or ""
    if len(new) < 6:
        return jsonify(error="Neues Passwort: mindestens 6 Zeichen."), 400
    db = SessionLocal()
    try:
        row = db.get(User, u["id"])
        if not row or not verify_password(current, row.password_hash):
            return jsonify(error="Aktuelles Passwort ist falsch."), 403
        row.password_hash = hash_password(new)
        row.force_pw_change = 0
        svc.log_audit(db, u, "SELF_PASSWORD", "Eigenes Passwort geändert (API)",
                      table_name="users", record_id=row.id)
        db.commit()
        return jsonify(ok=True)
    finally:
        db.close()


_VERSION_CACHE = None


def app_version():
    """Fortlaufende Versionsnummer = Anzahl Git-Commits (+ Kurz-Hash).

    Wird beim ersten Aufruf ermittelt und zwischengespeichert. Ohne Git
    (z. B. bei einer Kopie ohne .git) bleibt sie leer."""
    global _VERSION_CACHE
    if _VERSION_CACHE is not None:
        return _VERSION_CACHE
    build = commit = None
    try:
        import subprocess
        root = str(Path(__file__).resolve().parents[2])
        run = lambda *a: subprocess.check_output(["git", "-C", root, *a],
                                                 text=True, stderr=subprocess.DEVNULL).strip()
        build = run("rev-list", "--count", "HEAD")
        commit = run("rev-parse", "--short", "HEAD")
    except Exception:
        pass
    _VERSION_CACHE = {"build": build, "commit": commit}
    return _VERSION_CACHE


@bp.get("/version")
def version():
    # Öffentlich (auch vor Login sichtbar, z. B. auf der Anmeldeseite).
    return jsonify(app_version())


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


@bp.get("/werk-konto")
def werk_konto():
    """Feste Werk↔Konto-Paare aus den vorhandenen Daten (häufigste Zuordnung
    je Richtung). Das Frontend füllt damit beim Bearbeiten/Neuvertrag das
    jeweils andere Feld automatisch aus."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    from collections import Counter
    db = SessionLocal()
    try:
        pairs = (db.query(Participant.plant, Participant.konto)
                 .filter(Participant.plant.isnot(None), Participant.plant != "",
                         Participant.konto.isnot(None), Participant.konto != "").all())
    finally:
        db.close()
    w_count, k_count = {}, {}
    for plant, konto in pairs:
        plant, konto = plant.strip(), konto.strip()
        if not plant or not konto:
            continue
        w_count.setdefault(plant, Counter())[konto] += 1
        k_count.setdefault(konto, Counter())[plant] += 1
    werk_to_konto = {w: c.most_common(1)[0][0] for w, c in w_count.items()}
    konto_to_werk = {k: c.most_common(1)[0][0] for k, c in k_count.items()}
    return jsonify(werk_to_konto=werk_to_konto, konto_to_werk=konto_to_werk)


NEUVERTRAG_TO = "nicole.dieckmann@zinxs.com"


def _documents_dir():
    """Gemeinsamer Ordner für erzeugte Schreiben (Kündigung, Rücknahme,
    Neuvertrag). Entspricht dem Ausgabeordner der Kündigungen."""
    from modules import kuendigung as kmod
    kmod.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return kmod.OUTPUT_DIR


@bp.post("/neuvertrag")
def neuvertrag_create():
    """Neuvertrag bestellen: Teilnehmer anlegen (ungeprüft) und Mailtext
    zurückgeben (der Nutzer versendet ihn selbst in Outlook)."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    werk = (data.get("werk") or "").strip()
    konto = (data.get("konto") or "").strip()
    tarif = (data.get("tarif") or "").strip()
    if not name or not werk or not tarif:
        return jsonify(error="Bitte Name, Werk und Tarif angeben."), 400

    heute = date.today().strftime("%d.%m.%Y")
    db = SessionLocal()
    try:
        p = Participant(master_id=svc.next_master_id(db), created_at=svc.now_str(),
                        updated_at=svc.now_str(), name=name, plant=werk, konto=konto,
                        tarif=tarif, verified=0, provider="Vodafone",
                        pruefung_grund=f"Neuvertrag - Mail an Nicole am {heute}",
                        bemerkung="Neuvertrag bestellt, noch nicht bei Vodafone aktiv")
        db.add(p)
        db.flush()
        svc.log_import(db, "NEUVERTRAG",
                       f"ID={p.id} Name={name} Werk={werk} Konto={konto} Tarif={tarif} (API)",
                       participant_id=p.id)
        svc.log_audit(db, current_user(), "NEUVERTRAG",
                      f"Neuvertrag '{name}' angelegt (API)",
                      table_name="participants", record_id=p.id)
        db.commit()
        pid = p.id
    finally:
        db.close()

    subject = f"NV - {name}"
    body = (
        "Hallo liebe Nicole,\n\n"
        f"ich hätte gerne einen Neuvertrag für {name}.\n\n"
        f"Werk:  {werk}\n"
        f"Konto: {konto}\n"
        f"Tarif: {tarif}\n\n"
        "Magst du dich bitte um die Erstellung kümmern?\n\n"
        "Danke dir und ganz liebe Grüße\n"
        "Holger"
    )
    # Neuvertrag lokal als Textdatei ablegen (wie Kündigung/Rücknahme als PDF).
    filename = None
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = secure_filename(f"neuvertrag_{name}_{ts}.txt") or f"neuvertrag_{ts}.txt"
        fpath = _documents_dir() / fname
        fpath.write_text(f"An: {NEUVERTRAG_TO}\nBetreff: {subject}\n\n{body}\n", encoding="utf-8")
        filename = fpath.name
    except Exception:
        pass
    return jsonify(id=pid, to=NEUVERTRAG_TO, subject=subject, body=body, file=filename), 201


@bp.post("/participants/<int:pid>/kuendigung")
def participant_kuendigung(pid):
    """Kündigung/Rücknahme: Word-Vorlage füllen → PDF (Word bzw. LibreOffice)
    → Datei zum Download + Mailtext zurückgeben. Vorlagen liegen unter
    <DATA_DIR>/Dokumente/vorlage_kuendigung.docx bzw. vorlage_ruecknahme.docx."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    kind = (request.get_json(silent=True) or {}).get("kind", "kuendigung")
    if kind not in ("kuendigung", "ruecknahme"):
        return jsonify(error="unbekannter Schreiben-Typ"), 400

    from modules import kuendigung as kmod
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        gsm = (p.gsm or "").strip()
    finally:
        db.close()

    try:
        docx_path = kmod.generate_letter(kind, gsm)
        # Windows nimmt das lokal installierte Word, Linux LibreOffice.
        pdf_path = kmod.convert_to_pdf_auto(docx_path)
    except FileNotFoundError as e:
        return jsonify(error=f"Vorlage fehlt: {e}"), 400
    except Exception as e:
        return jsonify(error=f"PDF-Erzeugung fehlgeschlagen: {e}"), 500

    db = SessionLocal()
    try:
        aktion = "KUENDIGUNG" if kind == "kuendigung" else "RUECKNAHME"
        svc.log_import(db, aktion, f"ID={pid} GSM={gsm} PDF={pdf_path.name} (API)",
                       participant_id=pid)
        svc.log_audit(db, current_user(), aktion,
                      f"{aktion.title()} für GSM {gsm or '-'} erzeugt (API)",
                      table_name="participants", record_id=pid)
        db.commit()
    finally:
        db.close()

    gsm_txt = gsm or "unbekannt"
    return jsonify(file=pdf_path.name, to=kmod.DEFAULT_TO,
                   subject=kmod.SUBJECTS[kind].format(gsm=gsm_txt),
                   body=kmod.BODIES[kind].format(gsm=gsm_txt))


@bp.get("/kuendigung/<path:name>")
def kuendigung_download(name):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    from flask import send_from_directory
    from modules import kuendigung as kmod
    safe = os.path.basename(name)          # Path-Traversal verhindern
    if not safe.lower().endswith(".pdf"):
        return jsonify(error="ungültig"), 400
    outdir = kmod.OUTPUT_DIR
    if not (outdir / safe).exists():
        return jsonify(error="nicht gefunden"), 404
    return send_from_directory(str(outdir), safe, as_attachment=True,
                               mimetype="application/pdf")


@bp.get("/documents")
def documents_list():
    """Liste der lokal gespeicherten Schreiben (Kündigung/Rücknahme-PDFs,
    Neuvertrag-Texte) – der „Dokumente-Ordner" als Web-Ansicht."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    outdir = _documents_dir()
    files = []
    for f in outdir.iterdir():
        if f.is_file() and f.suffix.lower() != ".docx":   # .docx-Vorstufen ausblenden
            st = f.stat()
            files.append({"name": f.name, "size": st.st_size,
                          "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
    files.sort(key=lambda d: d["modified"], reverse=True)
    return jsonify(documents=files, folder=str(outdir))


@bp.get("/documents/<path:name>")
def document_download(name):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    from flask import send_from_directory
    safe = os.path.basename(name)          # Path-Traversal verhindern
    outdir = _documents_dir()
    if not (outdir / safe).is_file():
        return jsonify(error="nicht gefunden"), 404
    return send_from_directory(str(outdir), safe, as_attachment=True)


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


@bp.post("/participants/<int:pid>/overhead")
def participant_overhead(pid):
    """Overhead-Markierung umschalten. Der Provider (Original-Tab) bleibt
    unverändert – der Teilnehmer erscheint zusätzlich im Overhead-Filter."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if not p:
            return jsonify(error="nicht gefunden"), 404
        p.overhead = 0 if p.overhead else 1
        p.updated_at = svc.now_str()
        svc.log_import(db, "OVERHEAD", f"ID={pid} overhead={p.overhead} (API)", participant_id=pid)
        svc.log_audit(db, current_user(), "OVERHEAD",
                      f"ID={pid} overhead={p.overhead} (API)",
                      table_name="participants", record_id=pid)
        db.commit()
        return jsonify(id=pid, overhead=p.overhead)
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


MERGE_FIELDS = ["gsm", "name", "plant", "konto", "telefon", "tarif", "sim_nummer",
                "rahmenvertrag", "startdatum", "vertragsbeginn", "vertragsende",
                "kuendigung", "syno", "start_syno", "syno2", "start_syno2",
                "bemerkung", "pruefung_grund"]


@bp.post("/participants/merge")
def participant_merge():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    ids = [int(i) for i in (request.get_json(silent=True) or {}).get("ids", [])
           if isinstance(i, int) or (isinstance(i, str) and i.isdigit())]
    if len(ids) < 2:
        return jsonify(error="Bitte mindestens 2 Einträge auswählen."), 400
    db = SessionLocal()
    try:
        parts = (db.query(Participant).filter(Participant.id.in_(ids))
                   .order_by(Participant.id).all())
        if len(parts) < 2:
            return jsonify(error="Ausgewählte Einträge nicht gefunden."), 400
        target, others = parts[0], parts[1:]
        # Werte für leere Zielfelder sammeln, solange die anderen noch existieren
        fill = {}
        for f in MERGE_FIELDS:
            if not (getattr(target, f) or "").strip():
                for o in others:
                    val = getattr(o, f)
                    if val not in (None, "") and str(val).strip():
                        fill[f] = val
                        break
        other_ids = [o.id for o in others]
        # Erst die anderen löschen (flush), damit eindeutige Werte (z. B. GSM) frei werden
        for o in others:
            db.delete(o)
        db.flush()
        for f, val in fill.items():
            setattr(target, f, val)
        target.updated_at = svc.now_str()
        svc.log_import(db, "MERGE", f"IDs {other_ids} in ID {target.id} zusammengeführt (API)",
                       participant_id=target.id)
        svc.log_audit(db, current_user(), "MERGE",
                      f"{len(ids)} Einträge zusammengeführt in '{target.name or target.id}' (API)",
                      table_name="participants", record_id=target.id)
        db.commit()
        return jsonify(id=target.id, merged_count=len(ids),
                       participant=_dict(target, DETAIL_FIELDS))
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


@bp.get("/dataquality")
def dataquality():
    """Kennzahlen zur Datenqualität: fehlende Pflichtfelder, Duplikate,
    ungeprüfte Einträge, verwaiste Syno-Geräte + ein Sauberkeits-Prozentwert."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    P = Participant
    db = SessionLocal()
    try:
        def cnt(*crit):
            qy = db.query(func.count()).select_from(P)
            for cc in crit:
                qy = qy.filter(cc)
            return qy.scalar() or 0
        empty = lambda col: or_(col.is_(None), func.trim(col) == "")
        total = cnt()
        # Duplikate: Teilnehmer, die zu einer mehrfach vorkommenden Namensgruppe gehören
        norm = func.lower(func.trim(P.name))
        dupsub = (select(norm).where(P.name.isnot(None), P.name != "")
                  .group_by(norm).having(func.count() > 1))
        duplikate = cnt(norm.in_(dupsub))
        # Vollständig = GSM, Name, Werk und Konto vorhanden
        vollstaendig = cnt(func.trim(func.coalesce(P.gsm, "")) != "",
                           func.trim(func.coalesce(P.name, "")) != "",
                           func.trim(func.coalesce(P.plant, "")) != "",
                           func.trim(func.coalesce(P.konto, "")) != "")
        verwaiste = db.query(func.count()).select_from(UnmatchedDevice).scalar() or 0
        metrics = {
            "total":        total,
            "ohne_gsm":     cnt(empty(P.gsm)),
            "ohne_name":    cnt(empty(P.name)),
            "ohne_werk":    cnt(empty(P.plant)),
            "ohne_konto":   cnt(empty(P.konto)),
            "ungeprueft":   cnt(P.verified == 0),
            "duplikate":    duplikate,
            "verwaiste_geraete": verwaiste,
            "vollstaendig": vollstaendig,
        }
    finally:
        db.close()
    metrics["sauberkeit"] = round(100 * vollstaendig / total, 1) if total else 100.0
    return jsonify(metrics=metrics)


@bp.get("/unmatched-devices")
def unmatched_devices():
    """Verwaiste Syno-Geräte ('Nicht zugeordnet') – Zeilen ohne Teilnehmer."""
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    fields = ["id", "quelle", "gsm", "benutzer", "geraet", "startdatum", "importdatum"]
    db = SessionLocal()
    try:
        rows = db.query(UnmatchedDevice).order_by(UnmatchedDevice.id.desc()).all()
        out = [_dict(r, fields) for r in rows]
    finally:
        db.close()
    return jsonify(devices=out)


IMPORTLOG_FIELDS = ["id", "zeitpunkt", "quelle", "aktion", "details", "participant_id"]
AUDITLOG_FIELDS = ["id", "zeitpunkt", "user_id", "username", "aktion", "details",
                   "table_name", "record_id"]


@bp.get("/logs/import")
def logs_import():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    db = SessionLocal()
    try:
        rows = db.query(ImportLog).order_by(ImportLog.zeitpunkt.desc()).limit(500).all()
        out = [_dict(r, IMPORTLOG_FIELDS) for r in rows]
    finally:
        db.close()
    return jsonify(logs=out, total=len(out))


@bp.get("/logs/audit")
def logs_audit():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("admin"):
        return jsonify(error="keine Berechtigung"), 403
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).order_by(AuditLog.zeitpunkt.desc()).limit(500).all()
        out = [_dict(r, AUDITLOG_FIELDS) for r in rows]
    finally:
        db.close()
    return jsonify(logs=out, total=len(out))


# --------------------------------------------------------------------------- #
# Import (nur Admin) – wiederverwendet modules.vodafone_import / syno_import
# --------------------------------------------------------------------------- #
def _require_admin():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("admin"):
        return jsonify(error="keine Berechtigung"), 403
    return None


def _import_db_module():
    """None (= modules.database/SQLite, unverändert) solange DATABASE_URL auf
    SQLite zeigt; sonst der SQLAlchemy-Adapter (z. B. PostgreSQL) – siehe
    webapp/import_adapter.py. So landen Excel-Importe immer in der tatsächlich
    konfigurierten Datenbank, nicht versehentlich in einer lokalen SQLite-Datei."""
    if appconfig.DATABASE_URL.startswith("sqlite"):
        return None
    from webapp import import_adapter
    return import_adapter


def _save_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return None, None, (jsonify(error="Bitte eine Excel-Datei auswählen."), 400)
    if not f.filename.lower().endswith((".xlsx", ".xls")):
        return None, None, (jsonify(error="Nur Excel-Dateien (.xlsx/.xls) werden unterstützt."), 400)
    fd, path = tempfile.mkstemp(suffix="_" + secure_filename(f.filename))
    os.close(fd)
    f.save(path)
    return path, f.filename, None


@bp.post("/import/vodafone/preview")
def import_vodafone_preview():
    err = _require_admin()
    if err:
        return err
    path, filename, err = _save_upload()
    if err:
        return err
    try:
        preview = vodafone_import.run_vodafone_import(
            path, dry_run=True, db_module=_import_db_module())
    except Exception as exc:
        try: os.unlink(path)
        except OSError: pass
        return jsonify(error=f"Importfehler: {exc}"), 400
    session["vodafone_import_path"] = path
    session["vodafone_import_name"] = filename
    return jsonify(preview=preview, filename=filename)


@bp.post("/import/vodafone/confirm")
def import_vodafone_confirm():
    err = _require_admin()
    if err:
        return err
    path = session.pop("vodafone_import_path", None)
    filename = session.pop("vodafone_import_name", "?")
    if not path or not os.path.exists(path):
        return jsonify(error="Import-Datei nicht mehr vorhanden – bitte erneut hochladen."), 400
    db_module = _import_db_module()
    try:
        if db_module is None:      # SQLite: Backup wie bisher
            ddb.create_backup()
        result = vodafone_import.run_vodafone_import(path, db_module=db_module)
    except Exception as exc:
        return jsonify(error=f"Import fehlgeschlagen: {exc}"), 400
    finally:
        try: os.unlink(path)
        except OSError: pass
    return jsonify(result=result, filename=filename)


@bp.post("/import/syno")
def import_syno():
    err = _require_admin()
    if err:
        return err
    path, filename, err = _save_upload()
    if err:
        return err
    create_missing = (request.form.get("create_missing") or "").lower() in ("1", "true", "on", "yes")
    db_module = _import_db_module()
    try:
        if db_module is None:      # SQLite: Backup wie bisher
            ddb.create_backup()
        result = syno_import.run_syno_import(path, db_module=db_module,
                                             create_missing=create_missing)
    except Exception as exc:
        return jsonify(error=f"Import fehlgeschlagen: {exc}"), 400
    finally:
        try: os.unlink(path)
        except OSError: pass
    return jsonify(result=result, filename=filename)


SYNO_DIR_NAME = "SynoDateien"


def _syno_dir():
    from modules.paths import DATA_DIR
    d = Path(DATA_DIR) / SYNO_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


@bp.post("/syno/enrich")
def syno_enrich_upload():
    """Syno-Datei VOR dem Import mit DB-Daten anreichern (GSM/Namen korrigieren).
    Original wird gespeichert, eine angereicherte Kopie erzeugt, alles geloggt."""
    err = _require_admin()
    if err:
        return err
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Bitte eine Excel-Datei auswählen."), 400
    if not f.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify(error="Nur Excel-Dateien (.xlsx/.xls) werden unterstützt."), 400

    from modules import syno_enrich
    outdir = _syno_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    original = outdir / f"{ts}_{secure_filename(f.filename)}"
    f.save(str(original))          # Original hochgeladen und gespeichert
    try:
        summary = syno_enrich.run_syno_enrich(original)
    except Exception as exc:
        return jsonify(error=f"Anreicherung fehlgeschlagen: {exc}"), 400
    enriched = Path(summary["out_path"])

    db = SessionLocal()
    try:
        details = (f"Original={original.name} → {enriched.name}; "
                   f"GSM ergänzt={summary['fixed_gsm']}, GSM korrigiert={summary['changed_gsm']}, "
                   f"Namen ergänzt={summary['fixed_name']}, ohne Treffer={summary['no_match']}")
        svc.log_import(db, "SYNO_ANREICHERN", details + " (API)")
        svc.log_audit(db, current_user(), "SYNO_ANREICHERN", details)
        db.commit()
    finally:
        db.close()

    return jsonify(original=original.name, enriched=enriched.name,
                   summary={k: summary[k] for k in
                            ("fixed_gsm", "changed_gsm", "fixed_name", "no_match")})


@bp.get("/syno/file/<path:name>")
def syno_file_download(name):
    err = _require_admin()
    if err:
        return err
    from flask import send_from_directory
    safe = os.path.basename(name)
    if not safe.lower().endswith((".xlsx", ".xls")):
        return jsonify(error="ungültig"), 400
    outdir = _syno_dir()
    if not (outdir / safe).exists():
        return jsonify(error="nicht gefunden"), 404
    return send_from_directory(str(outdir), safe, as_attachment=True)


# --------------------------------------------------------------------------- #
# Einzel-Abgleich (im Bearbeiten-Dialog): Felder EINES Teilnehmers aus einer
# Export-Datei holen, ohne etwas zu speichern. Der Nutzer prüft und speichert
# dann selbst. Braucht Schreibrechte (nicht Admin – wie im Desktop-Editor).
# --------------------------------------------------------------------------- #
@bp.post("/match/vodafone")
def match_vodafone():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    gsm = (request.form.get("gsm") or "").strip()
    if not gsm:
        return jsonify(error="Bitte zuerst eine GSM-Nummer eingeben."), 400
    path, filename, err = _save_upload()
    if err:
        return err
    try:
        result = vodafone_import.find_by_gsm(path, gsm)
    except Exception as exc:
        return jsonify(error=f"Datei konnte nicht gelesen werden: {exc}"), 400
    finally:
        try: os.unlink(path)
        except OSError: pass
    return jsonify(match=result, filename=filename)


@bp.post("/match/syno")
def match_syno():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    gsm = (request.form.get("gsm") or "").strip()
    name = (request.form.get("name") or "").strip()
    if not gsm and not name:
        return jsonify(error="Bitte zuerst eine GSM-Nummer oder einen Namen eingeben."), 400
    path, filename, err = _save_upload()
    if err:
        return err
    try:
        result = syno_import.find_by_gsm_or_name(path, gsm, name)
    except Exception as exc:
        return jsonify(error=f"Datei konnte nicht gelesen werden: {exc}"), 400
    finally:
        try: os.unlink(path)
        except OSError: pass
    return jsonify(match=result, filename=filename)


# --------------------------------------------------------------------------- #
# Einstellungen (nur Admin) – Datenbankpfad (Programm/DB getrennt)
# --------------------------------------------------------------------------- #
@bp.get("/settings")
def settings_get():
    err = _require_admin()
    if err:
        return err
    cfg = webconfig.load()
    return jsonify(
        db_path=cfg.get("db_path", ""),
        database_url=cfg.get("database_url", ""),
        current_url=appconfig.DATABASE_URL,
        default_path=appconfig.DEFAULT_DB_PATH,
        config_file=str(webconfig.config_file()),
        env_override=bool(os.environ.get("DATABASE_URL")),
    )


@bp.put("/settings")
def settings_put():
    err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    db_path = (data.get("db_path") or "").strip()
    database_url = (data.get("database_url") or "").strip()
    cfg = webconfig.load()
    newcfg = dict(cfg)
    warning = None
    if database_url:
        newcfg["database_url"] = database_url
        newcfg.pop("db_path", None)
        message = "Volle DATABASE_URL gespeichert."
    elif db_path:
        p = Path(db_path)
        newcfg["db_path"] = str(p)
        newcfg.pop("database_url", None)
        if not p.exists():
            warning = "Achtung: Die angegebene Datei existiert (noch) nicht – bitte Pfad prüfen."
        message = "Datenbankpfad gespeichert."
    else:
        newcfg.pop("db_path", None)
        newcfg.pop("database_url", None)
        message = "Auf Standard-Datenbank zurückgesetzt."
    webconfig.save(newcfg)
    return jsonify(ok=True, message=message, warning=warning,
                   note="Bitte die Web-App neu starten, damit die Änderung aktiv wird.")


# --------------------------------------------------------------------------- #
# Benutzerverwaltung (nur Admin)
# --------------------------------------------------------------------------- #
USER_FIELDS = ["id", "username", "role", "active", "last_login",
               "created_at", "windows_login"]


@bp.get("/users")
def users_list():
    err = _require_admin()
    if err:
        return err
    db = SessionLocal()
    try:
        rows = db.query(User).order_by(User.username).all()
        return jsonify(users=[_dict(u, USER_FIELDS) for u in rows])
    finally:
        db.close()


@bp.post("/users")
def user_create():
    err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "read").strip()
    active = 1 if data.get("active", True) else 0
    windows_login = (data.get("windows_login") or "").strip() or None

    if not username:
        return jsonify(error="Benutzername darf nicht leer sein."), 400
    if role not in ROLES:
        return jsonify(error="Ungültige Rolle."), 400
    # Passwort ist Pflicht, außer es wird ein Windows-Login hinterlegt (SSO)
    if password:
        if len(password) < 6:
            return jsonify(error="Passwort: mindestens 6 Zeichen."), 400
        pw_hash = hash_password(password)
    elif windows_login:
        pw_hash = hash_password(os.urandom(24).hex())  # unbenutzbares Zufallspasswort
    else:
        return jsonify(error="Passwort (min. 6 Zeichen) oder Windows-Login erforderlich."), 400

    db = SessionLocal()
    try:
        if db.query(User).filter(func.lower(User.username) == username.lower()).first():
            return jsonify(error="Benutzername bereits vergeben."), 409
        u = User(username=username, password_hash=pw_hash, role=role, active=active,
                 force_pw_change=0, windows_login=windows_login, created_at=svc.now_str())
        db.add(u)
        db.flush()
        svc.log_audit(db, current_user(), "USER_CREATE",
                      f"Neuer Benutzer '{username}' Rolle={role} "
                      f"Windows-Login={windows_login or '-'} (API)",
                      table_name="users", record_id=u.id)
        db.commit()
        return jsonify(user=_dict(u, USER_FIELDS)), 201
    finally:
        db.close()


@bp.put("/users/<int:uid>")
def user_update(uid):
    err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        u = db.get(User, uid)
        if not u:
            return jsonify(error="nicht gefunden"), 404

        me = current_user()
        if "username" in data:
            username = (data.get("username") or "").strip()
            if not username:
                return jsonify(error="Benutzername darf nicht leer sein."), 400
            clash = db.query(User).filter(func.lower(User.username) == username.lower(),
                                          User.id != uid).first()
            if clash:
                return jsonify(error="Benutzername bereits vergeben."), 409
            u.username = username
        if "role" in data:
            role = (data.get("role") or "").strip()
            if role not in ROLES:
                return jsonify(error="Ungültige Rolle."), 400
            if u.id == me["id"] and role != "admin":
                return jsonify(error="Die eigene Admin-Rolle kann nicht entzogen werden."), 400
            u.role = role
        if "active" in data:
            active = 1 if data.get("active") else 0
            if u.id == me["id"] and active == 0:
                return jsonify(error="Das eigene Konto kann nicht deaktiviert werden."), 400
            u.active = active
        if "windows_login" in data:
            u.windows_login = (data.get("windows_login") or "").strip() or None

        svc.log_audit(db, me, "USER_EDIT",
                      f"Benutzer '{u.username}' geändert Rolle={u.role} aktiv={u.active} (API)",
                      table_name="users", record_id=u.id)
        db.commit()
        return jsonify(user=_dict(u, USER_FIELDS))
    finally:
        db.close()


@bp.post("/users/<int:uid>/password")
def user_set_password(uid):
    err = _require_admin()
    if err:
        return err
    password = (request.get_json(silent=True) or {}).get("password") or ""
    if len(password) < 6:
        return jsonify(error="Passwort: mindestens 6 Zeichen."), 400
    db = SessionLocal()
    try:
        u = db.get(User, uid)
        if not u:
            return jsonify(error="nicht gefunden"), 404
        u.password_hash = hash_password(password)
        u.force_pw_change = 0
        svc.log_audit(db, current_user(), "USER_PASSWORD",
                      f"Passwort für '{u.username}' zurückgesetzt (API)",
                      table_name="users", record_id=u.id)
        db.commit()
        return jsonify(ok=True)
    finally:
        db.close()


@bp.delete("/users/<int:uid>")
def user_delete(uid):
    err = _require_admin()
    if err:
        return err
    db = SessionLocal()
    try:
        u = db.get(User, uid)
        if not u:
            return jsonify(error="nicht gefunden"), 404
        if u.id == current_user()["id"]:
            return jsonify(error="Das eigene Konto kann nicht gelöscht werden."), 400
        name = u.username
        svc.log_audit(db, current_user(), "USER_DELETE",
                      f"Benutzer '{name}' gelöscht (API)",
                      table_name="users", record_id=uid)
        db.delete(u)
        db.commit()
        return jsonify(ok=True)
    finally:
        db.close()
