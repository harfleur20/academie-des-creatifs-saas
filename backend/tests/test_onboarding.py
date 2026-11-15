from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    FormationRecord,
    OrganizationInvitationRecord,
    OrganizationLegalProfileRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.onboarding import get_onboarding_status
from app.schemas.formations import FormationCreate
from app.services.formations import create_formation
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
    # The owner is already the first member of the school team.
    assert initial.completed_steps == 2
    assert initial.next_step is not None
    assert initial.next_step.key == "identity"
    assert [step.available for step in initial.steps] == [True, True, False, False, False, False, False]

    org.contact_email = "contact@example.test"
    org.subdomain = "school"
    db.add(OrganizationPublicSiteRecord(
        organization_id=org.id,
        student_code_prefix="SC",
        student_code_prefix_confirmed_at=datetime.now(UTC),
    ))
    db.add(OrganizationLegalProfileRecord(
        organization_id=org.id,
        legal_name="School SARL",
        legal_address="12 rue des écoles",
        invoice_email="factures@example.com",
        default_currency="XAF",
    ))
    db.add(
        OrganizationInvitationRecord(
            organization_id=org.id,
            email="teacher@example.test",
            role="teacher",
            token_hash="x" * 64,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(days=7),
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
    assert complete.completed_steps == 7
    assert complete.progress_percent == 100
    assert complete.is_complete is True
    assert complete.next_step is None


def test_formation_creation_waits_for_billing_details() -> None:
    db = build_db()
    org, tenant = seed(db)
    org.contact_email = "contact@example.com"
    org.subdomain = "school"
    db.add_all([
        OrganizationPublicSiteRecord(
            organization_id=org.id,
            student_code_prefix="SC",
            student_code_prefix_confirmed_at=datetime.now(UTC),
        ),
        OrganizationInvitationRecord(
            organization_id=org.id,
            email="teacher@example.com",
            role="teacher",
            token_hash="y" * 64,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        ),
    ])
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_formation(db, tenant, FormationCreate(slug="first", title="First"))
    assert exc.value.status_code == 409
    assert "facturation" in exc.value.detail

    db.add(OrganizationLegalProfileRecord(
        organization_id=org.id,
        legal_name="School SARL",
        legal_address="12 rue des écoles",
        invoice_email="factures@example.com",
        default_currency="XAF",
    ))
    db.commit()
    assert create_formation(db, tenant, FormationCreate(slug="first", title="First")).slug == "first"
