"""The read-only demo of the platform (app/services/demo.py, docs/DEMO.md)."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from test_academic_suite import seed

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import OrganizationMemberRecord, OrganizationRecord, UserRecord
from app.services.demo import DEMO_SITE_CLOSED, require_not_demo
from app.services.membership_roles import replace_effective_roles


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
