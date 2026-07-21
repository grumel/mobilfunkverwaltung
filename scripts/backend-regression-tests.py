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


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mobilfunk-regression-") as data_dir:
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
        assert client.get("/api/documents").status_code == 200
        assert client.get("/api/documents/../../etc/passwd").status_code in (400, 404)
        assert client.get("/api/syno/file/../../etc/passwd").status_code == 400
        assert client.post("/api/import/vodafone/preview").status_code == 400
        assert client.post("/api/import/syno").status_code == 400
        assert client.post(
            "/api/import/vodafone/preview",
            data={"file": (BytesIO(b"not-an-excel-file"), "invalid.txt")},
            content_type="multipart/form-data",
        ).status_code == 400

        assert client.post("/api/logout").status_code == 200
        assert client.get("/api/me").status_code == 401

        print("Backend regression tests passed (temporary SQLite database).")


if __name__ == "__main__":
    main()
