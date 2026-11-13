"""The read-only demo of the platform (app/services/demo.py, demo_school.py, docs/DEMO.md)."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from test_academic_suite import seed

from app.core.config import settings
from app.core.security import verify_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    CommunicationOutboxRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    UserRecord,
)
from app.services.demo import DEMO_SITE_CLOSED, demo_member, require_not_demo
from app.services.demo_school import build_demo_school, remove_demo_school
from app.services.membership_roles import replace_effective_roles
from app.services.public_catalog import list_public_formations
from app.services.publication import formation_content_issues
from app.services.school_communications import queue_school_event


def shared_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


@pytest.fixture()
def demo(monkeypatch):
    db = shared_db()
    org, teacher, student, _, _, _, _, _, _ = seed(db)
    owner = UserRecord(email="direction@demo.test", full_name="Direction Démo", status="active")
    other = OrganizationRecord(name="Autre école", slug="autre-ecole")
    db.add_all([owner, other])
    db.flush()
    member = OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active")
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"owner"})
    db.commit()
    monkeypatch.setattr(settings, "demo_organization_slug", org.slug)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            yield client, db, org, other, owner, teacher, student
    finally:
        app.dependency_overrides.clear()
        db.close()


def start(client, space):
    response = client.post("/api/v1/auth/demo", json={"space": space})
    assert response.status_code == 200, response.text
    return response.json()


def test_the_landing_offers_the_demo_of_one_school(demo, monkeypatch):
    client, _db, org, *_ = demo
    assert client.get("/api/v1/auth/demo").json() == {"enabled": True, "school_name": org.name, "organization_slug": org.slug}
    monkeypatch.setattr(settings, "demo_organization_slug", "")
    assert client.get("/api/v1/auth/demo").json()["enabled"] is False
    assert client.post("/api/v1/auth/demo", json={"space": "student"}).status_code == 404


def test_each_space_opens_with_one_of_the_demo_school_members(demo):
    client, _db, org, _other, owner, teacher, student = demo
    for space, user in (("manage", owner), ("teacher", teacher), ("student", student)):
        session = start(client, space)
        assert (session["organization_id"], session["user"]["email"]) == (org.id, user.email)
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {session['access_token']}"})
        assert me.json()["email"] == user.email
        # A demo token is never traded for the shared login cookie.
        assert "set-cookie" not in me.headers
    # No cookie: the demo stays in the visitor's tab, their own session is untouched.
    assert "set-cookie" not in client.post("/api/v1/auth/demo", json={"space": "manage"}).headers


def test_a_demo_visitor_only_looks(demo):
    client, _db, org, other, *_ = demo
    token = start(client, "student")["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}
    assert client.get("/api/v1/notifications?space=student", headers=headers).status_code == 200
    refused = client.patch("/api/v1/auth/me", headers=headers, json={"full_name": "Pirate"})
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "demo_read_only"
    assert client.post("/api/v1/auth/me/change-password", headers=headers,
                       json={"current_password": "x", "new_password": "y" * 12}).status_code == 403
    elsewhere = client.get("/api/v1/notifications?space=student", headers={**headers, "X-Organization-Id": str(other.id)})
    assert elsewhere.status_code == 403


def test_the_demo_school_site_takes_no_order(demo):
    _client, _db, org, other, *_ = demo
    with pytest.raises(HTTPException) as closed:
        require_not_demo(org)
    assert closed.value.detail == DEMO_SITE_CLOSED
    require_not_demo(other)


def test_the_demo_school_is_built_around_its_day_and_sends_nothing(monkeypatch):
    db = shared_db()
    now = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
    summary = build_demo_school(db, now=now, site_url="https://ecoles.example.com/")
    org = db.get(OrganizationRecord, summary["organization_id"])
    monkeypatch.setattr(settings, "demo_organization_slug", org.slug)
    assert (summary["formations"], summary["students"]) == (6, 26)
    with pytest.raises(ValueError):
        build_demo_school(db, now=now)

    # Each space opens with the person the demo shows.
    assert demo_member(db, org, "manage").email == summary["owner"]
    assert demo_member(db, org, "teacher").email == summary["teacher"]
    assert demo_member(db, org, "student").email == summary["student"]
    # Nobody knows the passwords of these fictional people.
    owner = db.scalar(select(UserRecord).where(UserRecord.email == summary["owner"]))
    assert not verify_password("Demo2026!", owner.password_hash)

    # Prices in whole francs, covers served by the frontend, all published, the next cohorts after the day.
    formations = db.scalars(select(FormationRecord).where(FormationRecord.organization_id == org.id)).all()
    assert {item.price_cents for item in formations} == {90_000, 100_000, 120_000, 150_000, 180_000, 200_000}
    assert all(item.cover_image_url == f"https://ecoles.example.com/demo/covers/{item.slug}.jpg" for item in formations)
    assert all(formation_content_issues(item) == [] for item in formations)
    assert len(list_public_formations(db, org)) == 6
    upcoming = db.scalars(select(FormationSessionRecord).where(
        FormationSessionRecord.organization_id == org.id, FormationSessionRecord.start_date > now.date(),
    )).all()
    assert len(upcoming) == 4 and all(session.start_date.weekday() == 0 for session in upcoming)

    # Classes held before the day have their report, the ones after are planned.
    days = db.scalars(select(SessionCourseDayRecord).where(SessionCourseDayRecord.organization_id == org.id)).all()
    naive_now = now.replace(tzinfo=None)
    held = [day for day in days if day.scheduled_at.replace(tzinfo=None) + timedelta(hours=2) <= naive_now]
    planned = [day for day in days if day.scheduled_at.replace(tzinfo=None) > naive_now]
    assert held and planned
    assert all(day.report_submitted_at is not None for day in held)
    assert all(day.report_submitted_at is None for day in planned)

    # Nothing leaves the demo school.
    assert db.scalar(select(CommunicationOutboxRecord.id).where(CommunicationOutboxRecord.organization_id == org.id)) is None
    assert queue_school_event(db, org=org, event_key="student.welcome", user=owner) == []

    # It can be rebuilt: everything it owns goes, its people too.
    assert remove_demo_school(db) is True
    assert db.scalar(select(OrganizationRecord.id).where(OrganizationRecord.slug == org.slug)) is None
    assert db.scalar(select(UserRecord.id).where(UserRecord.email.like("%@studiokora.example"))) is None
    assert db.scalar(select(FormationRecord.id).where(FormationRecord.organization_id == org.id)) is None
