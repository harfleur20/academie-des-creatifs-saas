from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import asyncio

import pytest
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, UploadFile
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.core.config import settings
from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    CertificateRecord,
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    LessonRecord,
    LessonVersionRecord,
    LessonProgressRecord,
    LessonPdfProgressRecord,
    LessonVideoProgressRecord,
    QuizAttemptRecord,
    QuizRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    ResourceRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    SchoolNotificationRecord,
    UserRecord,
)
from app.schemas.academic import (
    AttendanceMarkPayload,
    LessonVideoHeartbeatPayload,
    DiscussionCreate,
    QuizAttemptPayload,
    QuizCreate,
    QuizQuestionCreate,
    ResourceCreate,
)
from app.schemas.assignments import AssignmentCreate, AssignmentSubmit
from app.schemas.formations import CourseUpdate, EnrollmentUpdate, LessonCreate
from app.schemas.planning import CourseDayFeedbackSubmit, CourseDayReportSubmit, CourseDayUpdate
from app.services.assignments import create_assignment, list_student_assignments, submit_assignment
from app.services.class_certificates import (
    certificate_eligibility,
    create_discussion_post,
    discussion_posts,
    issue_certificate,
    list_student_classes,
    verify_certificate_token,
)
from app.services.school_documents import build_certificate_pdf
from app.services.learning_progress import (
    list_student_learning,
    mark_attendance,
    mark_lesson_complete,
    student_attendance,
    student_grades,
    student_progress,
    sync_lesson_video_progress,
    teacher_performance,
)
from app.services.live_classes import join_live_class, start_live_class
from app.services.planning import get_session_planning, list_course_day_feedback, list_school_course_day_reports, submit_course_day_feedback, submit_course_day_report, update_course_day
from app.services.formations import create_lesson, list_lesson_versions, publish_lesson, restore_lesson_version, update_course, update_enrollment, update_lesson
from app.services.pdf_lessons import pdf_bytes, read_pdf_progress, report_pdf_page, store_pdf_asset
from app.services.membership_roles import replace_effective_roles
from app.services.pedagogy_access import session_ends_at
from app.services.resources_quizzes import (
    create_quiz,
    create_resource,
    list_student_quizzes,
    list_student_resources,
    set_quiz_status,
    submit_quiz_attempt,
    teacher_quiz_results,
)
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
    org = OrganizationRecord(name="School", slug="school")
    teacher = UserRecord(email="teacher@test.dev", full_name="Teacher", status="active")
    student = UserRecord(email="student@test.dev", full_name="Student", status="active")
    classmate = UserRecord(email="mate@test.dev", full_name="Classmate", status="active")
    db.add_all([org, teacher, student, classmate])
    db.flush()
    db.add(OrganizationPublicSiteRecord(
        organization_id=org.id,
        student_code_prefix="SC",
        student_code_prefix_confirmed_at=datetime.now(UTC),
    ))

    members = [
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=teacher.id,
            role="teacher",
            status="active",
        ),
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=student.id,
            role="student",
            status="active",
        ),
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=classmate.id,
            role="student",
            status="active",
        ),
    ]
    db.add_all(members)
    db.flush()
    for member in members:
        replace_effective_roles(db, member, {member.role})

    formation = FormationRecord(
        organization_id=org.id,
        slug="motion",
        title="Motion Design",
        format_type="ligne",
    )
    db.add(formation)
    db.flush()

    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=formation.id,
        label="Cohorte 2025",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 2, 1),
        status="open",
    )
    db.add(session)
    db.flush()

    db.add(
        SessionTeacherRecord(
            organization_id=org.id,
            session_id=session.id,
            teacher_id=teacher.id,
            role="principal",
        )
    )
    student_enrollment = EnrollmentRecord(
        organization_id=org.id,
        session_id=session.id,
        student_id=student.id,
        status="active",
    )
    classmate_enrollment = EnrollmentRecord(
        organization_id=org.id,
        session_id=session.id,
        student_id=classmate.id,
        status="active",
    )
    db.add_all([student_enrollment, classmate_enrollment])
    db.flush()

    course = CourseRecord(
        organization_id=org.id,
        session_id=session.id,
        teacher_id=teacher.id,
        title="Bases",
        status="published",
    )
    db.add(course)
    db.flush()
    chapter = ChapterRecord(
        organization_id=org.id,
        course_id=course.id,
        title="Module 1",
        order_index=0,
    )
    db.add(chapter)
    db.flush()
    lesson = LessonRecord(
        organization_id=org.id,
        chapter_id=chapter.id,
        title="Introduction",
        order_index=0,
        lesson_type="text",
        content="Contenu",
    )
    db.add(lesson)

    day = SessionCourseDayRecord(
        organization_id=org.id,
        session_id=session.id,
        teacher_id=teacher.id,
        title="Cours 1",
        scheduled_at=datetime(2025, 1, 10, 9, 0, tzinfo=UTC),
        duration_minutes=120,
        status="planned",
    )
    db.add(day)
    db.commit()
    return org, teacher, student, classmate, session, student_enrollment, classmate_enrollment, lesson, day


def ctx(db: Session, org: OrganizationRecord, user: UserRecord):
    return resolve_tenant_context(db, user=user, organization_id=org.id)


def test_resources_are_published_to_enrolled_students() -> None:
    db = build_db()
    org, teacher, student, classmate, session, *_ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)

    created = create_resource(
        db,
        teacher_tenant,
        session.id,
        ResourceCreate(
            title="Support PDF",
            resource_type="pdf",
            url="https://files.test/support.pdf",
        ),
    )
    assert created.teacher_name == "Teacher"
    assert {row.user_id for row in db.scalars(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == org.id,
        SchoolNotificationRecord.event_key == f"resource.published:{created.id}",
    )).all()} == {student.id, classmate.id}

    rows = list_student_resources(db, student_tenant)
    assert [item.title for item in rows] == ["Support PDF"]


