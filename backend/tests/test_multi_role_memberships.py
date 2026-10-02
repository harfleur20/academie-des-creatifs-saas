from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
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
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([owner, org])
    db.flush()
    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=owner.id,
        role="owner",
        status="active",
    )
    db.add(member)
    db.commit()
    return owner, org, member


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
    updated = update_member_functional_roles(
        db,
        tenant,
        member.id,
        OrganizationMemberFunctionalRolesUpdate(
            functional_roles=[],
        ),
    )

    assert effective_member_roles(updated) == frozenset({"owner"})
