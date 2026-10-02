from datetime import date

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import OrganizationMemberRecord, OrganizationRecord, UserRecord
from app.schemas.formations import (
    ChapterCreate,
    CourseCreate,
    EnrollmentCreate,
    FormationCreate,
    LessonCreate,
    SessionCreate,
    TeacherAssignmentCreate,
)
from app.services.formations import (
    assign_teacher,
    create_chapter,
    create_course,
    create_formation,
    create_lesson,
    create_session,
    enroll_student,
    get_formation_detail,
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
    owner = UserRecord(email="owner@test.dev", full_name="Owner", status="active")
    teacher = UserRecord(email="teacher@test.dev", full_name="Teacher", status="active")
    student = UserRecord(email="student@test.dev", full_name="Student", status="active")
    outsider = UserRecord(email="outside@test.dev", full_name="Outside", status="active")
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([owner, teacher, student, outsider, org])
    db.flush()
    db.add_all([
        OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=teacher.id, role="teacher", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=student.id, role="student", status="active"),
    ])
    db.commit()
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    return tenant, teacher, student, outsider


def test_full_pedagogical_core_flow_is_tenant_scoped() -> None:
    db = build_db()
    tenant, teacher, student, outsider = seed(db)

    formation = create_formation(
        db,
        tenant,
        FormationCreate(
            slug="motion-design",
            title="Motion Design",
            category="Design",
            level="Intermédiaire",
            format_type="live",
            training_hours=40,
        ),
    )
    detail = create_session(
        db,
        tenant,
        formation.id,
        SessionCreate(
            label="Cohorte Octobre 2026",
            start_date=date(2026, 10, 5),
            end_date=date(2026, 11, 5),
            seat_capacity=20,
        ),
    )
    session_id = detail.sessions[0].id

    detail = assign_teacher(
        db,
        tenant,
        formation.id,
        session_id,
        TeacherAssignmentCreate(user_id=teacher.id, role="principal"),
    )
    detail = enroll_student(
        db,
        tenant,
        formation.id,
        session_id,
        EnrollmentCreate(user_id=student.id),
    )
    detail = create_course(
        db,
        tenant,
        formation.id,
        session_id,
        CourseCreate(title="Bases du motion design", teacher_id=teacher.id),
    )
    course_id = detail.sessions[0].courses[0].id
    detail = create_chapter(
        db,
        tenant,
        formation.id,
        session_id,
        course_id,
        ChapterCreate(title="Module 1", order_index=0),
    )
    chapter_id = detail.sessions[0].courses[0].chapters[0].id
    detail = create_lesson(
        db,
        tenant,
        formation.id,
        session_id,
        course_id,
        chapter_id,
        LessonCreate(
            title="Introduction",
            order_index=0,
            lesson_type="text",
            content="Bienvenue dans le cours.",
        ),
    )

    assert detail.teacher_count == 1
    assert detail.student_count == 1
    assert detail.course_count == 1
    assert detail.sessions[0].teachers[0].teacher_id == teacher.id
    assert detail.sessions[0].enrollments[0].student_id == student.id
    assert detail.sessions[0].courses[0].chapters[0].lessons[0].title == "Introduction"

    try:
        assign_teacher(
            db,
            tenant,
            formation.id,
            session_id,
            TeacherAssignmentCreate(user_id=outsider.id, role="intervenant"),
        )
        assert False, "outsider teacher assignment should have failed"
    except HTTPException as exc:
        assert exc.status_code == 409


def test_capacity_is_enforced() -> None:
    db = build_db()
    tenant, teacher, student, _ = seed(db)
    second_student = UserRecord(
        email="student2@test.dev",
        full_name="Student Two",
        status="active",
    )
    db.add(second_student)
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=tenant.organization_id,
            user_id=second_student.id,
            role="student",
            status="active",
        )
    )
    db.commit()

    formation = create_formation(
        db,
        tenant,
        FormationCreate(slug="small", title="Small formation"),
    )
    detail = create_session(
        db,
        tenant,
        formation.id,
        SessionCreate(
            label="Session",
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 6),
            seat_capacity=1,
        ),
    )
    session_id = detail.sessions[0].id
    enroll_student(db, tenant, formation.id, session_id, EnrollmentCreate(user_id=student.id))

    try:
        enroll_student(
            db,
            tenant,
            formation.id,
            session_id,
            EnrollmentCreate(user_id=second_student.id),
        )
        assert False, "capacity should have blocked enrollment"
    except HTTPException as exc:
        assert exc.status_code == 409



def test_teacher_formation_detail_hides_unassigned_sibling_session() -> None:
    db = build_db()
    org, manager, teacher, student, other_teacher, formation, session = seed(db)

    sibling = FormationSessionRecord(
        organization_id=org.id,
        formation_id=formation.id,
        label="Cohorte privée",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 12, 1),
        status="open",
    )
    db.add(sibling)
    db.flush()
    db.add(
        SessionTeacherRecord(
            organization_id=org.id,
            session_id=sibling.id,
            teacher_id=other_teacher.id,
            role="principal",
        )
    )
    db.commit()

    tenant = resolve_tenant_context(db, user=teacher, organization_id=org.id)
    detail = get_formation_detail(db, tenant, formation.id)

    assert detail is not None
    assert [item.id for item in detail.sessions] == [session.id]
    assert detail.session_count == 1