def test_quiz_attempt_creates_grade_and_teacher_result() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, *_ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)

    quiz = create_quiz(
        db,
        teacher_tenant,
        session.id,
        QuizCreate(
            title="Quiz 1",
            assessment_type="quiz",
            questions=[
                QuizQuestionCreate(
                    text="2 + 2 ?",
                    options=["3", "4", "5"],
                    correct_index=1,
                )
            ],
        ),
    )
    set_quiz_status(db, teacher_tenant, quiz.id, "active")
    assert db.scalar(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == org.id,
        SchoolNotificationRecord.user_id == student.id,
        SchoolNotificationRecord.event_key == f"quiz.published:{quiz.id}",
    )) is not None

    student_quiz = list_student_quizzes(db, student_tenant)[0]
    assert student_quiz.questions[0].options == ["3", "4", "5"]
    assert student_quiz.can_attempt is True

    updated = submit_quiz_attempt(
        db,
        student_tenant,
        quiz.id,
        QuizAttemptPayload(answers=[1]),
    )
    assert updated.best_score_pct == 100
    assert updated.passed is True
    assert updated.can_attempt is False

    grade = db.scalar(
        select(GradeRecord).where(
            GradeRecord.enrollment_id == enrollment.id,
            GradeRecord.source_type == "quiz",
            GradeRecord.source_id == quiz.id,
        )
    )
    assert grade is not None
    assert grade.score == 20

    results = teacher_quiz_results(db, teacher_tenant, quiz.id)
    assert results.total_students == 2
    assert results.attempts[0].student_name == "Student"


def test_linked_quiz_lesson_opens_on_schedule_and_completes_after_success() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, existing_lesson, _ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    quiz = create_quiz(db, teacher_tenant, session.id, QuizCreate(
        title="Validation", questions=[QuizQuestionCreate(text="Bonne réponse ?", options=["Non", "Oui"], correct_index=1)],
    ))
    set_quiz_status(db, teacher_tenant, quiz.id, "active")
    chapter = db.get(ChapterRecord, existing_lesson.chapter_id)
    course = db.get(CourseRecord, chapter.course_id)
    detail = create_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, LessonCreate(
        title="Évaluation du module", lesson_type="quiz", quiz_id=quiz.id,
        available_at=datetime(2099, 1, 1, tzinfo=UTC),
    ))
    linked_id = detail.sessions[0].courses[0].chapters[0].lessons[-1].id
    assert student_progress(db, student_tenant)[0].total_quizzes == 0
    publish_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, linked_id)
    assert student_progress(db, student_tenant)[0].total_quizzes == 1
    lesson_view = list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons[-1]
    assert lesson_view.is_locked and lesson_view.quiz_id == quiz.id
    assert list_student_quizzes(db, student_tenant)[0].questions == []
    with pytest.raises(HTTPException) as early:
        submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[1]))
    assert early.value.status_code == 409

    db.get(LessonRecord, linked_id).available_at = datetime(2025, 1, 1, tzinfo=UTC)
    db.commit()
    assert not list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons[-1].is_locked
    with pytest.raises(HTTPException) as manual:
        mark_lesson_complete(db, student_tenant, linked_id)
    assert manual.value.status_code == 400
    submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[0]))
    second = submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[0]))
    assert second.can_attempt is False
    assert second.next_attempt_available_at is not None
    with pytest.raises(HTTPException) as retry:
        submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[1]))
    assert retry.value.status_code == 409
    attempt = db.scalar(select(QuizAttemptRecord).where(
        QuizAttemptRecord.quiz_id == quiz.id, QuizAttemptRecord.enrollment_id == enrollment.id,
        QuizAttemptRecord.attempt_number == 2,
    ))
    attempt.submitted_at = datetime.now(UTC) - timedelta(hours=9)
    db.commit()
    passed = submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[1]))
    assert passed.passed and passed.attempts_remaining == 0
    assert list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons[-1].completed
    assert db.scalar(select(LessonProgressRecord).where(
        LessonProgressRecord.enrollment_id == enrollment.id, LessonProgressRecord.lesson_id == linked_id,
    )) is not None


def test_lesson_rejects_activity_from_another_school() -> None:
    db = build_db()
    org, teacher, _, _, session, _, _, lesson, _ = seed(db)
    other_org = OrganizationRecord(name="Another", slug="another")
    db.add(other_org)
    db.flush()
    other_formation = FormationRecord(organization_id=other_org.id, slug="other", title="Other")
    db.add(other_formation)
    db.flush()
    other_session = FormationSessionRecord(
        organization_id=other_org.id, formation_id=other_formation.id,
        label="Other", start_date=date(2025, 1, 1), end_date=date(2025, 2, 1), status="open",
    )
    db.add(other_session)
    db.flush()
    foreign_quiz = QuizRecord(organization_id=other_org.id, session_id=other_session.id, title="Foreign")
    db.add(foreign_quiz)
    db.commit()
    chapter = db.get(ChapterRecord, lesson.chapter_id)
    course = db.get(CourseRecord, chapter.course_id)
    with pytest.raises(HTTPException) as error:
        create_lesson(db, ctx(db, org, teacher), session.formation_id, session.id, course.id, chapter.id, LessonCreate(
            title="Lien étranger", lesson_type="quiz", quiz_id=foreign_quiz.id,
        ))
    assert error.value.status_code == 422


def test_lesson_draft_edit_publication_and_progress_reset() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, first_lesson, _ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    chapter = db.get(ChapterRecord, first_lesson.chapter_id)
    course = db.get(CourseRecord, chapter.course_id)
    detail = create_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, LessonCreate(title="Seconde leçon"))
    lesson_id = detail.sessions[0].courses[0].chapters[0].lessons[-1].id
    assert detail.sessions[0].courses[0].chapters[0].lessons[-1].publication_status == "draft"
    assert [item.id for item in list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons] == [first_lesson.id]
    with pytest.raises(HTTPException) as hidden:
        mark_lesson_complete(db, student_tenant, lesson_id)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as incomplete:
        publish_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id)
    assert incomplete.value.status_code == 422

    update_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id, LessonCreate(title="Seconde leçon", content="Premier contenu"))
    publish_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id)
    assert list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons[-1].id == lesson_id
    mark_lesson_complete(db, student_tenant, lesson_id)
    assert db.scalar(select(LessonProgressRecord).where(LessonProgressRecord.enrollment_id == enrollment.id, LessonProgressRecord.lesson_id == lesson_id)) is not None

    with pytest.raises(HTTPException) as empty_published:
        update_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id, LessonCreate(title="Seconde leçon", content=""))
    assert empty_published.value.status_code == 422
    assert db.get(LessonRecord, lesson_id).content == "Premier contenu"

    update_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id, LessonCreate(title="Seconde leçon", lesson_type="video", video_url="https://example.org/video"))
    assert db.scalar(select(LessonProgressRecord).where(LessonProgressRecord.enrollment_id == enrollment.id, LessonProgressRecord.lesson_id == lesson_id)) is None
    with pytest.raises(HTTPException) as wrong_scope:
        update_lesson(db, teacher_tenant, session.formation_id + 1, session.id, course.id, chapter.id, lesson_id, LessonCreate(title="Intruse", content="Autre"))
    assert wrong_scope.value.status_code == 404


