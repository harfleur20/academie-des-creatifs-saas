import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from program_helpers import frozen_program
from app.api.dependencies import get_tenant_context
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    ChapterRecord,
    CommunicationOutboxRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    LessonRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.assignments import AssignmentCreate, AssignmentSubmit, AssignmentUpdate, CommentCreate
from app.schemas.formations import CourseUpdate, LessonCreate
from app.services.assets import store_submission_asset
from app.services.assignments import (
    add_comment,
    create_assignment,
    delete_assignment,
    list_comments,
    list_student_assignments,
    list_teacher_assignments,
    publish_assignment,
    submit_assignment,
    update_assignment,
)
from app.services.formations import publish_lesson, update_course, update_lesson
from app.services.learning_progress import badge_for_enrollment, progress_for_enrollment
from app.services.membership_roles import replace_effective_roles
from app.services.school_pedagogy import school_pedagogy_overview
from app.services.tenancy import resolve_tenant_context


CREATED = "student.assignment.created"
UPDATED = "student.assignment.updated"


def days_from_now(days):
    return datetime.now(UTC) + timedelta(days=days)


def member(db, org, email, role):
    user = UserRecord(email=email, full_name=email.split("@")[0], status="active")
    db.add(user)
    db.flush()
    record = OrganizationMemberRecord(organization_id=org.id, user_id=user.id, role=role, status="active")
    db.add(record)
    db.flush()
    replace_effective_roles(db, record, {role})
    return user


def school(format_type="live"):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org = OrganizationRecord(name="School", slug="school")
    db.add(org)
    db.flush()
    teacher = member(db, org, "teacher@school.test", "teacher")
    student = member(db, org, "student@school.test", "student")
    formation = FormationRecord(organization_id=org.id, slug="f", title="F", format_type=format_type)
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(
        organization_id=org.id, formation_id=formation.id, label="Cohorte",
        start_date=days_from_now(-10).date(), end_date=days_from_now(30).date(), status="open",
    )
    db.add(session)
    db.flush()
    db.add(frozen_program(session))
    enrollment = EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=student.id, status="active")
    db.add_all([
        enrollment,
        SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, role="principal"),
    ])
    db.commit()
    return db, org, teacher, student, session, enrollment


def tenant_for(db, org, user):
    return resolve_tenant_context(db, user=user, organization_id=org.id)


def draft(db, org, teacher, session, *, days=5, **values):
    payload = AssignmentCreate(**{"title": "Projet", "due_date": days_from_now(days), **values})
    return create_assignment(db, tenant_for(db, org, teacher), session.id, payload)


def sent_events(db, event_key):
    return db.scalars(select(CommunicationOutboxRecord).where(CommunicationOutboxRecord.event_key == event_key)).all()


def teaching_outline(db, org, teacher, session, assignment_id, *, course_status="draft", lesson_status="draft"):
    course = CourseRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Cours", status=course_status,
    )
    db.add(course)
    db.flush()
    chapter = ChapterRecord(organization_id=org.id, course_id=course.id, title="Module")
    db.add(chapter)
    db.flush()
    lesson = LessonRecord(
        organization_id=org.id, chapter_id=chapter.id, title="Remettre le TP", lesson_type="assignment",
        assignment_id=assignment_id, publication_status=lesson_status,
    )
    db.add(lesson)
    db.commit()
    return course, chapter, lesson


def lesson_payload(lesson, assignment_id):
    return LessonCreate(title=lesson.title, lesson_type="assignment", assignment_id=assignment_id)


def real_file(org, student):
    """Store a real submission file and return its URL with the path to clean up."""
    asset = asyncio.run(store_submission_asset(UploadFile(file=BytesIO(b"work"), filename="work.pdf"), org.id, student.id))
    url = asset["public_url"]
    root = Path(__file__).resolve().parents[1] / "private_uploads" / "schools"
    return url, root / str(org.id) / "assignments" / str(student.id) / url.rsplit("/", 1)[-1]


