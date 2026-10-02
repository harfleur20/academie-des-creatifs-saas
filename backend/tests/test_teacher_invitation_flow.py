from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    CommunicationOutboxRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    OrganizationTeacherProfileRecord,
    UserRecord,
)
from app.schemas.organizations import OrganizationInvitationCreate
from app.services.membership_roles import replace_effective_roles
from app.services.organization_management import (
    accept_invitation,
    create_invitation,
    get_invitation_preview,
)
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_teacher_invitation_is_branded_and_creates_teacher_profile() -> None:
    db = build_db()
    org = OrganizationRecord(name="School Business", slug="school-business")
    owner = UserRecord(
        email="owner@test.dev",
        full_name="Owner",
        status="active",
    )
    teacher = UserRecord(
        email="teacher@test.dev",
        full_name="Teacher",
        status="active",
    )
    db.add_all([org, owner, teacher])
    db.flush()
    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=owner.id,
        role="owner",
        status="active",
    )
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"owner"})
    db.commit()

    tenant = resolve_tenant_context(
        db,
        user=owner,
        organization_id=org.id,
    )
    invitation, token = create_invitation(
        db,
        tenant,
        OrganizationInvitationCreate(
            email=teacher.email,
            role="teacher",
        ),
    )

    message = db.scalar(
        select(CommunicationOutboxRecord).where(
            CommunicationOutboxRecord.organization_id == org.id,
            CommunicationOutboxRecord.event_key == "school.team.invitation",
        )
    )
    assert message is not None
    assert message.recipient == teacher.email
    assert "School Business" in (message.subject or "")
    assert f"/invite/{token}" in message.body

    preview = get_invitation_preview(db, token=token)
    assert preview["organization_name"] == "School Business"
    assert preview["role"] == "teacher"

    organization, membership = accept_invitation(
        db,
        current_user=teacher,
        token=token,
    )
    assert organization.id == org.id
    assert membership.role == "teacher"
    profile = db.scalar(
        select(OrganizationTeacherProfileRecord).where(
            OrganizationTeacherProfileRecord.organization_id == org.id,
            OrganizationTeacherProfileRecord.user_id == teacher.id,
        )
    )
    assert profile is not None
    assert profile.teacher_code.startswith("SC-P")