def test_lesson_versions_restore_content_and_keep_school_boundary() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, _ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    chapter = db.get(ChapterRecord, lesson.chapter_id)
    course = db.get(CourseRecord, chapter.course_id)
    ids = (session.formation_id, session.id, course.id, chapter.id, lesson.id)

    update_lesson(db, teacher_tenant, *ids, LessonCreate(title="Introduction v2", content="Nouveau contenu"))
    assert [(row.version_number, row.snapshot["title"]) for row in list_lesson_versions(db, teacher_tenant, *ids)] == [
        (2, "Introduction v2"), (1, "Introduction"),
    ]
    mark_lesson_complete(db, ctx(db, org, student), lesson.id)
    restore_lesson_version(db, teacher_tenant, *ids, 1)
    assert db.get(LessonRecord, lesson.id).version_number == 3
    assert db.get(LessonRecord, lesson.id).content == "Contenu"
    assert db.scalar(select(LessonProgressRecord).where(
        LessonProgressRecord.enrollment_id == enrollment.id,
        LessonProgressRecord.lesson_id == lesson.id,
    )) is not None
    assert list_lesson_versions(db, teacher_tenant, *ids)[0].reason == "restored"
    assert db.scalar(select(LessonVersionRecord).where(LessonVersionRecord.lesson_id == lesson.id).order_by(LessonVersionRecord.version_number.desc())).version_number == 3

    other_school = OrganizationRecord(name="Other", slug="other")
    db.add(other_school)
    db.flush()
    member = OrganizationMemberRecord(organization_id=other_school.id, user_id=teacher.id, role="teacher", status="active")
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"teacher"})
    db.commit()
    with pytest.raises(HTTPException) as hidden:
        list_lesson_versions(db, ctx(db, other_school, teacher), *ids)
    assert hidden.value.status_code == 404


def test_live_class_join_requires_own_school_membership_and_course_window(monkeypatch) -> None:
    db = build_db()
    org, teacher, student, _, session, _, _, _, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ).decode()
    monkeypatch.setattr(settings, "jaas_enabled", True)
    monkeypatch.setattr(settings, "jaas_app_id", "test-live")
    monkeypatch.setattr(settings, "jaas_kid", "test-live/key")
    monkeypatch.setattr(settings, "jaas_private_key", pem)
    current = datetime(2025, 1, 10, 9, 5, tzinfo=UTC)

    joined = join_live_class(db, ctx(db, org, student), day.id, now=current)
    claims = jwt.decode(joined["token"], private_key.public_key(), algorithms=["RS256"],
                        audience="jitsi", options={"verify_exp": False, "verify_nbf": False})
    assert claims["room"] == f"school-{org.id}-session-{session.id}-day-{day.id}"
    assert claims["context"]["user"]["moderator"] == "false"
    assert join_live_class(db, ctx(db, org, teacher), day.id, now=current)["moderator"]
    with pytest.raises(HTTPException) as too_early:
        join_live_class(db, ctx(db, org, student), day.id, now=datetime(2025, 1, 10, 8, 40, tzinfo=UTC))
    assert too_early.value.status_code == 403

    other_school = OrganizationRecord(name="Other live", slug="other-live")
    db.add(other_school)
    db.flush()
    member = OrganizationMemberRecord(organization_id=other_school.id, user_id=teacher.id, role="teacher", status="active")
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"teacher"})
    db.commit()
    with pytest.raises(HTTPException) as hidden:
        join_live_class(db, ctx(db, other_school, teacher), day.id, now=current)
    assert hidden.value.status_code == 404


def test_live_class_start_is_teacher_owned_and_time_gated() -> None:
    db = build_db()
    org, teacher, student, _, session, _, _, _, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    start_time = datetime(2025, 1, 10, 9, 2, tzinfo=UTC)
    with pytest.raises(HTTPException) as early:
        start_live_class(db, teacher_tenant, day.id, now=datetime(2025, 1, 10, 8, 59, tzinfo=UTC))
    assert early.value.status_code == 409
    with pytest.raises(HTTPException) as forbidden:
        start_live_class(db, student_tenant, day.id, now=start_time)
    assert forbidden.value.status_code == 403
    started = start_live_class(db, teacher_tenant, day.id, now=start_time)
    assert started["started_at"] == start_time
    assert start_live_class(db, teacher_tenant, day.id, now=datetime(2025, 1, 10, 9, 4, tzinfo=UTC))["started_at"] == start_time
    assert get_session_planning(db, student_tenant, session.id).course_days[0].started_at == start_time
    with pytest.raises(HTTPException) as locked:
        update_course_day(db, teacher_tenant, day.id, CourseDayUpdate(title="Changed"))
    assert locked.value.status_code == 409