def test_new_assignment_stays_a_draft_hidden_from_students():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    assert created.publication_status == "draft"
    assert [item.publication_status for item in list_teacher_assignments(db, tenant_for(db, org, teacher), session.id)] == ["draft"]
    assert list_student_assignments(db, tenant_for(db, org, student)) == []
    assert sent_events(db, CREATED) == []


def test_students_are_told_once_when_the_assignment_is_published():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    tenant = tenant_for(db, org, teacher)
    assert publish_assignment(db, tenant, created.id).publication_status == "published"
    publish_assignment(db, tenant, created.id)
    assert [item.id for item in list_student_assignments(db, tenant_for(db, org, student))] == [created.id]
    assert [item.recipient for item in sent_events(db, CREATED)] == [student.email]


def test_existing_records_default_to_published():
    db, org, teacher, student, session, _enrollment = school()
    db.add(AssignmentRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Ancien", due_date=days_from_now(3),
    ))
    db.commit()
    assert [item.title for item in list_student_assignments(db, tenant_for(db, org, student))] == ["Ancien"]


def test_student_cannot_reach_a_draft():
    db, org, teacher, student, session, enrollment = school()
    created = draft(db, org, teacher, session)
    tenant = tenant_for(db, org, student)
    for action in (
        lambda: submit_assignment(db, tenant, created.id, AssignmentSubmit(file_url="x")),
        lambda: list_comments(db, tenant, created.id, enrollment.id),
        lambda: add_comment(db, tenant, created.id, enrollment.id, CommentCreate(body="Bonjour")),
    ):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 404


def test_draft_counts_nowhere_for_the_student():
    db, org, teacher, student, session, enrollment = school()
    overdue = draft(db, org, teacher, session, days=-1, is_final_project=False)
    tenant = tenant_for(db, org, student)
    assert badge_for_enrollment(db, tenant, enrollment).assignment_progress_pct is None
    assert progress_for_enrollment(db, tenant, enrollment).total_assignments == 0

    owner = member(db, org, "owner@school.test", "owner")
    db.commit()
    [row] = school_pedagogy_overview(db, tenant_for(db, org, owner)).students
    assert not [reason for reason in row.alert_reasons if "devoir" in reason]

    publish_assignment(db, tenant_for(db, org, teacher), overdue.id)
    assert badge_for_enrollment(db, tenant, enrollment).assignment_progress_pct == 0.0
    assert progress_for_enrollment(db, tenant, enrollment).total_assignments == 1
    [row] = school_pedagogy_overview(db, tenant_for(db, org, owner)).students
    assert "1 devoir(s) en retard" in row.alert_reasons


def test_late_submission_is_accepted_and_keeps_its_real_date():
    db, org, teacher, student, session, enrollment = school()
    created = draft(db, org, teacher, session, days=-1)
    publish_assignment(db, tenant_for(db, org, teacher), created.id)
    tenant = tenant_for(db, org, student)
    assert list_student_assignments(db, tenant)[0].student_status == "late"

    url, path = real_file(org, student)
    before = datetime.now(UTC)
    try:
        submitted = submit_assignment(db, tenant, created.id, AssignmentSubmit(file_url=url))
    finally:
        path.unlink(missing_ok=True)
    assert submitted.student_status == "submitted"
    saved = db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.enrollment_id == enrollment.id))
    assert saved.submitted_at.replace(tzinfo=UTC) >= before


def test_late_submission_stays_closed_when_the_session_is_cancelled():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session, days=-1)
    publish_assignment(db, tenant_for(db, org, teacher), created.id)
    session.status = "cancelled"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        submit_assignment(db, tenant_for(db, org, student), created.id, AssignmentSubmit(file_url="x"))
    assert exc.value.status_code == 409


def test_publishing_a_lesson_publishes_its_assignment():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    course, chapter, lesson = teaching_outline(db, org, teacher, session, created.id, course_status="published")
    publish_lesson(db, tenant_for(db, org, teacher), session.formation_id, session.id, course.id, chapter.id, lesson.id)
    assert [item.id for item in list_student_assignments(db, tenant_for(db, org, student))] == [created.id]
    assert len(sent_events(db, CREATED)) == 1


