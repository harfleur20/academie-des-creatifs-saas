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
from app.schemas.organizations import (
    OrganizationInvitationCreate,
    OrganizationMemberUpdate,
    OrganizationUpdate,
)
from app.services.organization_management import (
    accept_invitation,
    create_invitation,
    update_member,
    update_organization_settings,
)
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def add_user(db: Session, email: str, name: str) -> UserRecord:
    user = UserRecord(email=email, full_name=name, status="active")
    db.add(user)
    db.flush()
    return user


def add_org(db: Session, name: str, slug: str) -> OrganizationRecord:
    org = OrganizationRecord(name=name, slug=slug)
    db.add(org)
    db.flush()
    return org


def add_membership(
    db: Session,
    org: OrganizationRecord,
    user: UserRecord,
    role: str,
) -> OrganizationMemberRecord:
    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=user.id,
        role=role,
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def test_last_owner_cannot_be_demoted() -> None:
    db = build_db()
    owner = add_user(db, "owner@test.local", "Owner")
    org = add_org(db, "School", "school")
    membership = add_membership(db, org, owner, "owner")
    db.commit()

    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    with pytest.raises(HTTPException) as exc:
        update_member(
            db,
            tenant,
            membership.id,
            OrganizationMemberUpdate(role="admin"),
        )

    assert exc.value.status_code == 409
    assert membership.role == "owner"


def test_owner_can_be_demoted_when_another_active_owner_exists() -> None:
    db = build_db()
    owner_a = add_user(db, "a@test.local", "A")
    owner_b = add_user(db, "b@test.local", "B")
    org = add_org(db, "School", "school")
    membership_a = add_membership(db, org, owner_a, "owner")
    add_membership(db, org, owner_b, "owner")
    db.commit()

    tenant = resolve_tenant_context(db, user=owner_a, organization_id=org.id)
    updated = update_member(
        db,
        tenant,
        membership_a.id,
        OrganizationMemberUpdate(role="admin"),
    )

    assert updated.role == "admin"


def test_admin_cannot_promote_member_to_owner() -> None:
    db = build_db()
    owner = add_user(db, "owner@test.local", "Owner")
    admin = add_user(db, "admin@test.local", "Admin")
    teacher = add_user(db, "teacher@test.local", "Teacher")
    org = add_org(db, "School", "school")
    add_membership(db, org, owner, "owner")
    add_membership(db, org, admin, "admin")
    teacher_member = add_membership(db, org, teacher, "teacher")
    db.commit()

    tenant = resolve_tenant_context(db, user=admin, organization_id=org.id)

    with pytest.raises(HTTPException) as exc:
        update_member(
            db,
            tenant,
            teacher_member.id,
            OrganizationMemberUpdate(role="owner"),
        )

    assert exc.value.status_code == 403


def test_cross_tenant_member_update_is_hidden() -> None:
    db = build_db()
    owner_a = add_user(db, "a@test.local", "A")
    owner_b = add_user(db, "b@test.local", "B")
    org_a = add_org(db, "School A", "school-a")
    org_b = add_org(db, "School B", "school-b")
    add_membership(db, org_a, owner_a, "owner")
    member_b = add_membership(db, org_b, owner_b, "owner")
    db.commit()

    tenant_a = resolve_tenant_context(db, user=owner_a, organization_id=org_a.id)

    with pytest.raises(HTTPException) as exc:
        update_member(
            db,
            tenant_a,
            member_b.id,
            OrganizationMemberUpdate(status="suspended"),
        )

    assert exc.value.status_code == 404


def test_owner_can_update_school_settings() -> None:
    db = build_db()
    owner = add_user(db, "owner@test.local", "Owner")
    org = add_org(db, "School", "school")
    add_membership(db, org, owner, "owner")
    db.commit()

    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    updated = update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(
            name="New School",
            timezone="Africa/Douala",
            locale="fr-CM",
            contact_email="contact@example.com",
        ),
    )

    assert updated.name == "New School"
    assert updated.timezone == "Africa/Douala"
    assert updated.locale == "fr-CM"
    assert updated.contact_email == "contact@example.com"


def test_student_cannot_update_school_settings() -> None:
    db = build_db()
    student = add_user(db, "student@test.local", "Student")
    org = add_org(db, "School", "school")
    add_membership(db, org, student, "student")
    db.commit()

    tenant = resolve_tenant_context(db, user=student, organization_id=org.id)

    with pytest.raises(HTTPException) as exc:
        update_organization_settings(
            db,
            tenant,
            OrganizationUpdate(name="Hacked"),
        )

    assert exc.value.status_code == 403


def test_manager_can_invite_teacher_but_not_admin() -> None:
    db = build_db()
    manager = add_user(db, "manager@test.local", "Manager")
    org = add_org(db, "School", "school")
    add_membership(db, org, manager, "manager")
    db.commit()

    tenant = resolve_tenant_context(db, user=manager, organization_id=org.id)

    invitation, token = create_invitation(
        db,
        tenant,
        OrganizationInvitationCreate(
            email="teacher@example.com",
            role="teacher",
        ),
    )
    assert invitation.role == "teacher"
    assert token

    with pytest.raises(HTTPException) as exc:
        create_invitation(
            db,
            tenant,
            OrganizationInvitationCreate(
                email="admin@example.com",
                role="admin",
            ),
        )

    assert exc.value.status_code == 403


def test_matching_user_can_accept_invitation() -> None:
    db = build_db()
    owner = add_user(db, "owner@test.local", "Owner")
    invited = add_user(db, "teacher@example.com", "Teacher")
    org = add_org(db, "School", "school")
    add_membership(db, org, owner, "owner")
    db.commit()

    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    invitation, token = create_invitation(
        db,
        tenant,
        OrganizationInvitationCreate(
            email="teacher@example.com",
            role="teacher",
        ),
    )

    accepted_org, membership = accept_invitation(
        db,
        current_user=invited,
        token=token,
    )

    assert accepted_org.id == org.id
    assert membership.organization_id == org.id
    assert membership.user_id == invited.id
    assert membership.role == "teacher"
    assert invitation.status == "accepted"


def test_wrong_email_cannot_accept_invitation() -> None:
    db = build_db()
    owner = add_user(db, "owner@test.local", "Owner")
    wrong_user = add_user(db, "wrong@example.com", "Wrong")
    org = add_org(db, "School", "school")
    add_membership(db, org, owner, "owner")
    db.commit()

    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    invitation, token = create_invitation(
        db,
        tenant,
        OrganizationInvitationCreate(
            email="teacher@example.com",
            role="teacher",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        accept_invitation(
            db,
            current_user=wrong_user,
            token=token,
        )

    assert exc.value.status_code == 403
    assert invitation.status == "pending"
