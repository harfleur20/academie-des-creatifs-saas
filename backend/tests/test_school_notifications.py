import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import OrganizationMemberRecord, OrganizationRecord, SchoolNotificationRecord, UserRecord
from app.services.school_notifications import notify_school_managers, notify_user


def test_notifications_are_scoped_to_school_and_recipient() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    owner = UserRecord(email="owner@notifications.test", full_name="Owner", status="active")
    outsider = UserRecord(email="other@notifications.test", full_name="Other", status="active")
    first = OrganizationRecord(name="First", slug="first", status="active", is_active=True)
    second = OrganizationRecord(name="Second", slug="second", status="active", is_active=True)
    db.add_all([owner, outsider, first, second])
    db.flush()
    db.add_all([
        OrganizationMemberRecord(organization_id=first.id, user_id=owner.id, role="owner", status="active"),
        OrganizationMemberRecord(organization_id=second.id, user_id=owner.id, role="owner", status="active"),
        OrganizationMemberRecord(organization_id=first.id, user_id=outsider.id, role="student", status="active"),
    ])
    db.flush()
    notify_school_managers(db, organization_id=first.id, event_key="sale:1", title="Vente école 1", message="Paiement reçu")
    notify_school_managers(db, organization_id=first.id, event_key="sale:1", title="Vente école 1", message="Paiement reçu")
    notify_user(db, organization_id=second.id, user_id=owner.id, event_key="sale:1", title="Vente école 2", message="Paiement reçu", audience="manage")
    with pytest.raises(ValueError):
        notify_user(db, organization_id=first.id, user_id=outsider.id, event_key="bad", title="Bad", message="Bad", audience="student", action_path="/app/manage/commerce")
    db.commit()
    rows = db.scalars(select(SchoolNotificationRecord)).all()
    assert len(rows) == 2

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            token = create_access_token(owner.id, session_version=owner.session_version)
            headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(first.id)}
            listed = client.get("/api/v1/notifications?space=manage", headers=headers)
            assert listed.status_code == 200
            assert [item["title"] for item in listed.json()] == ["Vente école 1"]
            first_id = listed.json()[0]["id"]
            second_id = next(row.id for row in rows if row.organization_id == second.id)

            assert client.post("/api/v1/notifications/read", headers=headers, json={"ids": [second_id]}).status_code == 204
            assert client.get("/api/v1/notifications?space=manage", headers=headers).json()[0]["read_at"] is None
            assert client.post("/api/v1/notifications/read", headers=headers, json={"ids": [first_id]}).status_code == 204
            assert client.get("/api/v1/notifications?space=manage", headers=headers).json()[0]["read_at"] is not None
            assert client.post("/api/v1/notifications/dismiss", headers=headers, json={"ids": [first_id]}).status_code == 204
            assert client.get("/api/v1/notifications?space=manage", headers=headers).json() == []

            other_school = {**headers, "X-Organization-Id": str(second.id)}
            assert [item["title"] for item in client.get("/api/v1/notifications?space=manage", headers=other_school).json()] == ["Vente école 2"]
            first_membership = db.scalar(select(OrganizationMemberRecord).where(
                OrganizationMemberRecord.organization_id == first.id,
                OrganizationMemberRecord.user_id == owner.id,
            ))
            first_membership.role = "student"
            db.commit()
            assert client.get("/api/v1/notifications?space=manage", headers=headers).status_code == 403
            assert client.get("/api/v1/notifications?space=student", headers=headers).json() == []
            outsider_token = create_access_token(outsider.id, session_version=outsider.session_version)
            outsider_headers = {"Authorization": f"Bearer {outsider_token}", "X-Organization-Id": str(first.id)}
            assert client.get("/api/v1/notifications?space=manage", headers=outsider_headers).status_code == 403
            assert client.get("/api/v1/notifications?space=manage", headers={**outsider_headers, "X-Organization-Id": str(second.id)}).status_code == 404
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