def test_publishing_a_course_publishes_the_assignments_of_its_lessons():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    course, _chapter, _lesson = teaching_outline(db, org, teacher, session, created.id)
    update_course(
        db, tenant_for(db, org, teacher), session.formation_id, session.id, course.id, CourseUpdate(status="published"),
    )
    assert [item.id for item in list_student_assignments(db, tenant_for(db, org, student))] == [created.id]
    assert len(sent_events(db, CREATED)) == 1


def test_linking_a_draft_to_a_published_lesson_publishes_it():
    db, org, teacher, student, session, _enrollment = school()
    first = draft(db, org, teacher, session, title="Premier")
    second = draft(db, org, teacher, session, title="Second")
    publish_assignment(db, tenant_for(db, org, teacher), first.id)
    course, chapter, lesson = teaching_outline(
        db, org, teacher, session, first.id, course_status="published", lesson_status="published",
    )
    update_lesson(
        db, tenant_for(db, org, teacher), session.formation_id, session.id, course.id, chapter.id, lesson.id,
        lesson_payload(lesson, second.id),
    )
    assert second.id in [item.id for item in list_student_assignments(db, tenant_for(db, org, student))]


def test_linking_a_draft_to_a_draft_lesson_keeps_it_hidden():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    course, chapter, lesson = teaching_outline(db, org, teacher, session, created.id)
    update_lesson(
        db, tenant_for(db, org, teacher), session.formation_id, session.id, course.id, chapter.id, lesson.id,
        lesson_payload(lesson, created.id),
    )
    assert list_student_assignments(db, tenant_for(db, org, student)) == []


def test_teacher_edits_a_draft_without_telling_students():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    updated = update_assignment(
        db, tenant_for(db, org, teacher), created.id,
        AssignmentUpdate(title=" Nouveau ", instructions="Consignes", due_date=days_from_now(8), is_final_project=True),
    )
    assert (updated.title, updated.instructions, updated.is_final_project) == ("Nouveau", "Consignes", True)
    assert updated.publication_status == "draft"
    assert sent_events(db, UPDATED) == []


def test_students_are_told_when_a_published_assignment_changes():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    tenant = tenant_for(db, org, teacher)
    publish_assignment(db, tenant, created.id)
    update_assignment(db, tenant, created.id, AssignmentUpdate(title="Projet"))
    assert sent_events(db, UPDATED) == []
    update_assignment(db, tenant, created.id, AssignmentUpdate(due_date=days_from_now(9)))
    assert [item.recipient for item in sent_events(db, UPDATED)] == [student.email]


@pytest.mark.parametrize("days", [-40, 60])
def test_update_keeps_the_deadline_inside_the_session(days):
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    with pytest.raises(HTTPException) as exc:
        update_assignment(db, tenant_for(db, org, teacher), created.id, AssignmentUpdate(due_date=days_from_now(days)))
    assert exc.value.status_code == 422


def test_update_checks_the_course_day():
    db, org, teacher, _student, session, _enrollment = school()
    colleague = member(db, org, "colleague@school.test", "teacher")
    db.add(SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=colleague.id, role="intervenant"))
    mine = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Mien",
        scheduled_at=days_from_now(7), duration_minutes=90,
    )
    theirs = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=colleague.id, title="Autre",
        scheduled_at=days_from_now(1), duration_minutes=90,
    )
    db.add_all([mine, theirs])
    db.commit()
    created = draft(db, org, teacher, session)
    tenant = tenant_for(db, org, teacher)

    with pytest.raises(HTTPException) as forbidden:
        update_assignment(db, tenant, created.id, AssignmentUpdate(course_day_id=theirs.id))
    assert forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as too_early:
        update_assignment(db, tenant, created.id, AssignmentUpdate(course_day_id=mine.id))
    assert too_early.value.status_code == 422

    moved = update_assignment(db, tenant, created.id, AssignmentUpdate(course_day_id=mine.id, due_date=days_from_now(9)))
    assert moved.course_day_id == mine.id
    assert update_assignment(db, tenant, created.id, AssignmentUpdate(course_day_id=None)).course_day_id is None


