import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from test_academic_suite import build_db, ctx, seed
from test_assignment_workflow import ctx as workflow_ctx
from test_assignment_workflow import dbx as workflow_db
from test_assignment_workflow import published_assignment
from test_assignment_workflow import seed as workflow_seed
from test_school_commerce import build_db as build_commerce_db
from test_school_commerce import demo_payments  # noqa: F401  (autouse fixture)
from test_school_commerce import seed as seed_commerce

from app.core.config import settings
from app.models.entities import (
    ChapterRecord,
    CommunicationOutboxRecord,
    CourseRecord,
    FormationRecord,
    OrderInstallmentRecord,
    SchoolNotificationRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.academic import AttendanceMarkPayload, TeacherGradeEntry
from app.schemas.assignments import AssignmentCreate, AssignmentSubmit
from app.schemas.commerce import CheckoutCreate
from app.schemas.formations import LessonCreate
from app.schemas.planning import CourseDayReportSubmit
from app.services.assets import store_submission_asset
from app.services.assignments import submit_assignment
from app.services.formations import create_lesson, publish_lesson
from app.services.grades import save_teacher_grades
from app.services.learning_progress import mark_attendance
from app.services.planning import submit_course_day_report
from app.services.school_commerce import confirm_demo_checkout, create_checkout
from app.services.training_notifications import (
    process_course_reminders,
    process_payment_reminders,
    process_session_end_notices,
)


def notices(db, prefix: str, user_id: int | None = None, *, active_only: bool = False) -> int:
    query = select(func.count(SchoolNotificationRecord.id)).where(SchoolNotificationRecord.event_key.startswith(prefix))
    if user_id is not None:
        query = query.where(SchoolNotificationRecord.user_id == user_id)
    if active_only:
        query = query.where(SchoolNotificationRecord.dismissed_at.is_(None))
    return int(db.scalar(query) or 0)


def emails(db, event_key: str, recipient: str | None = None) -> int:
    query = select(func.count(CommunicationOutboxRecord.id)).where(
        CommunicationOutboxRecord.event_key == event_key, CommunicationOutboxRecord.channel == "email",
    )
    if recipient is not None:
        query = query.where(CommunicationOutboxRecord.recipient == recipient)
    return int(db.scalar(query) or 0)


def live_school():
    db = build_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, _lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    return db, org, teacher, student, classmate, session, enrollment, classmate_enrollment, day


def test_course_reminders_reach_students_and_teacher_once_per_window() -> None:
    db, org, teacher, student, classmate, session, *_rest, day = live_school()
    now = datetime.now(UTC)
    day.scheduled_at = now + timedelta(hours=23)
    db.commit()

    assert process_course_reminders(db, now=now) == 3  # two students and the teacher
    assert notices(db, f"course.reminder:{day.id}:24h", student.id) == 1
    assert notices(db, f"course.reminder:{day.id}:24h", teacher.id) == 1
    assert emails(db, "student.course.reminder_24h") == 2
    assert process_course_reminders(db, now=now + timedelta(minutes=30)) == 0

    assert process_course_reminders(db, now=now + timedelta(hours=22, minutes=30)) == 3
    assert emails(db, "student.course.reminder_1h") == 2

    day.status = "cancelled"
    day.scheduled_at = now + timedelta(hours=23, minutes=30)
    db.commit()
    assert process_course_reminders(db, now=now) == 0


def test_the_report_announces_absences_and_a_correction_withdraws_them() -> None:
    db, org, teacher, student, classmate, session, enrollment, classmate_enrollment, day = live_school()
    tenant = ctx(db, org, teacher)
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="present"))
    submit_course_day_report(db, tenant, day.id, CourseDayReportSubmit(delivery_status="held", summary="Cours tenu normalement"))

    assert notices(db, f"attendance.absent:{day.id}", classmate.id) == 1
    assert notices(db, f"attendance.absent:{day.id}", student.id) == 0
    assert emails(db, "student.attendance.absent", classmate.email) == 1

    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=classmate_enrollment.id, status="late"))
    assert notices(db, f"attendance.absent:{day.id}", classmate.id, active_only=True) == 0
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="absent"))
    assert notices(db, f"attendance.absent:{day.id}", student.id) == 1


def test_an_interrupted_day_announces_no_absence() -> None:
    db, org, teacher, _student, classmate, *_rest, day = live_school()
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(delivery_status="interrupted", summary="Coupure de la connexion"))
    assert notices(db, "attendance.absent:") == 0


def test_a_teacher_grade_tells_the_student_once_per_score() -> None:
    db, org, teacher, student, _classmate, session, enrollment, *_ = live_school()
    tenant = ctx(db, org, teacher)
    entry = {"enrollment_id": enrollment.id, "label": "Projet final", "score": 15, "max_score": 20}
    save_teacher_grades(db, tenant, session.id, [TeacherGradeEntry(**entry)])
    save_teacher_grades(db, tenant, session.id, [TeacherGradeEntry(**entry)])
    assert notices(db, "grade.manual:", student.id) == 1
    assert emails(db, "student.grade.created", student.email) == 1
    save_teacher_grades(db, tenant, session.id, [TeacherGradeEntry(**{**entry, "score": 17})])
    assert notices(db, "grade.manual:", student.id) == 2