def test_guided_badge_waits_for_course_day_report_and_finalized_attendance() -> None:
    db = build_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    mark_lesson_complete(db, student_tenant, lesson.id)
    assert student_progress(db, student_tenant)[0].badge.level == "semi_pro"
    with pytest.raises(HTTPException) as too_early:
        submit_course_day_report(db, teacher_tenant, day.id, CourseDayReportSubmit(delivery_status="held", summary="Cours terminé normalement"), now=datetime(2025, 1, 10, 9, 30, tzinfo=UTC))
    assert too_early.value.status_code == 409
    with pytest.raises(HTTPException) as unmarked:
        submit_course_day_report(db, teacher_tenant, day.id, CourseDayReportSubmit(delivery_status="held", summary="Cours terminé normalement"))
    assert unmarked.value.status_code == 409
    for current_enrollment in (enrollment, classmate_enrollment):
        mark_attendance(db, teacher_tenant, day.id, AttendanceMarkPayload(enrollment_id=current_enrollment.id, status="present"))
    planning = submit_course_day_report(db, teacher_tenant, day.id, CourseDayReportSubmit(
        delivery_status="held", summary="Cours terminé normalement",
        difficulties="  Audio instable  ", homework="Projet suivant", attendance_notes="  ",
    ))
    assert planning.course_days[0].report_submitted_at is not None
    assert planning.course_days[0].started_at == day.scheduled_at
    assert planning.course_days[0].report_summary == "Cours terminé normalement"
    assert planning.course_days[0].report_difficulties == "Audio instable"
    assert planning.course_days[0].report_homework == "Projet suivant"
    assert planning.course_days[0].report_attendance_notes is None
    assert get_session_planning(db, student_tenant, session.id).course_days[0].report_summary is None
    assert get_session_planning(db, student_tenant, session.id).course_days[0].report_difficulties is None
    assert student_progress(db, student_tenant)[0].badge.level == "professionnel"
    with pytest.raises(HTTPException) as closed:
        mark_attendance(db, teacher_tenant, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="absent"))
    assert closed.value.status_code == 409


def test_non_held_course_day_does_not_count_as_student_absence() -> None:
    db = build_db()
    org, teacher, student, _, session, _, _, lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    mark_lesson_complete(db, student_tenant, lesson.id)

    planning = submit_course_day_report(db, teacher_tenant, day.id, CourseDayReportSubmit(
        delivery_status="not_held", summary="La séance n'a pas pu avoir lieu.",
    ))
    assert planning.course_days[0].delivery_status == "not_held"
    progress = student_progress(db, student_tenant)[0]
    assert progress.attendance_total == 0
    assert progress.badge.level == "professionnel"
    with pytest.raises(HTTPException) as closed:
        join_live_class(db, student_tenant, day.id, now=datetime(2025, 1, 10, 11, 5, tzinfo=UTC))
    assert closed.value.status_code == 404


def test_student_course_day_feedback_is_private_and_school_scoped() -> None:
    db = build_db()
    org, teacher, student, classmate, session, _, _, _, day = seed(db)
    student_tenant = ctx(db, org, student)
    classmate_tenant = ctx(db, org, classmate)
    teacher_tenant = ctx(db, org, teacher)
    payload = CourseDayFeedbackSubmit(rating=4, delivery_status="partial", comment="  Cours utile  ")
    with pytest.raises(HTTPException) as early:
        submit_course_day_feedback(db, student_tenant, day.id, payload, now=datetime(2025, 1, 10, 9, 30, tzinfo=UTC))
    assert early.value.status_code == 409

    planning = submit_course_day_feedback(db, student_tenant, day.id, payload)
    assert planning.course_days[0].my_feedback.comment == "Cours utile"
    assert planning.course_days[0].feedback_count == 1
    assert get_session_planning(db, classmate_tenant, session.id).course_days[0].my_feedback is None
    submit_course_day_feedback(db, classmate_tenant, day.id, CourseDayFeedbackSubmit(
        rating=2, delivery_status="not_held", comment=None,
    ))
    updated = submit_course_day_feedback(db, student_tenant, day.id, CourseDayFeedbackSubmit(
        rating=5, delivery_status="held", comment="Finalement bien tenu",
    ))
    assert updated.course_days[0].feedback_count == 2
    assert updated.course_days[0].average_rating == 3.5
    with pytest.raises(HTTPException) as forbidden:
        list_course_day_feedback(db, student_tenant, day.id)
    assert forbidden.value.status_code == 403
    reviews = list_course_day_feedback(db, teacher_tenant, day.id)
    assert {item.student_name for item in reviews} == {"Student", "Classmate"}
    assert {item.rating for item in reviews} == {2, 5}
    other_org = OrganizationRecord(name="Other school", slug="other-school")
    db.add(other_org)
    db.flush()
    other_formation = FormationRecord(organization_id=other_org.id, slug="other", title="Other course")
    db.add(other_formation)
    db.flush()
    other_session = FormationSessionRecord(
        organization_id=other_org.id, formation_id=other_formation.id, label="Other session",
        start_date=date(2025, 1, 1), end_date=date(2025, 2, 1), status="open",
    )
    db.add(other_session)
    db.flush()
    other_day = SessionCourseDayRecord(
        organization_id=other_org.id, session_id=other_session.id, title="Other day",
        scheduled_at=datetime(2025, 1, 10, 9, tzinfo=UTC), duration_minutes=60,
    )
    db.add(other_day)
    db.commit()
    with pytest.raises(HTTPException) as hidden:
        submit_course_day_feedback(db, student_tenant, other_day.id, payload)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as hidden_reviews:
        list_course_day_feedback(db, teacher_tenant, other_day.id)
    assert hidden_reviews.value.status_code == 404


def test_school_manager_can_review_course_day_reports() -> None:
    db = build_db()
    org, teacher, student, _, _, _, _, _, day = seed(db)
    manager = UserRecord(email="manager@test.dev", full_name="Manager", status="active")
    db.add(manager)
    db.flush()
    member = OrganizationMemberRecord(organization_id=org.id, user_id=manager.id, role="manager", status="active")
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"manager"})
    db.commit()
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(
        delivery_status="not_held", summary="Cours annulé sur place.",
    ))
    reports = list_school_course_day_reports(db, ctx(db, org, manager))
    assert len(reports) == 1
    assert reports[0].course_day_id == day.id
    assert reports[0].teacher_name == "Teacher"
    assert reports[0].summary == "Cours annulé sur place."
    with pytest.raises(HTTPException) as forbidden:
        list_school_course_day_reports(db, ctx(db, org, student))
    assert forbidden.value.status_code == 403


def test_course_publication_publishes_valid_lessons_together() -> None:
    db = build_db()
    org, teacher, student, _, session, _, _, first_lesson, _ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    chapter = db.get(ChapterRecord, first_lesson.chapter_id)
    course = db.get(CourseRecord, chapter.course_id)
    course.status = "draft"
    db.commit()
    detail = create_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, LessonCreate(title="À rédiger"))
    lesson_id = detail.sessions[0].courses[0].chapters[0].lessons[-1].id
    with pytest.raises(HTTPException) as invalid:
        update_course(db, teacher_tenant, session.formation_id, session.id, course.id, CourseUpdate(status="published"))
    assert invalid.value.status_code == 422
    update_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id, LessonCreate(title="À lire", content="Contenu prêt"))
    update_course(db, teacher_tenant, session.formation_id, session.id, course.id, CourseUpdate(status="published"))
    assert db.get(LessonRecord, lesson_id).publication_status == "published"
    assert len(list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons) == 2


