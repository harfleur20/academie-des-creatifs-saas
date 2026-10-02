from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import OrganizationMemberRecord, OrganizationRecord, UserRecord
from app.schemas.organizations import OrganizationUpdate
from app.services.organization_management import update_organization_settings
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session, role: str = "owner"):
    user = UserRecord(
        email=f"{role}@example.test",
        full_name=role.title(),
        status="active",
    )
    org = OrganizationRecord(name="Initial School", slug=f"school-{role}")
    db.add_all([user, org])
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=user.id,
            role=role,
            status="active",
        )
    )
    db.commit()
    tenant = resolve_tenant_context(
        db,
        user=user,
        organization_id=org.id,
    )
    return org, tenant


def test_owner_can_rename_once_then_cooldown_blocks_second_change(monkeypatch) -> None:
    db = build_db()
    org, tenant = seed(db, "owner")
    monkeypatch.setattr(settings, "organization_name_change_cooldown_days", 30)

    first = update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(name="New School"),
    )
    assert first.name == "New School"
    assert first.name_changed_at is not None

    with pytest.raises(HTTPException) as exc:
        update_organization_settings(
            db,
            tenant,
            OrganizationUpdate(name="Another School"),
        )

    assert exc.value.status_code == 409
    assert "30 jours" in exc.value.detail


def test_same_name_does_not_reset_cooldown_timestamp() -> None:
    db = build_db()
    org, tenant = seed(db, "owner")
    old_time = datetime.now(UTC) - timedelta(days=10)
    org.name_changed_at = old_time
    db.commit()

    update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(
            name="Initial School",
            timezone="Europe/Paris",
        ),
    )

    db.refresh(org)
    normalized = (
        org.name_changed_at.replace(tzinfo=UTC)
        if org.name_changed_at.tzinfo is None
        else org.name_changed_at.astimezone(UTC)
    )
    assert normalized == old_time


def test_owner_can_rename_again_after_cooldown(monkeypatch) -> None:
    db = build_db()
    org, tenant = seed(db, "owner")
    monkeypatch.setattr(settings, "organization_name_change_cooldown_days", 30)
    org.name_changed_at = datetime.now(UTC) - timedelta(days=31)
    db.commit()

    updated = update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(name="Allowed Again"),
    )
    assert updated.name == "Allowed Again"


def test_admin_cannot_rename_school() -> None:
    db = build_db()
    _, tenant = seed(db, "admin")

    with pytest.raises(HTTPException) as exc:
        update_organization_settings(
            db,
            tenant,
            OrganizationUpdate(name="Admin Rename"),
        )

    assert exc.value.status_code == 403


def test_admin_can_still_update_non_name_settings() -> None:
    db = build_db()
    _, tenant = seed(db, "admin")

    updated = update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(timezone="Europe/Paris"),
    )

    assert updated.timezone == "Europe/Paris"