def test_the_end_of_a_session_is_announced_once_in_the_following_week() -> None:
    db, org, _teacher, student, classmate, session, *_ = live_school()
    now = datetime.now(UTC)
    session.end_date = (now - timedelta(days=1)).date()
    db.commit()
    assert process_session_end_notices(db, now=now) == 2
    assert process_session_end_notices(db, now=now) == 0
    assert emails(db, "student.session.ended", student.email) == 1

    session.end_date = (now - timedelta(days=10)).date()
    db.commit()
    db.query(SchoolNotificationRecord).delete()
    assert process_session_end_notices(db, now=now) == 0


def commerce_school_with_teacher():
    db = build_commerce_db()
    org, user, formation, session = seed_commerce(db)
    teacher = UserRecord(email="prof@test.dev", full_name="Prof Test", status="active")
    db.add(teacher)
    db.flush()
    db.add(SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, role="principal"))
    db.commit()
    return db, org, user, formation, session, teacher


def test_payment_reminders_seven_days_then_one_day_before_once_the_previous_is_paid() -> None:
    db, org, user, _formation, session, _teacher = commerce_school_with_teacher()
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="installments"))
    second = db.scalar(select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.order_id == checkout.order_id, OrderInstallmentRecord.sequence == 2,
    ))
    now = datetime.now(UTC)
    # Reminders go by the school's calendar day (J-7, J-1): whole days keep the test true at any hour.
    second.due_at = now + timedelta(days=7)
    db.commit()
    assert process_payment_reminders(db, now=now) == 0  # the first instalment is not paid yet

    confirm_demo_checkout(db, org, user, checkout.order_id)
    order = db.get(StudentOrderRecord, checkout.order_id)
    order.status = "refunded"  # a refunded order is not chased
    db.commit()
    assert process_payment_reminders(db, now=now) == 0
    order.status = "partially_paid"
    db.commit()
    assert process_payment_reminders(db, now=now) == 1
    assert process_payment_reminders(db, now=now) == 0
    assert emails(db, "student.payment.reminder", user.email) == 1
    assert process_payment_reminders(db, now=now + timedelta(days=3)) == 0
    assert process_payment_reminders(db, now=now + timedelta(days=6)) == 1  # the day before


def test_a_lesson_published_on_its_own_is_announced_when_open() -> None:
    db, org, teacher, student, _classmate, session, *_rest = live_school()
    tenant = ctx(db, org, teacher)
    course = db.scalar(select(CourseRecord).where(CourseRecord.session_id == session.id))
    chapter = db.scalar(select(ChapterRecord).where(ChapterRecord.course_id == course.id))
    place = (session.formation_id, session.id, course.id, chapter.id)
    open_now = create_lesson(db, tenant, *place, LessonCreate(title="Ouverte", content="Contenu", order_index=5))
    later = create_lesson(db, tenant, *place, LessonCreate(
        title="Plus tard", content="Contenu", order_index=6, available_at=datetime.now(UTC) + timedelta(days=3),
    ))
    open_id = open_now.sessions[0].courses[0].chapters[0].lessons[-1].id
    later_id = later.sessions[0].courses[0].chapters[0].lessons[-1].id
    publish_lesson(db, tenant, *place, open_id)
    publish_lesson(db, tenant, *place, later_id)
    assert notices(db, f"lesson.published:{open_id}", student.id) == 1
    assert notices(db, f"lesson.published:{later_id}") == 0


def test_a_first_submission_emails_the_teacher(monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "local")
    db = workflow_db()
    org, teacher, student, session = workflow_seed(db)
    assignment = published_assignment(db, workflow_ctx(db, org, teacher), session.id, AssignmentCreate(
        title="Projet", due_date=datetime.now(UTC) + timedelta(days=20),
    ))
    asset = asyncio.run(store_submission_asset(UploadFile(file=BytesIO(b"work"), filename="work.pdf"), org.id, student.id))
    path = Path(__file__).resolve().parents[1] / "private_uploads" / "schools" / str(org.id) / "assignments" / str(student.id) / asset["public_url"].rsplit("/", 1)[-1]
    try:
        for _ in range(2):
            submit_assignment(db, workflow_ctx(db, org, student), assignment.id, AssignmentSubmit(file_url=asset["public_url"]))
    finally:
        path.unlink(missing_ok=True)
    assert emails(db, "teacher.assignment.submitted", teacher.email) == 1


def test_a_new_student_is_announced_to_the_session_teachers() -> None:
    db, org, user, _formation, session, teacher = commerce_school_with_teacher()
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    confirm_demo_checkout(db, org, user, checkout.order_id)
    assert notices(db, f"enrollment.created:{session.id}:{user.id}", teacher.id) == 1
    assert emails(db, "teacher.enrollment.created", teacher.email) == 1
