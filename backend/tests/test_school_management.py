from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    CommunicationOutboxRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    UserRecord,
)
from app.schemas.organizations import (
    OrganizationInvitationCreate,
    OrganizationMemberUpdate,
    OrganizationUpdate,
)
from app.schemas.commerce import SchoolIdentityPayload
from app.services.organization_management import (
    accept_invitation,
    create_invitation,
    get_invitation_preview,
    renew_invitation,
    update_member,
    update_organization_settings,
)
from app.services.school_branding import get_school_identity, update_school_identity
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
    org = OrganizationRecord(name=name, slug=slug, contact_email="contact@test.local", subdomain=slug)
    db.add(org)
    db.flush()
    db.add(OrganizationPublicSiteRecord(
        organization_id=org.id,
        student_code_prefix="SC",
        student_code_prefix_confirmed_at=datetime.now(UTC),
    ))
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


def test_setup_blocks_invitation_until_identity_address_and_matricule_are_confirmed() -> None:
    db = build_db()
    owner = add_user(db, "owner@example.com", "Owner")
    teacher = add_user(db, "teacher@example.com", "Teacher")
    org = OrganizationRecord(name="New School", slug="new-school")
    db.add(org)
    db.flush()
    add_membership(db, org, owner, "owner")
    db.commit()
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    invitation_payload = OrganizationInvitationCreate(email=teacher.email, role="teacher")

    with pytest.raises(HTTPException) as exc:
        create_invitation(db, tenant, invitation_payload)
    assert exc.value.status_code == 409

    identity = get_school_identity(db, tenant)
    assert identity.public_site.student_code_prefix
    assert not identity.public_site.student_code_prefix_confirmed
    confirmation = SchoolIdentityPayload.model_validate(identity.model_dump())
    confirmation.public_site.student_code_prefix_confirmed = True
    with pytest.raises(HTTPException) as exc:
        update_school_identity(db, tenant, confirmation)
    assert exc.value.status_code == 409

    org.contact_email = "contact@example.com"
    org.subdomain = "new-school"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        create_invitation(db, tenant, invitation_payload)
    assert exc.value.status_code == 409

    confirmed = update_school_identity(db, tenant, confirmation)
    assert confirmed.public_site.student_code_prefix_confirmed
    invitation, token = create_invitation(db, tenant, invitation_payload)
    assert invitation.status == "pending"

    site = db.scalar(select(OrganizationPublicSiteRecord).where(OrganizationPublicSiteRecord.organization_id == org.id))
    site.student_code_prefix_confirmed_at = None
    db.commit()
    with pytest.raises(HTTPException) as exc:
        accept_invitation(db, current_user=teacher, token=token)
    assert exc.value.status_code == 409
    assert db.scalar(select(OrganizationMemberRecord).where(
        OrganizationMemberRecord.organization_id == org.id,
        OrganizationMemberRecord.user_id == teacher.id,
    )) is None

    site.student_code_prefix_confirmed_at = datetime.now(UTC)
    db.commit()
    accept_invitation(db, current_user=teacher, token=token)
    changed = SchoolIdentityPayload.model_validate(get_school_identity(db, tenant).model_dump())
    changed.public_site.student_code_prefix = "OTHER"
    with pytest.raises(HTTPException) as exc:
        update_school_identity(db, tenant, changed)
    assert exc.value.status_code == 409


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


def test_pending_teacher_invitation_can_be_renewed_by_its_school() -> None:
    db = build_db()
    manager = add_user(db, "manager@test.local", "Manager")
    outsider = add_user(db, "outsider@test.local", "Outsider")
    org = add_org(db, "School", "school")
    other_org = add_org(db, "Other", "other")
    add_membership(db, org, manager, "manager")
    add_membership(db, other_org, outsider, "owner")
    db.commit()
    tenant = resolve_tenant_context(db, user=manager, organization_id=org.id)
    other_tenant = resolve_tenant_context(db, user=outsider, organization_id=other_org.id)
    invitation, old_token = create_invitation(
        db, tenant, OrganizationInvitationCreate(email="teacher@example.com", role="teacher"),
    )
    original_email = db.scalar(select(CommunicationOutboxRecord).where(CommunicationOutboxRecord.organization_id == org.id))
    assert original_email.status == "pending"

    with pytest.raises(HTTPException) as other_school:
        renew_invitation(db, other_tenant, invitation.id)
    assert other_school.value.status_code == 404

    renewed, new_token = renew_invitation(db, tenant, invitation.id)
    assert renewed.id == invitation.id
    assert new_token != old_token
    assert original_email.status == "superseded"
    with pytest.raises(HTTPException) as old_link:
        get_invitation_preview(db, token=old_token)
    assert old_link.value.status_code == 404
    assert get_invitation_preview(db, token=new_token)["email"] == "teacher@example.com"


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
    with pytest.raises(HTTPException) as used:
        renew_invitation(db, tenant, invitation.id)
    assert used.value.status_code == 409


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
