#!/usr/bin/env python3
"""Isolierter CI-Smoke-Test für Flask, Login, API und SQLite."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mobilfunk-ci-") as data_dir:
        os.environ["MOBILFUNK_DATA_DIR"] = data_dir
        os.environ["MOBILFUNK_WEBCONFIG_DIR"] = data_dir
        os.environ.setdefault("MOBILFUNK_SECRET", "ci-only-secret")
        os.environ["MOBILFUNK_CSRF"] = "0"

        from modules.auth import hash_password
        from webapp import create_app
        from webapp.db import Base, SessionLocal, engine
        from webapp.models import User

        Base.metadata.create_all(engine)
        session = SessionLocal()
        try:
            session.add(
                User(
                    username="ci-smoke",
                    password_hash=hash_password("ci-smoke-password"),
                    role="admin",
                    active=1,
                    force_pw_change=0,
                )
            )
            session.commit()
        finally:
            session.close()

        client = create_app().test_client()
        version = client.get("/api/version")
        assert version.status_code == 200, version.get_data(as_text=True)

        login = client.post(
            "/api/login",
            json={"username": "ci-smoke", "password": "ci-smoke-password"},
        )
        assert login.status_code == 200, login.get_data(as_text=True)

        me = client.get("/api/me")
        assert me.status_code == 200, me.get_data(as_text=True)
        assert me.json["user"]["role"] == "admin"

        database = Path(data_dir) / "mobilfunk.db"
        with sqlite3.connect(database) as connection:
            count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        assert count == 1

        print("Backend smoke test passed (temporary SQLite database).")


if __name__ == "__main__":
    main()
