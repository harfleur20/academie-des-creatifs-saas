from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.services.membership_roles import replace_effective_roles
from app.services.tenancy import resolve_tenant_context
from app.services.workspace import get_student_workspace, get_teacher_workspace


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    owner = UserRecord(email="owner@test.dev", full_name="Owner", status="active")
    teacher = UserRecord(email="teacher@test.dev", full_name="Teacher", status="active")
    student = UserRecord(email="student@test.dev", full_name="Student", status="active")
    other_teacher = UserRecord(email="other@test.dev", full_name="Other", status="active")
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([owner, teacher, student, other_teacher, org])
    db.flush()
    db.add(OrganizationPublicSiteRecord(
        organization_id=org.id,
        student_code_prefix="SC",
        student_code_prefix_confirmed_at=datetime.now(UTC),
    ))

    memberships = [
        OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=teacher.id, role="teacher", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=student.id, role="student", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=other_teacher.id, role="teacher", status="active"),
    ]
    db.add_all(memberships)
    db.flush()
    for member in memberships:
        replace_effective_roles(db, member, {member.role})

    formation = FormationRecord(
        organization_id=org.id,
        slug="motion",
        title="Motion Design",
        cover_image_url="https://example.test/motion.jpg",
    )
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=formation.id,
        label="Cohorte Octobre",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 11, 1),
        campus_label="Campus Créatif",
        seat_capacity=25,
        status="open",
    )
    db.add(session)
    db.flush()
    db.add_all([
        SessionTeacherRecord(
            organization_id=org.id,
            session_id=session.id,
            teacher_id=teacher.id,
            role="principal",
        ),
        EnrollmentRecord(
            organization_id=org.id,
            session_id=session.id,
            student_id=student.id,
            status="active",
        ),
        CourseRecord(
            organization_id=org.id,
            session_id=session.id,
            teacher_id=teacher.id,
            title="Bases",
            status="published",
        ),
    ])
    db.commit()
    return org, owner, teacher, student, other_teacher


def test_teacher_workspace_only_contains_assigned_sessions() -> None:
    db = build_db()
    org, _, teacher, _, other_teacher = seed(db)

    tenant = resolve_tenant_context(db, user=teacher, organization_id=org.id)
    workspace = get_teacher_workspace(db, tenant)
    assert workspace.total_sessions == 1
    assert workspace.total_students == 1
    assert workspace.total_courses == 1
    assert workspace.sessions[0].formation_title == "Motion Design"
    assert workspace.sessions[0].format_type == "ligne"
    assert workspace.sessions[0].seat_capacity == 25

    other_tenant = resolve_tenant_context(db, user=other_teacher, organization_id=org.id)
    other_workspace = get_teacher_workspace(db, other_tenant)
    assert other_workspace.total_sessions == 0


def test_student_workspace_only_contains_own_enrollments() -> None:
    db = build_db()
    org, _, _, student, _ = seed(db)

    tenant = resolve_tenant_context(db, user=student, organization_id=org.id)
    workspace = get_student_workspace(db, tenant)
    expected_code = f"SC{datetime.now(UTC):%y}-001"
    assert workspace.student_code == expected_code
    assert workspace.total_sessions == 1
    assert workspace.total_courses == 1
    assert workspace.sessions[0].session_label == "Cohorte Octobre"
    assert workspace.sessions[0].formation_image == "https://example.test/motion.jpg"
    assert workspace.sessions[0].teacher_name == "Teacher"
    assert workspace.sessions[0].campus_label == "Campus Créatif"

    # Legacy student memberships without a commerce profile are repaired once.
    assert get_student_workspace(db, tenant).student_code == expected_code
    profiles = db.scalars(select(OrganizationStudentProfileRecord).where(
        OrganizationStudentProfileRecord.organization_id == org.id,
        OrganizationStudentProfileRecord.user_id == student.id,
    )).all()
    assert len(profiles) == 1


def test_student_workspace_stays_available_until_prefix_is_confirmed() -> None:
    db = build_db()
    org, _, _, student, _ = seed(db)
    site = db.scalar(select(OrganizationPublicSiteRecord).where(
        OrganizationPublicSiteRecord.organization_id == org.id,
    ))
    assert site is not None
    site.student_code_prefix_confirmed_at = None
    db.commit()

    tenant = resolve_tenant_context(db, user=student, organization_id=org.id)
    workspace = get_student_workspace(db, tenant)
    assert workspace.student_code is None
    assert workspace.total_sessions == 1


def test_owner_without_student_role_cannot_open_student_workspace() -> None:
    db = build_db()
    org, owner, _, _, _ = seed(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    with pytest.raises(HTTPException) as exc:
        get_student_workspace(db, tenant)

    assert exc.value.status_code == 403
