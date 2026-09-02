#!/usr/bin/env python3
"""Isolierte Regressionstests für Authentifizierung und read-only API-Verträge."""

from __future__ import annotations

import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _build_template(path: Path, split_runs: bool, with_date_tag: bool) -> None:
    """Erzeugt eine Vorlage wie Word sie speichert.

    `split_runs` bildet den Normalfall echter Vorlagen nach: Word verteilt einen
    getippten Platzhalter über mehrere Runs, sobald der Text nachbearbeitet
    wurde.
    """
    import docx

    doc = docx.Document()
    doc.add_paragraph("Berlin, {{ datum }}" if with_date_tag else "Berlin, 01.01.2020")
    paragraph = doc.add_paragraph()
    if split_runs:
        for chunk in ("Betrifft Rufnummer: {{ num", "mer", " }}"):
            paragraph.add_run(chunk)
    else:
        paragraph.add_run("Betrifft Rufnummer: {{ nummer }}")
    table = doc.add_table(rows=1, cols=1)
    table.rows[0].cells[0].paragraphs[0].add_run("Tabelle: {{ nummer }}")
    doc.save(str(path))


def _text_of(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    parts += [cell.text for table in document.tables
              for row in table.rows for cell in row.cells]
    return "\n".join(parts)


def check_letter_generation(data_dir: str) -> None:
    """Kündigung und Rücknahme: plattformneutrales Füllen der Vorlage."""
    from datetime import date

    from modules import kuendigung as kmod

    template_dir = Path(data_dir) / "Dokumente"
    template_dir.mkdir(parents=True, exist_ok=True)
    gsm = "491701234567"
    today = date.today().strftime("%d.%m.%Y")

    # Beide Schreiben-Typen, beide Vorlagenformen und beide Datumsvarianten.
    for kind in ("kuendigung", "ruecknahme"):
        for split_runs in (False, True):
            for with_date_tag in (False, True):
                template = kmod.TEMPLATES[kind]
                _build_template(template, split_runs, with_date_tag)
                text = _text_of(kmod.generate_letter(kind, gsm))
                assert f"Betrifft Rufnummer: {gsm}" in text, (kind, split_runs, text)
                assert f"Tabelle: {gsm}" in text, (kind, split_runs, text)
                assert "{{" not in text, (kind, split_runs, text)
                # Mit Platzhalter füllt docxtpl das Datum, ohne Platzhalter
                # greift die Ersetzung über das Format DD.MM.YYYY.
                assert f"Berlin, {today}" in text, (kind, with_date_tag, text)
                template.unlink()

    # Vorlagen mit dem alten Umlaut-Namen bleiben übergangsweise lesbar.
    legacy = template_dir / kmod.LEGACY_TEMPLATES["kuendigung"]
    _build_template(legacy, split_runs=True, with_date_tag=True)
    # samefile statt ==: robust gegen NFC/NFD-Normalisierung des Umlaut-Namens
    # (unter Windows weicht die String-Form des Pfades ab, die Datei ist dieselbe).
    assert kmod.resolve_template("kuendigung").samefile(legacy)
    text = _text_of(kmod.generate_letter("kuendigung", gsm))
    assert f"Betrifft Rufnummer: {gsm}" in text, text
    legacy.unlink()

    # Fehlerfälle bleiben unterscheidbar: die API meldet sie getrennt.
    try:
        kmod.resolve_template("unbekannt")
    except ValueError:
        pass
    else:
        raise AssertionError("Unbekannter Schreiben-Typ muss ValueError auslösen")
    try:
        kmod.generate_letter("kuendigung", gsm)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Fehlende Vorlage muss FileNotFoundError auslösen")

    # Ohne GSM-Nummer bleibt das Schreiben erzeugbar.
    template = kmod.TEMPLATES["ruecknahme"]
    _build_template(template, split_runs=False, with_date_tag=True)
    assert "unbekannt" in _text_of(kmod.generate_letter("ruecknahme", ""))
    template.unlink()


def check_pdf_engine_selection() -> None:
    """Auswahl des PDF-Wegs, ohne Word oder LibreOffice zu benötigen."""
    from modules import kuendigung as kmod

    calls = []
    original = (kmod.convert_to_pdf, kmod.convert_to_pdf_soffice,
                kmod.word_available, kmod.find_soffice)
    kmod.convert_to_pdf = lambda path: calls.append("word") or Path(path)
    kmod.convert_to_pdf_soffice = lambda path: calls.append("soffice") or Path(path)
    try:
        # Windows mit Word: Word gewinnt, LibreOffice wird nicht gebraucht.
        kmod.word_available = lambda: True
        kmod.find_soffice = lambda: ""
        calls.clear()
        kmod.convert_to_pdf_auto(Path("brief.docx"))
        assert calls == ["word"], calls

        # Linux: kein Word, LibreOffice übernimmt.
        kmod.word_available = lambda: False
        kmod.find_soffice = lambda: "/usr/bin/soffice"
        calls.clear()
        kmod.convert_to_pdf_auto(Path("brief.docx"))
        assert calls == ["soffice"], calls

        # Weder noch: verständlicher Fehler statt Absturz im Konverter.
        kmod.find_soffice = lambda: ""
        try:
            kmod.convert_to_pdf_auto(Path("brief.docx"))
        except RuntimeError as exc:
            assert "Word" in str(exc) and "LibreOffice" in str(exc), exc
        else:
            raise AssertionError("Fehlende PDF-Erzeugung muss RuntimeError auslösen")

        # Erzwungene Engine ignoriert die Erkennung.
        os.environ["MOBILFUNK_PDF_ENGINE"] = "soffice"
        calls.clear()
        kmod.convert_to_pdf_auto(Path("brief.docx"))
        assert calls == ["soffice"], calls
        os.environ["MOBILFUNK_PDF_ENGINE"] = "unsinn"
        try:
            kmod.convert_to_pdf_auto(Path("brief.docx"))
        except ValueError:
            pass
        else:
            raise AssertionError("Unbekannte Engine muss ValueError auslösen")
    finally:
        os.environ.pop("MOBILFUNK_PDF_ENGINE", None)
        (kmod.convert_to_pdf, kmod.convert_to_pdf_soffice,
         kmod.word_available, kmod.find_soffice) = original

    # Portable LibreOffice-Kopie über MOBILFUNK_SOFFICE.
    portable = Path(os.environ["MOBILFUNK_DATA_DIR"]) / "soffice-portable"
    portable.write_text("#!/bin/sh\n", encoding="utf-8")
    os.environ["MOBILFUNK_SOFFICE"] = str(portable)
    try:
        assert kmod.find_soffice() == str(portable)
    finally:
        os.environ.pop("MOBILFUNK_SOFFICE", None)
        portable.unlink()
    # Unter Linux ist Word nie eine Option.
    if sys.platform != "win32":
        assert kmod.word_available() is False


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mobilfunk-regression-", ignore_cleanup_errors=True) as data_dir:
        os.environ.update(
            MOBILFUNK_DATA_DIR=data_dir,
            MOBILFUNK_WEBCONFIG_DIR=data_dir,
            MOBILFUNK_SECRET="regression-only-secret",
            MOBILFUNK_CSRF="0",
        )

        from modules.auth import hash_password
        from webapp import create_app
        from webapp.db import Base, SessionLocal, engine
        from webapp.models import Participant, User

        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            db.add_all(
                [
                    User(username="admin", password_hash=hash_password("admin-pass"),
                         role="admin", active=1, force_pw_change=0),
                    User(username="reader", password_hash=hash_password("reader-pass"),
                         role="read", active=1, force_pw_change=0),
                    Participant(name="Fixture Teilnehmer", gsm="491701234567", verified=1),
                ]
            )
            db.commit()
        finally:
            db.close()

        client = create_app().test_client()

        assert client.get("/api/version").status_code == 200
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/participants").status_code == 401
        assert client.post("/api/login", json={"username": "admin", "password": "wrong"}).status_code == 401

        login = client.post("/api/login", json={"username": "admin", "password": "admin-pass"})
        assert login.status_code == 200, login.get_data(as_text=True)
        assert login.json["user"]["role"] == "admin"
        assert client.get("/api/me").status_code == 200

        participants = client.get("/api/participants")
        assert participants.status_code == 200
        assert participants.json["total"] == 1
        assert client.get("/api/summary").status_code == 200
        assert client.get("/api/tasks").status_code == 200
        assert client.get("/api/stats").status_code == 200
        documents_dir = Path(data_dir) / "Kuendigungen"
        documents_dir.mkdir()
        (documents_dir / "fixture.txt").write_text("temporary document", encoding="utf-8")
        assert client.get("/api/documents").status_code == 200
        document = client.get("/api/documents/fixture.txt")
        assert document.status_code == 200
        assert document.data == b"temporary document"
        assert client.get("/api/documents/../../etc/passwd").status_code in (400, 404)
        assert client.get("/api/syno/file/../../etc/passwd").status_code == 400
        assert client.post("/api/import/vodafone/preview").status_code == 400
        assert client.post("/api/import/syno").status_code == 400
        assert client.post(
            "/api/import/vodafone/preview",
            data={"file": (BytesIO(b"not-an-excel-file"), "invalid.txt")},
            content_type="multipart/form-data",
        ).status_code == 400
        assert client.post(
            "/api/import/vodafone/preview",
            data={"file": (BytesIO(b"not-a-valid-xlsx"), "fixture.xlsx")},
            content_type="multipart/form-data",
        ).status_code == 400

        assert client.post("/api/logout").status_code == 200
        assert client.post("/api/login", json={"username": "reader", "password": "reader-pass"}).status_code == 200
        assert client.post("/api/participants", json={"name": "Denied"}).status_code == 403
        assert client.post("/api/participants/1/tasks", json={"kommentar": "Denied"}).status_code == 403
        assert client.post("/api/participants/1/archive").status_code == 403

        assert client.post("/api/logout").status_code == 200
        assert client.post("/api/login", json={"username": "admin", "password": "admin-pass"}).status_code == 200
        created = client.post("/api/participants", json={"name": "CRUD Fixture", "gsm": "491701111111"})
        assert created.status_code == 201, created.get_data(as_text=True)
        participant_id = created.json["participant"]["id"]
        assert client.put(f"/api/participants/{participant_id}", json={"name": "CRUD Updated"}).status_code == 200
        assert client.post(f"/api/participants/{participant_id}/verify").status_code == 200
        assert client.post(f"/api/participants/{participant_id}/overhead").status_code == 200
        assert client.post(f"/api/participants/{participant_id}/move", json={"provider": "Telekom"}).status_code == 200
        archived = client.post(f"/api/participants/{participant_id}/archive")
        assert archived.status_code == 200 and archived.json["archived"] == 1
        # archivierter Eintrag verschwindet aus dem Provider-View, taucht im Archiv-View auf
        telekom_view = client.get("/api/participants?view=telekom")
        assert all(p["id"] != participant_id for p in telekom_view.json["participants"])
        archiv_view = client.get("/api/participants?view=archiv")
        assert any(p["id"] == participant_id for p in archiv_view.json["participants"])
        restored = client.post(f"/api/participants/{participant_id}/archive")
        assert restored.status_code == 200 and restored.json["archived"] == 0
        task = client.post(f"/api/participants/{participant_id}/tasks", json={"kommentar": "CRUD Task"})
        assert task.status_code == 201, task.get_data(as_text=True)
        task_id = task.json["id"]
        assert client.post(f"/api/tasks/{task_id}/done").status_code == 200
        assert client.delete(f"/api/tasks/{task_id}").status_code == 200
        assert client.delete(f"/api/participants/{participant_id}").status_code == 200

        assert client.post("/api/logout").status_code == 200
        assert client.get("/api/me").status_code == 401

        # Nur das Füllen der Vorlage, ohne PDF-Konvertierung: LibreOffice ist
        # in CI nicht installiert und der Schritt ist plattformspezifisch.
        check_letter_generation(data_dir)
        check_pdf_engine_selection()

        # Verbindungen lösen, sonst kann Windows das Temp-Verzeichnis nicht
        # aufräumen (offene DB-Datei -> WinError 32).
        engine.dispose()
        print("Backend regression tests passed (temporary SQLite database).")


if __name__ == "__main__":
    main()
