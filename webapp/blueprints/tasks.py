"""
tasks.py – Aufgabenverwaltung (Web). Aufgaben werden aus einem Teilnehmer
angelegt (übernehmen Name/GSM/Werk/Konto/Tarif), können erledigt/gelöscht werden.
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort)
from sqlalchemy import case

from webapp.db import SessionLocal
from webapp.models import Task, Participant
from webapp.security import login_required, require, current_user
from webapp import service as svc

bp = Blueprint("tasks", __name__)


@bp.route("/aufgaben")
@login_required
def list_tasks():
    show = request.args.get("show", "offen")
    db = SessionLocal()
    try:
        q = db.query(Task)
        if show != "alle":
            q = q.filter(Task.erledigt == 0)
        # Offen zuerst, dann hohe Priorität, dann Fälligkeit (leere zuletzt)
        no_due = case((Task.faellig_am.is_(None), 1), (Task.faellig_am == "", 1), else_=0)
        tasks = q.order_by(Task.erledigt, Task.prioritaet.desc(), no_due,
                           Task.faellig_am, Task.created_at.desc()).all()
    finally:
        db.close()
    return render_template("tasks/list.html", tasks=tasks, show=show,
                           active_tab="aufgaben", today=svc.now_str()[:10])


@bp.route("/participant/<int:pid>/task/new", methods=["GET", "POST"])
@require("write")
def new_task(pid):
    db = SessionLocal()
    try:
        p = db.get(Participant, pid)
        if p is None:
            abort(404)
        if request.method == "POST":
            t = Task(participant_id=p.id, name=p.name, gsm=p.gsm, plant=p.plant,
                     konto=p.konto, tarif=p.tarif,
                     kommentar=(request.form.get("kommentar") or "").strip() or None,
                     faellig_am=svc.from_display_date(request.form.get("faellig_am")),
                     prioritaet=1 if request.form.get("prioritaet") == "on" else 0,
                     created_by=(current_user() or {}).get("username"),
                     created_at=svc.now_str(), erledigt=0)
            db.add(t)
            svc.log_import(db, "AUFGABE", f"Aufgabe für ID={pid} angelegt",
                           participant_id=pid)
            db.commit()
            flash(f"Aufgabe für '{p.name or pid}' angelegt.")
            return redirect(url_for("tasks.list_tasks"))
        # GET
        pname, pgsm = p.name, p.gsm
    finally:
        db.close()
    return render_template("tasks/new.html", pid=pid, pname=pname, pgsm=pgsm,
                           active_tab="aufgaben")


@bp.post("/aufgaben/<int:tid>/done")
@require("write")
def toggle_done(tid):
    db = SessionLocal()
    try:
        t = db.get(Task, tid)
        if t is not None:
            t.erledigt = 0 if t.erledigt else 1
            t.done_at = svc.now_str() if t.erledigt else None
            db.commit()
            flash(f"Aufgabe {'erledigt' if t.erledigt else 'wieder offen'}.")
    finally:
        db.close()
    return redirect(request.form.get("back") or url_for("tasks.list_tasks"))


@bp.post("/aufgaben/<int:tid>/delete")
@require("write")
def delete_task(tid):
    db = SessionLocal()
    try:
        t = db.get(Task, tid)
        if t is not None:
            db.delete(t)
            db.commit()
            flash("Aufgabe gelöscht.")
    finally:
        db.close()
    return redirect(request.form.get("back") or url_for("tasks.list_tasks"))
