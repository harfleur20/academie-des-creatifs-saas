import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.commerce import (
    PURCHASE_BLOCKED_MESSAGE,
    _purchase_blocked_reason,
    _require_public_purchase_allowed,
)
from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationMemberRoleRecord,
    OrganizationRecord,
    UserRecord,
)


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed_member(db: Session, role: str) -> tuple[OrganizationRecord, UserRecord, OrganizationMemberRecord]:
    org = OrganizationRecord(
        name="School Business",
        slug="school-business",
        status="active",
        is_active=True,
    )
    user = UserRecord(
        email=f"{role}@test.dev",
        full_name=f"Test {role}",
        status="active",
        platform_role="user",
    )
    db.add_all([org, user])
    db.flush()
    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=user.id,
        role=role,
        status="active",
    )
    db.add(member)
    db.commit()
    return org, user, member


@pytest.mark.parametrize("role", ["owner", "admin", "manager", "teacher"])
def test_school_staff_cannot_buy_school_formations(role: str) -> None:
    db = build_db()
    org, user, _member = seed_member(db, role)

    with pytest.raises(HTTPException) as exc:
        _require_public_purchase_allowed(
            db,
            organization_id=org.id,
            user=user,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == PURCHASE_BLOCKED_MESSAGE


def test_student_can_buy_school_formations() -> None:
    db = build_db()
    org, user, _member = seed_member(db, "student")

    _require_public_purchase_allowed(
        db,
        organization_id=org.id,
        user=user,
    )


def test_teacher_role_blocks_multi_role_student_account() -> None:
    db = build_db()
    org, user, member = seed_member(db, "student")
    db.add(
        OrganizationMemberRoleRecord(
            organization_id=org.id,
            member_id=member.id,
            role="teacher",
        )
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        _require_public_purchase_allowed(
            db,
            organization_id=org.id,
            user=user,
        )

    assert exc.value.status_code == 403


def test_user_without_school_membership_can_buy() -> None:
    db = build_db()
    org = OrganizationRecord(
        name="School Business",
        slug="school-business",
        status="active",
        is_active=True,
    )
    user = UserRecord(
        email="visitor@test.dev",
        full_name="Visitor",
        status="active",
        platform_role="user",
    )
    db.add_all([org, user])
    db.commit()

    _require_public_purchase_allowed(
        db,
        organization_id=org.id,
        user=user,
    )


def test_super_admin_cannot_buy_school_formations() -> None:
    db = build_db()
    org = OrganizationRecord(
        name="School Business",
        slug="school-business",
        status="active",
        is_active=True,
    )
    user = UserRecord(
        email="superadmin@test.dev",
        full_name="Super Admin",
        status="active",
        platform_role="super_admin",
    )
    db.add_all([org, user])
    db.commit()

    with pytest.raises(HTTPException) as exc:
        _require_public_purchase_allowed(
            db,
            organization_id=org.id,
            user=user,
        )

    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", ["owner", "teacher"])
def test_school_staff_see_the_prices_but_are_told_why_they_cannot_buy(role: str) -> None:
    db = build_db()
    org, user, _member = seed_member(db, role)
    assert _purchase_blocked_reason(db, organization_id=org.id, user=user) == PURCHASE_BLOCKED_MESSAGE
    buyer = UserRecord(email="buyer@test.dev", full_name="Buyer", status="active", platform_role="user")
    db.add(buyer)
    db.commit()
    assert _purchase_blocked_reason(db, organization_id=org.id, user=buyer) is None
