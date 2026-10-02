from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.planning import CourseDayCreate, CourseDayUpdate
from app.services.membership_roles import replace_effective_roles
from app.services.planning import (
    create_course_day,
    get_session_planning,
    update_course_day,
)
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    org = OrganizationRecord(name="School", slug="school")
    formation = FormationRecord(
        organization_id=1,
        slug="motion",
        title="Motion Design",
    )
    principal = UserRecord(email="principal@test.dev", full_name="Prof Principal", status="active")
    intervenant = UserRecord(email="inter@test.dev", full_name="Prof Intervenant", status="active")
    student = UserRecord(email="student@test.dev", full_name="Student", status="active")
    outsider = UserRecord(email="outsider@test.dev", full_name="Outsider", status="active")
    db.add_all([org, principal, intervenant, student, outsider])
    db.flush()
    formation.organization_id = org.id
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=formation.id,
        label="Cohorte Octobre",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31),
        status="open",
    )
    db.add(session)
    db.flush()

    members = [
        OrganizationMemberRecord(organization_id=org.id, user_id=principal.id, role="teacher", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=intervenant.id, role="teacher", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=student.id, role="student", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=outsider.id, role="student", status="active"),
    ]
    db.add_all(members)
    db.flush()
    for member in members:
        replace_effective_roles(db, member, {member.role})

    db.add_all([
        SessionTeacherRecord(
            organization_id=org.id,
            session_id=session.id,
            teacher_id=principal.id,
            role="principal",
        ),
        SessionTeacherRecord(
            organization_id=org.id,
            session_id=session.id,
            teacher_id=intervenant.id,
            role="intervenant",
        ),
        EnrollmentRecord(
            organization_id=org.id,
            session_id=session.id,
            student_id=student.id,
            status="active",
        ),
    ])
    db.commit()
    return org, session, principal, intervenant, student, outsider


def context(db: Session, org: OrganizationRecord, user: UserRecord):
    return resolve_tenant_context(db, user=user, organization_id=org.id)


def test_teachers_share_planning_but_only_owner_can_edit() -> None:
    db = build_db()
    org, session, principal, intervenant, _, _ = seed(db)

    principal_tenant = context(db, org, principal)
    intervenant_tenant = context(db, org, intervenant)

    planning = create_course_day(
        db,
        principal_tenant,
        session.id,
        CourseDayCreate(
            title="Cours du principal",
            scheduled_at=datetime(2026, 10, 6, 9, 0, tzinfo=UTC),
            duration_minutes=120,
        ),
    )
    day = planning.course_days[0]
    assert day.teacher_id == principal.id
    assert day.can_edit is True

    shared = get_session_planning(db, intervenant_tenant, session.id)
    assert len(shared.course_days) == 1
    assert shared.course_days[0].teacher_name == "Prof Principal"
    assert shared.course_days[0].can_edit is False

    with pytest.raises(HTTPException) as exc:
        update_course_day(
            db,
            intervenant_tenant,
            day.id,
            CourseDayUpdate(title="Je modifie le cours"),
        )
    assert exc.value.status_code == 403
    assert "appartient" in exc.value.detail


def test_overlap_and_dates_outside_session_are_rejected() -> None:
    db = build_db()
    org, session, principal, _, _, _ = seed(db)
    tenant = context(db, org, principal)

    create_course_day(
        db,
        tenant,
        session.id,
        CourseDayCreate(
            title="Cours A",
            scheduled_at=datetime(2026, 10, 6, 9, 0, tzinfo=UTC),
            duration_minutes=120,
        ),
    )

    with pytest.raises(HTTPException) as overlap:
        create_course_day(
            db,
            tenant,
            session.id,
            CourseDayCreate(
                title="Cours B",
                scheduled_at=datetime(2026, 10, 6, 10, 0, tzinfo=UTC),
                duration_minutes=90,
            ),
        )
    assert overlap.value.status_code == 409

    with pytest.raises(HTTPException) as outside:
        create_course_day(
            db,
            tenant,
            session.id,
            CourseDayCreate(
                title="Cours hors session",
                scheduled_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
                duration_minutes=90,
            ),
        )
    assert outside.value.status_code == 422


def test_student_reads_own_session_planning_only() -> None:
    db = build_db()
    org, session, principal, _, student, outsider = seed(db)
    principal_tenant = context(db, org, principal)

    create_course_day(
        db,
        principal_tenant,
        session.id,
        CourseDayCreate(
            title="Cours visible",
            scheduled_at=datetime(2026, 10, 8, 14, 0, tzinfo=UTC),
            duration_minutes=90,
        ),
    )

    student_planning = get_session_planning(db, context(db, org, student), session.id)
    assert [item.title for item in student_planning.course_days] == ["Cours visible"]
    assert student_planning.course_days[0].can_edit is False

    with pytest.raises(HTTPException) as exc:
        get_session_planning(db, context(db, org, outsider), session.id)
    assert exc.value.status_code == 403
