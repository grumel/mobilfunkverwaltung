"""
participants.py – Teilnehmer je Provider (alle Register), Live-Suche,
Bearbeiten/Neu, sowie Aktionen (verschieben, geprüft, löschen).
Schreibzugriffe sind rollen-geschützt und werden protokolliert (wie im Desktop).
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   Response, flash, abort)
from sqlalchemy import func, or_

from webapp.db import SessionLocal
from webapp.models import Participant
from webapp.security import login_required, require, current_user, can
from webapp import service as svc

bp = Blueprint("participants", __name__)

COLUMNS = [
    ("master_id",    "Nr."),
    ("gsm",          "GSM"),
    ("name",         "Name"),
    ("plant",        "Werk"),
    ("konto",        "Konto"),
    ("tarif",        "Tarif"),
    ("vertragsende", "Vtg.-Ende"),
    ("bemerkung",    "Bemerkung"),
]
SEARCH_FIELDS = ["name", "gsm", "plant", "konto", "tarif", "bemerkung"]


# --------------------------------------------------------------------------- #
# Listen je Provider
# --------------------------------------------------------------------------- #
def load_participants(provider: str, q: str = ""):
    db = SessionLocal()
    try:
        query = db.query(Participant).filter(
            func.coalesce(Participant.provider, "Vodafone") == provider)
        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            query = query.filter(or_(*[getattr(Participant, f).ilike(like)
                                       for f in SEARCH_FIELDS]))
        return query.order_by(Participant.name).all()
    finally:
        db.close()


def _provider_from_slug(slug: str) -> str:
    provider = svc.SLUG_TO_PROVIDER.get(slug)
    if provider is None:
        abort(404)
    return provider


@bp.route("/")
@login_required
def index():
    return provider_list("vodafone")


@bp.route("/p/<slug>")
@login_required
def provider_list(slug):
    provider = _provider_from_slug(slug)
    q = request.args.get("q", "")
    rows = load_participants(provider, q)
    return render_template("participants/list.html",
                           columns=COLUMNS, rows=rows, total=len(rows), q=q,
                           title=provider, provider=provider, slug=slug,
                           active_provider=slug,
                           rows_url=url_for("participants.provider_rows", slug=slug),
                           providers=svc.PROVIDERS)


@bp.route("/p/<slug>/rows")
@login_required
def provider_rows(slug):
    provider = _provider_from_slug(slug)
    rows = load_participants(provider, request.args.get("q", ""))
    html = render_template("participants/_rows.html", columns=COLUMNS, rows=rows,
                           slug=slug)
    return Response(html, mimetype="text/html")


# --------------------------------------------------------------------------- #
# Bearbeiten / Neu
# --------------------------------------------------------------------------- #
@bp.route("/participant/new", methods=["GET", "POST"])
@require("write")
def new_participant():
    if request.method == "POST":
        return _save_participant(None)
    return render_template("participants/edit.html",
                           p=None, fields=svc.FORM_FIELDS, providers=svc.PROVIDERS,
                           to_display_date=svc.to_display_date,
                           is_new=True, active_provider="")


@bp.route("/participant/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit_participant(pid):
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
    finally:
        db.close()
    if p is None:
        abort(404)
    if request.method == "POST":
        if not can("write"):
            abort(403)
        return _save_participant(pid)
    return render_template("participants/edit.html",
                           p=p, fields=svc.FORM_FIELDS, providers=svc.PROVIDERS,
                           to_display_date=svc.to_display_date,
                           is_new=False, active_provider="")


def _save_participant(pid):
    """Gemeinsame Speicherlogik für Neu und Bearbeiten."""
    form = request.form
    gsm = (form.get("gsm") or "").strip()
    if gsm and not svc.is_valid_gsm(gsm):
        flash("GSM-Nummer ungültig (erwartet 10–15 Ziffern, optional +/00).")
        # Formular erneut anzeigen (mit den eingegebenen Werten)
        return _rerender_edit(pid, form)

    db = SessionLocal()
    try:
        if pid is None:
            p = Participant(provider=form.get("provider") or "Vodafone",
                            master_id=svc.next_master_id(db),
                            created_at=svc.now_str())
            db.add(p)
            is_new = True
        else:
            p = db.get(Participant, pid)
            if p is None:
                abort(404)
            is_new = False

        # Textfelder / Datumsfelder aus FORM_FIELDS
        for key, _label, typ in svc.FORM_FIELDS:
            raw = form.get(key)
            value = svc.from_display_date(raw) if typ == "date" else (
                (raw or "").strip() or None)
            setattr(p, key, value)

        p.provider       = form.get("provider") or "Vodafone"
        p.bemerkung      = (form.get("bemerkung") or "").strip() or None
        p.pruefung_grund = (form.get("pruefung_grund") or "").strip() or None
        p.verified       = 1 if form.get("verified") == "on" else 0
        p.updated_at     = svc.now_str()

        db.flush()  # p.id verfügbar
        new_id = p.id
        svc.log_import(db, "INSERT" if is_new else "UPDATE",
                       f"ID={new_id} GSM={p.gsm} über Web",
                       participant_id=new_id)
        svc.log_audit(db, current_user(), "INSERT" if is_new else "UPDATE",
                      f"Teilnehmer '{p.name or new_id}' {'angelegt' if is_new else 'geändert'}",
                      table_name="participants", record_id=new_id)
        db.commit()
        flash(f"'{p.name or new_id}' gespeichert.")
        return redirect(url_for("participants.edit_participant", pid=new_id))
    except Exception as exc:
        db.rollback()
        flash(f"Fehler beim Speichern: {exc}")
        return _rerender_edit(pid, form)
    finally:
        db.close()


def _rerender_edit(pid, form):
    """Formular nach Fehler erneut anzeigen, mit den eingegebenen Werten."""
    class _Draft:  # leichtgewichtiger Platzhalter für die Template-Anzeige
        def __init__(self, data):
            self._d = dict(data)
        def __getattr__(self, name):
            return self._d.get(name)
    draft = _Draft(form)
    draft._d["id"] = pid  # für die Formular-Action beim erneuten Anzeigen
    return render_template("participants/edit.html",
                           p=draft, fields=svc.FORM_FIELDS, providers=svc.PROVIDERS,
                           to_display_date=lambda v: v or "",
                           is_new=(pid is None), active_provider="")


# --------------------------------------------------------------------------- #
# Aktionen (Kontextmenü) – POST, protokolliert, mit Meldung
# --------------------------------------------------------------------------- #
def _back(default_slug="vodafone"):
    return request.form.get("back") or url_for("participants.provider_list",
                                               slug=default_slug)


@bp.post("/participant/<int:pid>/move")
@require("write")
def move_participant(pid):
    provider = request.form.get("provider", "")
    if provider not in svc.PROVIDERS:
        abort(400)
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if p is not None:
            old = p.provider or "Vodafone"
            p.provider = provider
            p.updated_at = svc.now_str()
            svc.log_import(db, "PROVIDER", f"ID={pid} {old} → {provider}",
                           participant_id=pid)
            svc.log_audit(db, current_user(), "PROVIDER",
                          f"ID={pid} {old} → {provider}",
                          table_name="participants", record_id=pid)
            db.commit()
            flash(f"'{p.name or pid}' nach {provider} verschoben.")
    finally:
        db.close()
    return redirect(_back())


@bp.post("/participant/<int:pid>/verify")
@require("write")
def verify_participant(pid):
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if p is not None:
            new_val = 0 if p.verified else 1
            p.verified = new_val
            p.updated_at = svc.now_str()
            svc.log_import(db, "VERIFIED", f"ID={pid} verified={new_val} (Web)",
                           participant_id=pid)
            db.commit()
            flash(f"'{p.name or pid}' als {'geprüft' if new_val else 'offen'} markiert.")
    finally:
        db.close()
    return redirect(_back(svc.PROVIDER_TO_SLUG.get(request.form.get("cur_provider", ""), "vodafone")))


MERGE_FIELDS = ["gsm", "name", "plant", "konto", "telefon", "tarif", "sim_nummer",
                "rahmenvertrag", "startdatum", "vertragsbeginn", "vertragsende",
                "kuendigung", "syno", "start_syno", "syno2", "start_syno2",
                "bemerkung", "pruefung_grund"]


@bp.post("/participants/merge")
@require("write")
def merge():
    ids = [int(i) for i in request.form.getlist("ids") if i.isdigit()]
    back = request.form.get("back") or url_for("participants.index")
    if len(ids) < 2:
        flash("Bitte mindestens 2 Einträge auswählen.")
        return redirect(back)
    db = SessionLocal()
    try:
        parts = (db.query(Participant).filter(Participant.id.in_(ids))
                   .order_by(Participant.id).all())
        if len(parts) < 2:
            flash("Ausgewählte Einträge nicht gefunden.")
            return redirect(back)
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
        svc.log_import(db, "MERGE",
                       f"IDs {other_ids} in ID {target.id} zusammengeführt",
                       participant_id=target.id)
        svc.log_audit(db, current_user(), "MERGE",
                      f"{len(ids)} Einträge zusammengeführt in '{target.name or target.id}'",
                      table_name="participants", record_id=target.id)
        db.commit()
        flash(f"{len(ids)} Einträge zusammengeführt in '{target.name or target.id}'.")
    finally:
        db.close()
    return redirect(back)


@bp.post("/participant/<int:pid>/delete")
@require("delete")
def delete_participant(pid):
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if p is not None:
            name = p.name or f"ID {pid}"
            db.delete(p)
            svc.log_import(db, "DELETE", f"ID={pid} {name} gelöscht (Web)",
                           participant_id=pid)
            svc.log_audit(db, current_user(), "DELETE",
                          f"Teilnehmer '{name}' (ID={pid}) gelöscht",
                          table_name="participants", record_id=pid)
            db.commit()
            flash(f"'{name}' gelöscht.")
    finally:
        db.close()
    return redirect(_back())
