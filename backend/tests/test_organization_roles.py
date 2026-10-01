import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.tenancy import require_organization_roles, resolve_tenant_context


def build_context(role: str):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)

    user = UserRecord(
        email=f"{role}@example.test",
        full_name=role.title(),
        status="active",
    )
    org = OrganizationRecord(name="Test School", slug=f"test-{role}")
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
    return db, resolve_tenant_context(db, user=user, organization_id=org.id)


@pytest.mark.parametrize("role", ["owner", "admin", "manager"])
def test_management_roles_are_accepted(role: str) -> None:
    _, tenant = build_context(role)
    assert require_organization_roles(
        tenant,
        "owner",
        "admin",
        "manager",
    ) is tenant


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_non_management_roles_are_rejected(role: str) -> None:
    _, tenant = build_context(role)

    with pytest.raises(HTTPException) as exc:
        require_organization_roles(
            tenant,
            "owner",
            "admin",
            "manager",
        )

    assert exc.value.status_code == 403
