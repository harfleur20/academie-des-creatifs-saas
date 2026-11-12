from datetime import UTC, datetime, timedelta

import pytest
from test_academic_suite import build_db, ctx, seed
from test_training_notifications import notices

from app.models.entities import FormationRecord, SessionCourseDayRecord
from app.schemas.academic import AttendanceMarkPayload
from app.schemas.planning import CourseDayReportSubmit
from app.services.learning_progress import mark_attendance, teacher_performance
from app.services.planning import submit_course_day_report
from app.services.training_notifications import attendance_risk

START = datetime(2025, 1, 10, 9, 0, tzinfo=UTC)  # the seeded course day


@pytest.mark.parametrize(("attended", "streak", "low_rate"), [
    ([False, False], True, False),  # two in a row
    ([True, False, False], True, True),  # and 33 % on the third class
    ([True, True, False], False, False),  # 67 %: still fine
    ([True, False, True, False], False, True),  # 50 % after 4 classes: crossed
    ([False, True, False, True, False], False, False),  # stays under 60 %: already told when it crossed
])
def test_attendance_risk(attended, streak, low_rate):
    risk = attendance_risk(attended)
    if not (streak or low_rate):
        assert risk is None
    else:
        assert (risk.streak, risk.low_rate) == (streak, low_rate)


def live_school_with_classes(count: int):
    db = build_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, _lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    days = [day]
    for index in range(1, count):
        extra = SessionCourseDayRecord(
            organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title=f"Séance {index + 1}",
            scheduled_at=START + timedelta(days=index), duration_minutes=60, status="planned",
        )
        db.add(extra)
        days.append(extra)
    db.commit()
    return db, org, teacher, student, classmate, enrollment, classmate_enrollment, days


def close(db, org, teacher, day, present: list[int]):
    for enrollment_id in present:
        mark_attendance(db, ctx(db, org, teacher), day.id, AttendanceMarkPayload(enrollment_id=enrollment_id, status="present"))
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(
        delivery_status="held", summary="Compte rendu de la séance",
    ), now=day.scheduled_at + timedelta(hours=2))


def test_two_absences_in_a_row_warn_the_student_and_the_teacher():
    db, org, teacher, student, classmate, enrollment, classmate_enrollment, days = live_school_with_classes(2)
    close(db, org, teacher, days[0], [classmate_enrollment.id])
    assert notices(db, "attendance.risk:") == 0
    close(db, org, teacher, days[1], [classmate_enrollment.id])
    assert notices(db, f"attendance.risk:{enrollment.id}:{days[1].id}", student.id) == 1
    assert notices(db, f"attendance.risk:{enrollment.id}:{days[1].id}", teacher.id) == 1
    assert notices(db, f"attendance.risk:{classmate_enrollment.id}:") == 0


def test_the_teacher_sees_who_falls_behind_and_when_evaluation_is_too_thin():
    db, org, teacher, student, classmate, enrollment, classmate_enrollment, days = live_school_with_classes(3)
    for day in days:
        close(db, org, teacher, day, [classmate_enrollment.id])
    row = teacher_performance(db, ctx(db, org, teacher)).sessions[0]
    assert row.low_attendance_count == 1
    assert row.badge_hint is not None and "Publiez des quiz ou des TP" in row.badge_hint