def test_pdf_lesson_requires_real_page_reading_before_quiz_completion() -> None:
    db = build_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, first_lesson, _ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    raw = BytesIO()
    pdf = canvas.Canvas(raw)
    for page in range(5):
        pdf.drawString(72, 720, f"Page de formation {page + 1}")
        pdf.showPage()
    pdf.save()
    asset = asyncio.run(store_pdf_asset(db, teacher_tenant, UploadFile(file=BytesIO(raw.getvalue()), filename="course.pdf")))
    file_path = Path(__file__).resolve().parents[1] / "private_uploads" / asset.storage_key
    try:
        quiz = create_quiz(db, teacher_tenant, session.id, QuizCreate(
            title="Validation PDF", questions=[QuizQuestionCreate(
                text=f"Question {index + 1} ?", options=["Oui", "Non"], correct_index=0,
            ) for index in range(20)],
        ))
        chapter = db.get(ChapterRecord, first_lesson.chapter_id)
        course = db.get(CourseRecord, chapter.course_id)
        detail = create_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, LessonCreate(
            title="Support PDF validé", lesson_type="pdf", file_url=asset.source_url, quiz_id=quiz.id,
        ))
        lesson_id = detail.sessions[0].courses[0].chapters[0].lessons[-1].id
        publish_lesson(db, teacher_tenant, session.formation_id, session.id, course.id, chapter.id, lesson_id)
        assert db.get(QuizRecord, quiz.id).pass_pct == 70
        assert pdf_bytes(db, student_tenant, lesson_id) == raw.getvalue()
        assert read_pdf_progress(db, student_tenant, lesson_id)["viewed_pct"] == 0
        locked_quiz = list_student_quizzes(db, student_tenant)[0]
        assert locked_quiz.pdf_reading_locked and locked_quiz.questions == []
        with pytest.raises(HTTPException) as early:
            submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[0] * 20))
        assert early.value.status_code == 409
        with pytest.raises(HTTPException) as manual:
            mark_lesson_complete(db, student_tenant, lesson_id)
        assert manual.value.status_code == 400
        with pytest.raises(HTTPException) as unknown_page:
            report_pdf_page(db, student_tenant, lesson_id, 6, "open")
        assert unknown_page.value.status_code == 422
        for page in range(1, 5):
            report_pdf_page(db, student_tenant, lesson_id, page, "open")
            progress_record = db.scalar(select(LessonPdfProgressRecord).where(
                LessonPdfProgressRecord.enrollment_id == enrollment.id,
                LessonPdfProgressRecord.lesson_id == lesson_id,
            ))
            assert report_pdf_page(db, student_tenant, lesson_id, page, "confirm")["viewed_pct"] == (page - 1) * 20
            progress_record.active_since = datetime.now(UTC) - timedelta(seconds=3)
            db.commit()
            state = report_pdf_page(db, student_tenant, lesson_id, page, "confirm")
            assert state["viewed_pct"] == page * 20
        assert state["quiz_unlocked"] and state["viewed_pages"] == [1, 2, 3, 4]
        assert not state["is_completed"]
        open_quiz = list_student_quizzes(db, student_tenant)[0]
        assert open_quiz.can_attempt and len(open_quiz.questions) == 20
        result = submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[0] * 20))
        assert result.passed
        assert read_pdf_progress(db, student_tenant, lesson_id)["is_completed"]
        assert list_student_learning(db, student_tenant)[0].courses[0].chapters[0].lessons[-1].completed

        classmate_tenant = ctx(db, org, classmate)
        assert read_pdf_progress(db, classmate_tenant, lesson_id)["viewed_pct"] == 0
        assert list_student_quizzes(db, classmate_tenant)[0].pdf_reading_locked
        for page in range(1, 5):
            report_pdf_page(db, classmate_tenant, lesson_id, page, "open")
            row = db.scalar(select(LessonPdfProgressRecord).where(
                LessonPdfProgressRecord.enrollment_id == classmate_enrollment.id,
                LessonPdfProgressRecord.lesson_id == lesson_id,
            ))
            row.active_since = datetime.now(UTC) - timedelta(seconds=3)
            db.commit()
            report_pdf_page(db, classmate_tenant, lesson_id, page, "confirm")
        for index in range(3):
            failed = submit_quiz_attempt(db, classmate_tenant, quiz.id, QuizAttemptPayload(answers=[1] * 20))
            assert not failed.passed
            assert failed.attempts_remaining == 2 - index
        assert failed.next_attempt_available_at is not None
        with pytest.raises(HTTPException) as retry:
            submit_quiz_attempt(db, classmate_tenant, quiz.id, QuizAttemptPayload(answers=[0] * 20))
        assert retry.value.status_code == 409
        third_attempt = db.scalar(select(QuizAttemptRecord).where(
            QuizAttemptRecord.quiz_id == quiz.id, QuizAttemptRecord.enrollment_id == classmate_enrollment.id,
            QuizAttemptRecord.attempt_number == 3,
        ))
        third_attempt.submitted_at = datetime.now(UTC) - timedelta(hours=9)
        db.commit()
        assert list_student_quizzes(db, classmate_tenant)[0].attempts_remaining == 3
        fourth = submit_quiz_attempt(db, classmate_tenant, quiz.id, QuizAttemptPayload(answers=[0] * 20))
        assert fourth.passed and fourth.attempts[-1].attempt_number == 4

        other_org = OrganizationRecord(name="Other PDF school", slug="other-pdf-school")
        db.add(other_org)
        db.flush()
        other_member = OrganizationMemberRecord(
            organization_id=other_org.id, user_id=student.id, role="student", status="active",
        )
        db.add(other_member)
        db.flush()
        replace_effective_roles(db, other_member, {"student"})
        db.commit()
        other_tenant = ctx(db, other_org, student)
        with pytest.raises(HTTPException) as other_school:
            pdf_bytes(db, other_tenant, lesson_id)
        assert other_school.value.status_code == 404
    finally:
        file_path.unlink(missing_ok=True)


