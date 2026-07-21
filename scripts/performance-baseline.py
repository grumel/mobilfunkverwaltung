#!/usr/bin/env python3
"""Kleine, reproduzierbare Performance-Baseline ohne Produktionszugriff."""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="mobilfunk-perf-") as data_dir:
        os.environ.update(
            MOBILFUNK_DATA_DIR=data_dir,
            MOBILFUNK_WEBCONFIG_DIR=data_dir,
            MOBILFUNK_SECRET="performance-only-secret",
            MOBILFUNK_CSRF="0",
        )
        from modules.auth import hash_password
        from webapp import create_app
        from webapp.db import Base, SessionLocal, engine
        from webapp.models import Participant, User

        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            db.add(User(username="perf", password_hash=hash_password("perf-pass"),
                        role="admin", active=1, force_pw_change=0))
            db.add_all([Participant(name=f"Fixture {i}", gsm=f"491701{i:06d}", verified=1)
                        for i in range(1, 101)])
            db.commit()
        finally:
            db.close()

        client = create_app().test_client()
        assert client.post("/api/login", json={"username": "perf", "password": "perf-pass"}).status_code == 200
        timings = {}
        for endpoint in ("/api/participants", "/api/summary", "/api/tasks", "/api/stats"):
            samples = []
            for _ in range(5):
                started = time.perf_counter()
                response = client.get(endpoint)
                samples.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200, (endpoint, response.status_code)
            timings[endpoint] = statistics.median(samples)

        print("Performance baseline (temporary SQLite, 100 participants; median of 5):")
        for endpoint, median_ms in timings.items():
            print(f"  {endpoint}: {median_ms:.2f} ms")


if __name__ == "__main__":
    main()
