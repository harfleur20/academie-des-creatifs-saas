from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    UserRecord,
)
from app.schemas.organizations import OrganizationMemberFunctionalRolesUpdate
from app.services.membership_roles import effective_member_roles
from app.services.organization_management import update_member_functional_roles
from app.services.tenancy import require_organization_roles, resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed_owner(db: Session):
    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner Teacher",
        status="active",
    )
    org = OrganizationRecord(name="School", slug="school", contact_email="contact@example.com", subdomain="school")
    db.add_all([owner, org])
    db.flush()
    db.add(OrganizationPublicSiteRecord(
        organization_id=org.id,
        student_code_prefix="SC",
        student_code_prefix_confirmed_at=datetime.now(UTC),
    ))
    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=owner.id,
        role="owner",
        status="active",
    )
    db.add(member)
    db.commit()
    return owner, org, member


def test_teacher_functional_role_requires_school_setup() -> None:
    db = build_db()
    owner = UserRecord(email="owner@example.com", full_name="Owner", status="active")
    org = OrganizationRecord(name="New School", slug="new-school")
    db.add_all([owner, org])
    db.flush()
    member = OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active")
    db.add(member)
    db.commit()
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    with pytest.raises(HTTPException) as exc:
        update_member_functional_roles(
            db, tenant, member.id,
            OrganizationMemberFunctionalRolesUpdate(functional_roles=["teacher"]),
        )
    assert exc.value.status_code == 409
    assert effective_member_roles(member) == frozenset({"owner"})


def test_owner_can_keep_management_and_gain_teacher_space() -> None:
    db = build_db()
    owner, org, member = seed_owner(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    updated = update_member_functional_roles(
        db,
        tenant,
        member.id,
        OrganizationMemberFunctionalRolesUpdate(
            functional_roles=["teacher"],
        ),
    )

    roles = effective_member_roles(updated)
    assert roles == frozenset({"owner", "teacher"})

    refreshed = resolve_tenant_context(db, user=owner, organization_id=org.id)
    assert require_organization_roles(refreshed, "owner") is refreshed
    assert require_organization_roles(refreshed, "teacher") is refreshed
    assert refreshed.organization_role == "owner"


def test_functional_roles_can_be_removed_without_losing_primary_role() -> None:
    db = build_db()
    owner, org, member = seed_owner(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    update_member_functional_roles(
        db,
        tenant,
        member.id,
        OrganizationMemberFunctionalRolesUpdate(
            functional_roles=["teacher", "student"],
        ),
    )
    profile = db.scalar(select(OrganizationStudentProfileRecord).where(
        OrganizationStudentProfileRecord.organization_id == org.id,
        OrganizationStudentProfileRecord.user_id == owner.id,
    ))
    assert profile is not None
    assert profile.student_code.startswith(f"SC{datetime.now(UTC):%y}-")
    updated = update_member_functional_roles(
        db,
        tenant,
        member.id,
        OrganizationMemberFunctionalRolesUpdate(
            functional_roles=[],
        ),
    )

    assert effective_member_roles(updated) == frozenset({"owner"})