def test_lesson_progress_badge_and_certificate_are_real() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, day = seed(db)
    student_tenant = ctx(db, org, student)
    teacher_tenant = ctx(db, org, teacher)

    learning = mark_lesson_complete(db, student_tenant, lesson.id)
    assert learning.courses[0].chapters[0].lessons[0].completed is True

    mark_attendance(
        db,
        teacher_tenant,
        day.id,
        AttendanceMarkPayload(
            enrollment_id=enrollment.id,
            status="present",
        ),
    )

    progress = student_progress(db, student_tenant)[0]
    assert progress.lesson_progress_pct == 100
    assert progress.badge.level == "professionnel"

    certificate = issue_certificate(db, student_tenant, enrollment.id)
    assert certificate.student_name == "Student"
    assert certificate.formation_title == "Motion Design"
    assert "-CERT-" in certificate.certificate_number
    assert certificate.certificate_number.startswith("SC-CERT-")

    verified = verify_certificate_token(db, certificate.verification_token)
    assert verified.certificate_number == certificate.certificate_number

    certificate_row = db.scalar(
        select(CertificateRecord).where(
            CertificateRecord.enrollment_id == enrollment.id
        )
    )
    assert certificate_row is not None
    assert certificate_row.branding_snapshot["school_name"] == "School"
    assert certificate_row.branding_snapshot["document"]["session_label"] == "Cohorte 2025"
    filename, pdf = build_certificate_pdf(certificate_row)
    assert filename.endswith(".pdf")
    assert pdf.startswith(b"%PDF")


def test_classic_certificate_ignores_technical_session_end_and_unlinked_assignment() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, _ = seed(db)
    tenant = ctx(db, org, student)
    session.end_date = date(2099, 1, 1)
    db.add(AssignmentRecord(
        organization_id=org.id,
        session_id=session.id,
        teacher_id=teacher.id,
        title="Devoir hors parcours",
        due_date=datetime(2099, 1, 1, tzinfo=UTC),
    ))
    db.commit()

    mark_lesson_complete(db, tenant, lesson.id)
    eligibility = certificate_eligibility(db, tenant, enrollment.id)
    assert eligibility.eligible is True
    assert issue_certificate(db, tenant, enrollment.id).enrollment_id == enrollment.id


def test_classic_certificate_requires_success_on_linked_quiz() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, _ = seed(db)
    tenant = ctx(db, org, student)
    mark_lesson_complete(db, tenant, lesson.id)
    quiz = QuizRecord(
        organization_id=org.id,
        session_id=session.id,
        teacher_id=teacher.id,
        title="Évaluation de la leçon",
        status="active",
        pass_pct=80,
    )
    db.add(quiz)
    db.flush()
    lesson.quiz_id = quiz.id
    lesson.lesson_type = "quiz"
    db.commit()

    eligibility = certificate_eligibility(db, tenant, enrollment.id)
    assert eligibility.eligible is False
    assert "quiz" in eligibility.reason

    db.add(QuizAttemptRecord(
        organization_id=org.id,
        quiz_id=quiz.id,
        enrollment_id=enrollment.id,
        attempt_number=1,
        answers=[],
        score_pct=80,
        submitted_at=datetime.now(UTC),
    ))
    db.commit()
    assert certificate_eligibility(db, tenant, enrollment.id).eligible is True


def test_guided_certificate_waits_until_paris_session_end() -> None:
    db = build_db()
    org, _, student, _, session, enrollment, _, _, _ = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    session.end_date = date(2099, 1, 1)
    db.commit()

    eligibility = certificate_eligibility(db, ctx(db, org, student), enrollment.id)
    assert eligibility.eligible is False
    assert "fin de la session" in eligibility.reason
    assert session_ends_at(session) == datetime(2099, 1, 1, 23, 0, tzinfo=UTC)


def test_guided_certificate_requires_school_validation() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    day.status = "cancelled"
    db.commit()
    student_tenant = ctx(db, org, student)
    mark_lesson_complete(db, student_tenant, lesson.id)
    assert student_progress(db, student_tenant)[0].badge.level == "professionnel"

    before = certificate_eligibility(db, student_tenant, enrollment.id)
    assert before.eligible is False
    assert "validée par l'école" in before.reason

    update_enrollment(
        db, ctx(db, org, teacher), session.formation_id, session.id,
        enrollment.id, EnrollmentUpdate(status="completed"),
    )
    assert certificate_eligibility(db, student_tenant, enrollment.id).eligible is True
    assert issue_certificate(db, student_tenant, enrollment.id).enrollment_id == enrollment.id


def test_badge_weights_standard_assignments_and_final_project_separately() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, _, _ = seed(db)
    ordinary = AssignmentRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Exercice", due_date=datetime(2025, 1, 15, tzinfo=UTC), is_final_project=False,
    )
    final = AssignmentRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Projet final", due_date=datetime(2025, 1, 20, tzinfo=UTC), is_final_project=True,
    )
    db.add_all([ordinary, final])
    db.flush()
    db.add(AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=ordinary.id, enrollment_id=enrollment.id,
        file_url="https://example.org/exercice.pdf", submitted_at=datetime(2025, 1, 15, tzinfo=UTC),
    ))
    db.commit()
    progress = student_progress(db, ctx(db, org, student))[0]
    assert progress.total_assignments == 2
    assert progress.badge.assignment_progress_pct == 100
    assert progress.badge.final_project_validated is False
    assert progress.badge.score_pct == 23.3


def test_badge_quiz_mastery_requires_eighty_percent() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, day = seed(db)
    day.status = "cancelled"
    db.commit()
    tenant = ctx(db, org, student)
    mark_lesson_complete(db, tenant, lesson.id)
    quiz = QuizRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Quiz PDF", status="active", pass_pct=70,
    )
    db.add(quiz)
    db.flush()
    db.add(QuizAttemptRecord(
        organization_id=org.id, quiz_id=quiz.id, enrollment_id=enrollment.id,
        attempt_number=1, answers=[], score_pct=75, submitted_at=datetime.now(UTC),
    ))
    db.commit()

    progress = student_progress(db, tenant)[0]
    assert progress.badge.quiz_progress_pct == 20
    assert progress.badge.level != "professionnel"

    db.add(QuizAttemptRecord(
        organization_id=org.id, quiz_id=quiz.id, enrollment_id=enrollment.id,
        attempt_number=2, answers=[], score_pct=80, submitted_at=datetime.now(UTC),
    ))
    db.commit()
    assert student_progress(db, tenant)[0].badge.level == "professionnel"


