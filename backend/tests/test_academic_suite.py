from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    LessonRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.academic import (
    AttendanceMarkPayload,
    DiscussionCreate,
    QuizAttemptPayload,
    QuizCreate,
    QuizQuestionCreate,
    ResourceCreate,
)
from app.services.class_certificates import (
    create_discussion_post,
    discussion_posts,
    issue_certificate,
    list_student_classes,
    verify_certificate_token,
)
from app.services.learning_progress import (
    mark_attendance,
    mark_lesson_complete,
    student_attendance,
    student_grades,
    student_progress,
    teacher_performance,
)
from app.services.membership_roles import replace_effective_roles
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
        status="completed",
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
    org, teacher, student, _, session, *_ = seed(db)
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


def test_lesson_progress_badge_and_certificate_are_real() -> None:
    db = build_db()
    org, teacher, student, _, session, enrollment, _, lesson, _ = seed(db)
    student_tenant = ctx(db, org, student)

    learning = mark_lesson_complete(db, student_tenant, lesson.id)
    assert learning.courses[0].chapters[0].lessons[0].completed is True

    progress = student_progress(db, student_tenant)[0]
    assert progress.lesson_progress_pct == 100
    assert progress.badge.level == "professionnel"

    certificate = issue_certificate(db, student_tenant, enrollment.id)
    assert certificate.student_name == "Student"
    assert certificate.formation_title == "Motion Design"
    assert certificate.certificate_number.startswith("CERT-")

    verified = verify_certificate_token(db, certificate.verification_token)
    assert verified.certificate_number == certificate.certificate_number


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
