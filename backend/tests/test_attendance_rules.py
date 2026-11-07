from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_academic_suite import build_db, ctx, seed

from app.models.entities import AttendanceRecord, FormationRecord, SessionCourseDayRecord
from app.schemas.academic import AttendanceMarkPayload
from app.schemas.planning import CourseDayReportSubmit
from app.services.learning_progress import mark_attendance, student_progress, teacher_attendance
from app.services.planning import submit_course_day_report


def live_school():
    db = build_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, _lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    return db, org, teacher, student, classmate, session, enrollment, classmate_enrollment, day


def attendance_day(db, tenant, session_id, day_id):
    return next(item for item in teacher_attendance(db, tenant, session_id) if item.course_day_id == day_id)


def statuses(db, day_id) -> dict[int, str]:
    return {row.enrollment_id: row.status for row in db.scalars(
        select(AttendanceRecord).where(AttendanceRecord.course_day_id == day_id)
    ).all()}


def test_attendance_opens_at_the_start_of_the_course_day() -> None:
    db, org, teacher, _student, _classmate, session, enrollment, _ce, past_day = live_school()
    future = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Demain",
        scheduled_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=90, status="planned",
    )
    db.add(future)
    db.commit()
    tenant = ctx(db, org, teacher)

    with pytest.raises(HTTPException) as early:
        mark_attendance(db, tenant, future.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="present"))
    assert early.value.status_code == 409 and "début de cette séance" in early.value.detail
    view = attendance_day(db, tenant, session.id, future.id)
    assert view.can_edit is False and "début de cette séance" in view.edit_blocked_reason

    assert attendance_day(db, tenant, session.id, past_day.id).can_edit is True
    mark_attendance(db, tenant, past_day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="present"))


def test_a_late_student_counts_as_present() -> None:
    db, org, teacher, student, classmate, _session, enrollment, classmate_enrollment, day = live_school()
    tenant = ctx(db, org, teacher)
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="late"))
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=classmate_enrollment.id, status="absent"))
    submit_course_day_report(db, tenant, day.id, CourseDayReportSubmit(delivery_status="held", summary="Cours tenu"))

    late = student_progress(db, ctx(db, org, student))[0]
    absent = student_progress(db, ctx(db, org, classmate))[0]
    assert (late.attendance_present, late.attendance_total) == (1, 1)
    assert (absent.attendance_present, absent.attendance_total) == (0, 1)


def test_the_report_records_unmarked_students_absent_then_allows_24_hours_of_corrections() -> None:
    db, org, teacher, _student, _classmate, session, enrollment, classmate_enrollment, day = live_school()
    tenant = ctx(db, org, teacher)
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="present"))
    submit_course_day_report(db, tenant, day.id, CourseDayReportSubmit(delivery_status="partial", summary="Séance écourtée"))
    assert statuses(db, day.id) == {enrollment.id: "present", classmate_enrollment.id: "absent"}

    view = attendance_day(db, tenant, session.id, day.id)
    reported_at = db.get(SessionCourseDayRecord, day.id).report_submitted_at.replace(tzinfo=UTC)
    assert view.can_edit is True and view.locks_at == reported_at + timedelta(hours=24)
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=classmate_enrollment.id, status="excused"))
    assert statuses(db, day.id)[classmate_enrollment.id] == "excused"

    db.get(SessionCourseDayRecord, day.id).report_submitted_at = datetime.now(UTC) - timedelta(hours=23, minutes=59)
    db.commit()
    mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=classmate_enrollment.id, status="late"))

    db.get(SessionCourseDayRecord, day.id).report_submitted_at = datetime.now(UTC) - timedelta(hours=24, seconds=1)
    db.commit()
    with pytest.raises(HTTPException) as locked:
        mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=classmate_enrollment.id, status="absent"))
    assert locked.value.status_code == 409 and "verrouillées" in locked.value.detail
    assert attendance_day(db, tenant, session.id, day.id).can_edit is False
    assert statuses(db, day.id)[classmate_enrollment.id] == "late"


def test_an_interrupted_day_fills_absences_but_never_counts() -> None:
    db, org, teacher, student, _classmate, _session, enrollment, classmate_enrollment, day = live_school()
    tenant = ctx(db, org, teacher)
    submit_course_day_report(db, tenant, day.id, CourseDayReportSubmit(delivery_status="interrupted", summary="Coupure de la connexion"))
    assert statuses(db, day.id) == {enrollment.id: "absent", classmate_enrollment.id: "absent"}
    assert student_progress(db, ctx(db, org, student))[0].attendance_total == 0


def test_a_day_not_held_takes_no_attendance() -> None:
    db, org, teacher, _student, _classmate, session, enrollment, _ce, day = live_school()
    tenant = ctx(db, org, teacher)
    submit_course_day_report(db, tenant, day.id, CourseDayReportSubmit(delivery_status="not_held", summary="Annulée sur place"))
    assert statuses(db, day.id) == {}
    with pytest.raises(HTTPException) as refused:
        mark_attendance(db, tenant, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="present"))
    assert refused.value.status_code == 409 and "pas eu lieu" in refused.value.detail
    assert attendance_day(db, tenant, session.id, day.id).can_edit is False