def test_guided_assignment_lesson_requires_a_real_submission() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    day.status = "cancelled"
    assignment = AssignmentRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Travail pratique", due_date=datetime(2025, 1, 20, tzinfo=UTC),
    )
    db.add(assignment)
    db.flush()
    lesson.lesson_type = "assignment"
    lesson.assignment_id = assignment.id
    db.add(LessonProgressRecord(
        organization_id=org.id, enrollment_id=enrollment.id,
        lesson_id=lesson.id, completed_at=datetime.now(UTC),
    ))
    db.commit()
    tenant = ctx(db, org, student)

    before = student_progress(db, tenant)[0]
    assert before.completed_lessons == 0
    assert list_student_learning(db, tenant)[0].courses[0].chapters[0].lessons[0].completed is False

    db.add(AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=assignment.id, enrollment_id=enrollment.id,
        file_url="https://example.org/travail.pdf", submitted_at=datetime.now(UTC),
    ))
    db.commit()
    assert student_progress(db, tenant)[0].completed_lessons == 1
    assert list_student_learning(db, tenant)[0].courses[0].chapters[0].lessons[0].completed is True


def test_draft_course_is_invisible_and_cannot_be_completed_by_student() -> None:
    db = build_db()
    org, teacher, student, _, _, enrollment, _, lesson, _ = seed(db)
    student_tenant = ctx(db, org, student)
    teacher_tenant = ctx(db, org, teacher)
    course = db.get(ChapterRecord, lesson.chapter_id).course
    course.status = "draft"
    db.commit()

    assert list_student_learning(db, student_tenant)[0].courses == []
    assert get_student_workspace(db, student_tenant).total_courses == 0
    assert get_teacher_workspace(db, teacher_tenant).total_courses == 1
    assert student_progress(db, student_tenant)[0].lesson_progress_pct == 0
    with pytest.raises(HTTPException) as error:
        mark_lesson_complete(db, student_tenant, lesson.id)
    assert error.value.status_code == 404
    assert db.scalar(select(LessonProgressRecord).where(LessonProgressRecord.enrollment_id == enrollment.id)) is None


def test_guided_course_waits_for_session_start_but_classic_is_immediate() -> None:
    db = build_db()
    org, _, student, _, session, _, _, lesson, _ = seed(db)
    tenant = ctx(db, org, student)
    formation = db.get(FormationRecord, session.formation_id)
    session.start_date = date(2099, 1, 1)
    session.end_date = date(2099, 2, 1)

    classic = list_student_learning(db, tenant)[0]
    assert classic.dashboard_type == "classic"
    assert classic.is_locked is False
    assert classic.courses[0].chapters[0].lessons[0].content == "Contenu"

    formation.format_type = "live"
    db.commit()
    guided = list_student_learning(db, tenant)[0]
    assert guided.dashboard_type == "guided"
    assert guided.is_locked is True
    assert guided.available_at is not None
    assert guided.courses[0].chapters[0].lessons[0].content is None
    assert get_student_workspace(db, tenant).sessions[0].dashboard_type == "guided"
    with pytest.raises(HTTPException) as error:
        mark_lesson_complete(db, tenant, lesson.id)
    assert error.value.status_code == 409

    session.start_date = date(2025, 1, 1)
    session.end_date = date(2025, 2, 1)
    db.commit()
    assert list_student_learning(db, tenant)[0].is_locked is False


def test_video_requires_eighty_percent_watched_without_counting_seeks() -> None:
    db = build_db()
    org, _, student, _, _, enrollment, _, lesson, _ = seed(db)
    tenant = ctx(db, org, student)
    lesson.lesson_type = "video"
    lesson.video_url = "https://video.test/lesson.mp4"
    db.commit()

    with pytest.raises(HTTPException) as error:
        mark_lesson_complete(db, tenant, lesson.id)
    assert error.value.status_code == 400

    start = datetime(2026, 1, 1, tzinfo=UTC)
    def report(position: float, seconds: int, event: str = "heartbeat"):
        return sync_lesson_video_progress(
            db,
            tenant,
            lesson.id,
            LessonVideoHeartbeatPayload(
                current_time_seconds=position,
                duration_seconds=100,
                event=event,
            ),
            now=start + timedelta(seconds=seconds),
        )

    report(90, 0, "seek")
    jumped = report(95, 1)
    assert jumped.courses[0].chapters[0].lessons[0].video_watched_pct == 0
    assert db.scalar(select(LessonProgressRecord).where(LessonProgressRecord.enrollment_id == enrollment.id)) is None

    report(0, 2, "seek")
    for index in range(1, 8):
        report(index * 10, 2 + index * 10)
    finished = report(80, 82)
    video = finished.courses[0].chapters[0].lessons[0]
    assert video.video_watched_pct == 80
    assert video.completed is True
    assert student_progress(db, tenant)[0].lesson_progress_pct == 100
    record = db.scalar(select(LessonVideoProgressRecord).where(LessonVideoProgressRecord.enrollment_id == enrollment.id))
    assert record.watched_ranges == [[0.0, 80.0]]


