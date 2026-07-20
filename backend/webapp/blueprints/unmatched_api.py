"""Schreibende JSON-Endpunkte für verwaiste Syno-Geräte."""

from flask import Blueprint, jsonify, request

from webapp.db import SessionLocal
from webapp.models import Participant, UnmatchedDevice
from webapp.security import can, current_user
from webapp import service as svc

bp = Blueprint("unmatched_api", __name__, url_prefix="/api/unmatched-devices")
FIELDS = ["id", "quelle", "gsm", "benutzer", "geraet", "startdatum", "importdatum"]
EDITABLE = ["quelle", "gsm", "benutzer", "geraet", "startdatum"]


def _dict(row):
    return {field: getattr(row, field) for field in FIELDS}


def _clean(value):
    return (value.strip() or None) if isinstance(value, str) else value


def _require_write():
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("write"):
        return jsonify(error="keine Berechtigung"), 403
    return None


@bp.put("/<int:device_id>")
def update_device(device_id):
    denied = _require_write()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    gsm = (data.get("gsm") or "").strip()
    if "gsm" in data and gsm and not svc.is_valid_gsm(gsm):
        return jsonify(error="GSM-Nummer ungültig (10–15 Ziffern, optional +/00)."), 400

    db = SessionLocal()
    try:
        row = db.get(UnmatchedDevice, device_id)
        if not row:
            return jsonify(error="nicht gefunden"), 404
        for field in EDITABLE:
            if field in data:
                setattr(row, field, _clean(data[field]))
        svc.log_audit(db, current_user(), "UNMATCHED_UPDATE",
                      f"Verwaistes Gerät ID={device_id} geändert (API)",
                      table_name="unmatched_devices", record_id=device_id)
        db.commit()
        return jsonify(device=_dict(row))
    finally:
        db.close()


@bp.delete("/<int:device_id>")
def delete_device(device_id):
    if not current_user():
        return jsonify(error="nicht angemeldet"), 401
    if not can("delete"):
        return jsonify(error="Löschen erfordert Admin-Rechte"), 403

    db = SessionLocal()
    try:
        row = db.get(UnmatchedDevice, device_id)
        if not row:
            return jsonify(error="nicht gefunden"), 404
        label = row.geraet or row.benutzer or f"ID {device_id}"
        db.delete(row)
        svc.log_audit(db, current_user(), "UNMATCHED_DELETE",
                      f"Verwaistes Gerät '{label}' gelöscht (API)",
                      table_name="unmatched_devices", record_id=device_id)
        db.commit()
        return jsonify(ok=True, id=device_id)
    finally:
        db.close()


@bp.post("/<int:device_id>/assign")
def assign_device(device_id):
    denied = _require_write()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        participant_id = int(data.get("participant_id"))
    except (TypeError, ValueError):
        return jsonify(error="Bitte einen Teilnehmer auswählen."), 400
    slot = data.get("slot", "auto")
    if slot not in ("auto", "syno", "syno2"):
        return jsonify(error="Ungültiger Geräteplatz."), 400

    db = SessionLocal()
    try:
        row = db.get(UnmatchedDevice, device_id)
        participant = db.get(Participant, participant_id)
        if not row:
            return jsonify(error="verwaistes Gerät nicht gefunden"), 404
        if not participant:
            return jsonify(error="Teilnehmer nicht gefunden"), 404

        target = slot
        if target == "auto":
            target = "syno" if not (participant.syno or "").strip() else "syno2"
        if (getattr(participant, target) or "").strip():
            return jsonify(error=f"{target} ist beim Teilnehmer bereits belegt."), 409

        setattr(participant, target, row.geraet)
        setattr(participant, "start_" + target, row.startdatum)
        if not (participant.gsm or "").strip() and (row.gsm or "").strip():
            if svc.is_valid_gsm(row.gsm.strip()):
                participant.gsm = row.gsm.strip()
        participant.updated_at = svc.now_str()
        label = row.geraet or f"Gerät {device_id}"
        db.delete(row)
        svc.log_import(db, "SYNO_ASSIGN",
                       f"Verwaistes Gerät ID={device_id} → Teilnehmer ID={participant_id} ({target})",
                       participant_id=participant_id)
        svc.log_audit(db, current_user(), "UNMATCHED_ASSIGN",
                      f"'{label}' Teilnehmer '{participant.name or participant_id}' zugeordnet ({target})",
                      table_name="participants", record_id=participant_id)
        db.commit()
        return jsonify(ok=True, participant_id=participant_id, slot=target)
    finally:
        db.close()


@bp.post("/<int:device_id>/create-participant")
def create_participant(device_id):
    denied = _require_write()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}

    db = SessionLocal()
    try:
        row = db.get(UnmatchedDevice, device_id)
        if not row:
            return jsonify(error="nicht gefunden"), 404
        name = (data.get("name") or row.benutzer or "").strip()
        gsm = (data.get("gsm") or row.gsm or "").strip()
        if gsm and not svc.is_valid_gsm(gsm):
            return jsonify(error="GSM-Nummer ungültig (10–15 Ziffern, optional +/00)."), 400
        if not name:
            return jsonify(error="Bitte einen Namen angeben."), 400

        participant = Participant(
            master_id=svc.next_master_id(db),
            created_at=svc.now_str(),
            updated_at=svc.now_str(),
            name=name,
            gsm=gsm or None,
            plant=_clean(data.get("plant")),
            konto=_clean(data.get("konto")),
            provider="Ohne SIM",
            syno=row.geraet,
            start_syno=row.startdatum,
            verified=0,
            pruefung_grund="Aus verwaistem Syno-Gerät angelegt",
            bemerkung=_clean(data.get("bemerkung")),
        )
        db.add(participant)
        db.flush()
        db.delete(row)
        svc.log_import(db, "UNMATCHED_CREATE",
                       f"Verwaistes Gerät ID={device_id} als Teilnehmer ID={participant.id} angelegt",
                       participant_id=participant.id)
        svc.log_audit(db, current_user(), "UNMATCHED_CREATE",
                      f"Teilnehmer '{participant.name}' aus verwaistem Gerät angelegt",
                      table_name="participants", record_id=participant.id)
        db.commit()
        return jsonify(participant_id=participant.id), 201
    finally:
        db.close()