def test_editing_the_text_ignores_a_deadline_left_outside_the_session():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    session.end_date = days_from_now(1).date()
    db.commit()
    updated = update_assignment(db, tenant_for(db, org, teacher), created.id, AssignmentUpdate(title="Corrigé"))
    assert updated.title == "Corrigé"


def test_only_the_owner_manages_an_assignment():
    db, org, teacher, _student, session, _enrollment = school()
    colleague = member(db, org, "colleague@school.test", "teacher")
    db.add(SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=colleague.id, role="intervenant"))
    db.commit()
    created = draft(db, org, teacher, session)
    tenant = tenant_for(db, org, colleague)
    assert [item.can_manage for item in list_teacher_assignments(db, tenant, session.id)] == [False]
    for action in (
        lambda: publish_assignment(db, tenant, created.id),
        lambda: update_assignment(db, tenant, created.id, AssignmentUpdate(title="Volé")),
        lambda: delete_assignment(db, tenant, created.id),
    ):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 403
    assert [item.can_manage for item in list_teacher_assignments(db, tenant_for(db, org, teacher), session.id)] == [True]


def test_support_mode_cannot_manage_an_assignment():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    tenant = replace(tenant_for(db, org, teacher), support_mode=True)
    assert [item.can_manage for item in list_teacher_assignments(db, tenant, session.id)] == [False]
    with pytest.raises(HTTPException) as exc:
        publish_assignment(db, tenant, created.id)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("status", ["cancelled", "completed"])
def test_closed_session_refuses_a_new_publication(status):
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    session.status = status
    db.commit()
    with pytest.raises(HTTPException) as exc:
        publish_assignment(db, tenant_for(db, org, teacher), created.id)
    assert exc.value.status_code == 409
    assert sent_events(db, CREATED) == []


def test_teacher_deletes_a_free_assignment():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    delete_assignment(db, tenant_for(db, org, teacher), created.id)
    assert db.scalars(select(AssignmentRecord)).all() == []


def test_assignment_linked_to_a_lesson_cannot_be_deleted():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    teaching_outline(db, org, teacher, session, created.id)
    tenant = tenant_for(db, org, teacher)
    assert list_teacher_assignments(db, tenant, session.id)[0].delete_blocked_reason is not None
    with pytest.raises(HTTPException) as exc:
        delete_assignment(db, tenant, created.id)
    assert exc.value.status_code == 409


def test_assignment_with_submitted_work_cannot_be_deleted():
    db, org, teacher, _student, session, enrollment = school()
    created = draft(db, org, teacher, session)
    db.add(AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=created.id, enrollment_id=enrollment.id,
        file_url="https://files.test/work.pdf", submitted_at=datetime.now(UTC),
    ))
    db.commit()
    tenant = tenant_for(db, org, teacher)
    assert list_teacher_assignments(db, tenant, session.id)[0].delete_blocked_reason is not None
    with pytest.raises(HTTPException) as exc:
        delete_assignment(db, tenant, created.id)
    assert exc.value.status_code == 409


def test_assignment_api_round_trip():
    db, org, teacher, _student, session, _enrollment = school()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_tenant_context] = lambda: tenant_for(db, org, teacher)
    try:
        client = TestClient(app)
        created = client.post(
            f"/api/v1/assignments/teacher/sessions/{session.id}",
            json={"title": "Projet", "due_date": days_from_now(5).isoformat()},
        ).json()
        url = f"/api/v1/assignments/teacher/{created['id']}"
        edited = client.patch(url, json={"title": "Projet final"})
        refused = client.patch(url, json={"title": "x"})
        published = client.post(f"{url}/publish")
        deleted = client.delete(url)
        gone = client.get(f"/api/v1/assignments/teacher/sessions/{session.id}")
    finally:
        app.dependency_overrides.clear()
    assert created["publication_status"] == "draft"
    assert created["can_manage"] is True
    assert edited.json()["title"] == "Projet final"
    assert refused.status_code == 422
    assert published.json()["publication_status"] == "published"
    assert deleted.status_code == 204
    assert gone.json() == []