def test_guided_quiz_and_assignment_wait_for_session_start() -> None:
    db = build_db()
    org, teacher, student, _, session, *_ = seed(db)
    formation = db.get(FormationRecord, session.formation_id)
    formation.format_type = "live"
    session.start_date = date(2099, 1, 1)
    session.end_date = date(2099, 2, 1)
    db.commit()
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)

    quiz = create_quiz(db, teacher_tenant, session.id, QuizCreate(
        title="Contrôle", questions=[QuizQuestionCreate(text="Question ?", options=["Oui", "Non"], correct_index=0)],
    ))
    set_quiz_status(db, teacher_tenant, quiz.id, "active")
    student_quiz = list_student_quizzes(db, student_tenant)[0]
    assert student_quiz.can_attempt is False
    assert student_quiz.is_locked is True
    assert student_quiz.questions == []
    with pytest.raises(HTTPException) as quiz_error:
        submit_quiz_attempt(db, student_tenant, quiz.id, QuizAttemptPayload(answers=[0]))
    assert quiz_error.value.status_code == 409

    assignment = create_assignment(db, teacher_tenant, session.id, AssignmentCreate(
        title="Travail", due_date=datetime(2099, 1, 20, tzinfo=UTC),
    ))
    locked_assignment = list_student_assignments(db, student_tenant)[0]
    assert locked_assignment.is_locked is True
    assert locked_assignment.instructions == ""
    with pytest.raises(HTTPException) as assignment_error:
        submit_assignment(db, student_tenant, assignment.id, AssignmentSubmit(file_url="test"))
    assert assignment_error.value.status_code == 409

    session.start_date = date(2025, 1, 1)
    session.end_date = date(2099, 2, 1)
    db.commit()
    assert list_student_quizzes(db, student_tenant)[0].can_attempt is True
    assert len(list_student_quizzes(db, student_tenant)[0].questions) == 1
    assert [item.id for item in list_student_assignments(db, student_tenant)] == [assignment.id]
    assert list_student_assignments(db, student_tenant)[0].is_locked is False


def test_guided_preparatory_resource_stays_available_before_session() -> None:
    db = build_db()
    org, teacher, student, _, session, *_ = seed(db)
    formation = db.get(FormationRecord, session.formation_id)
    formation.format_type = "presentiel"
    session.start_date = date(2099, 1, 1)
    session.end_date = date(2099, 2, 1)
    db.commit()
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)
    resource = create_resource(db, teacher_tenant, session.id, ResourceCreate(
        title="À lire avant la rentrée", resource_type="pdf", url="https://files.test/intro.pdf",
    ))
    assert [item.id for item in list_student_resources(db, student_tenant)] == [resource.id]

    day = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Cours annulé", scheduled_at=datetime(2099, 1, 10, tzinfo=UTC),
        duration_minutes=90, status="cancelled",
    )
    db.add(day)
    db.flush()
    db.get(ResourceRecord, resource.id).course_day_id = day.id
    db.commit()
    assert list_student_resources(db, student_tenant) == []


def test_video_progress_is_isolated_between_schools() -> None:
    db = build_db()
    org, _, student, _, session, enrollment, _, lesson, _ = seed(db)
    lesson.lesson_type = "video"
    lesson.video_url = "https://video.test/a.mp4"
    other_org = OrganizationRecord(name="Other school", slug="other-school")
    db.add(other_org)
    db.flush()
    member = OrganizationMemberRecord(
        organization_id=other_org.id, user_id=student.id, role="student", status="active",
    )
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"student"})
    other_formation = FormationRecord(organization_id=other_org.id, slug="other", title="Other")
    db.add(other_formation)
    db.flush()
    other_session = FormationSessionRecord(
        organization_id=other_org.id, formation_id=other_formation.id,
        label="Other", start_date=date(2025, 1, 1), end_date=date(2025, 2, 1), status="open",
    )
    db.add(other_session)
    db.flush()
    db.add(EnrollmentRecord(
        organization_id=other_org.id, session_id=other_session.id, student_id=student.id, status="active",
    ))
    db.commit()

    first_tenant = ctx(db, org, student)
    other_tenant = ctx(db, other_org, student)
    sync_lesson_video_progress(db, first_tenant, lesson.id, LessonVideoHeartbeatPayload(
        current_time_seconds=20, duration_seconds=100, event="seek",
    ))
    assert db.scalar(select(LessonVideoProgressRecord).where(
        LessonVideoProgressRecord.enrollment_id == enrollment.id,
    )) is not None
    assert list_student_learning(db, other_tenant)[0].courses == []
    with pytest.raises(HTTPException) as error:
        sync_lesson_video_progress(db, other_tenant, lesson.id, LessonVideoHeartbeatPayload(
            current_time_seconds=30, duration_seconds=100,
        ))
    assert error.value.status_code == 404


def test_attendance_is_owned_by_course_day_teacher() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, _, day = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)

    updated = mark_attendance(
        db,
        teacher_tenant,
        day.id,
        AttendanceMarkPayload(
            enrollment_id=enrollment.id,
            status="present",
        ),
    )
    assert next(item for item in updated.rows if item.enrollment_id == enrollment.id).status == "present"

    own = student_attendance(db, student_tenant)
    assert own[0].status == "present"


def test_class_roster_discussion_and_performance() -> None:
    db = build_db()
    org, teacher, student, classmate, session, *_ = seed(db)
    student_tenant = ctx(db, org, student)
    teacher_tenant = ctx(db, org, teacher)

    classes = list_student_classes(db, student_tenant)
    assert len(classes) == 1
    assert {item.full_name for item in classes[0].classmates} == {"Student", "Classmate"}

    post = create_discussion_post(
        db,
        student_tenant,
        session.id,
        DiscussionCreate(body="Bonjour la classe"),
    )
    assert post.author.full_name == "Student"
    assert db.scalar(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == org.id,
        SchoolNotificationRecord.user_id == classmate.id,
        SchoolNotificationRecord.event_key == f"discussion.post:{post.id}",
    )) is not None
    assert db.scalar(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == org.id,
        SchoolNotificationRecord.user_id == student.id,
        SchoolNotificationRecord.event_key == f"discussion.post:{post.id}",
    )) is None
    assert discussion_posts(db, teacher_tenant, session.id)[0].body == "Bonjour la classe"

    performance = teacher_performance(db, teacher_tenant)
    assert performance.total_sessions == 1
    assert performance.total_students == 2


def test_student_grades_returns_quiz_grade() -> None:
    db = build_db()
    org, teacher, student, _, session, *_ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    student_tenant = ctx(db, org, student)

    quiz = create_quiz(
        db,
        teacher_tenant,
        session.id,
        QuizCreate(
            title="Examen",
            assessment_type="exam",
            questions=[
                QuizQuestionCreate(
                    text="Bonne réponse ?",
                    options=["A", "B"],
                    correct_index=0,
                )
            ],
        ),
    )
    set_quiz_status(db, teacher_tenant, quiz.id, "active")
    submit_quiz_attempt(
        db,
        student_tenant,
        quiz.id,
        QuizAttemptPayload(answers=[0]),
    )

    grades = student_grades(db, student_tenant)
    assert len(grades) == 1
    assert grades[0].source_type == "quiz"
    assert grades[0].score == 20
