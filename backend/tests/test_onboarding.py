from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    FormationRecord,
    OrganizationInvitationRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.onboarding import get_onboarding_status
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    org = OrganizationRecord(
        name="School",
        slug="school",
        status="active",
        is_active=True,
    )
    db.add_all([owner, org])
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
    )
    db.commit()
    tenant = resolve_tenant_context(
        db,
        user=owner,
        organization_id=org.id,
    )
    return org, tenant


def test_onboarding_status_is_derived_from_real_school_data() -> None:
    db = build_db()
    org, tenant = seed(db)

    initial = get_onboarding_status(db, tenant)
    assert initial.completed_steps == 1
    assert initial.next_step is not None
    assert initial.next_step.key == "identity"

    org.contact_email = "contact@example.test"
    org.subdomain = "school"
    db.add(
        OrganizationInvitationRecord(
            organization_id=org.id,
            email="teacher@example.test",
            role="teacher",
            token_hash="x" * 64,
            status="pending",
            expires_at=datetime.now(UTC),
        )
    )
    db.add(
        FormationRecord(
            organization_id=org.id,
            slug="first-course",
            title="First course",
            description="",
            status="draft",
        )
    )
    db.commit()

    complete = get_onboarding_status(db, tenant)
    assert complete.completed_steps == 5
    assert complete.progress_percent == 100
    assert complete.is_complete is True
    assert complete.next_step is None
