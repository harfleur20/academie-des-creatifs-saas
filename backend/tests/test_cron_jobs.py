"""The local job runner and the hourly GitHub job call the same protected routes."""

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from main import app
from scripts.run_cron_jobs import JOBS, run_once

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/billing-lifecycle.yml"


def empty_db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_the_local_runner_calls_what_github_calls():
    called = re.findall(r'"\$BILLING_CRON_URL(/api/v1/[^"]+)"', WORKFLOW.read_text(encoding="utf-8"))
    assert called == [path for _label, path in JOBS]


def test_each_job_runs_with_the_secret_and_is_refused_without_it(monkeypatch, capsys):
    monkeypatch.setattr(settings, "billing_cron_secret", "cron-secret")
    db = empty_db()
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        assert run_once(client, "cron-secret") is True
        accepted = capsys.readouterr().out
        assert run_once(client, "wrong-secret") is False
        refused = capsys.readouterr().err
    finally:
        app.dependency_overrides.clear()
    for label, _path in JOBS:
        assert f"{label} : {{" in accepted
        assert f"{label} : refusé (401" in refused
