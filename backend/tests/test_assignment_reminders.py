from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_assignment_publication import draft, member, school, sent_events, teaching_outline, tenant_for

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    AssignmentSubmissionRecord,
    EnrollmentRecord,
    SchoolNotificationRecord,
    SessionCourseDayRecord,
)
from app.schemas.assignments import AssignmentUpdate
from app.services.assignment_reminders import process_assignment_reminders
from app.services.assignments import publish_assignment, update_assignment


DUE_24H = "student.assignment.due_24h"
DUE_1H = "student.assignment.due_1h"


def published_due_in(db, org, teacher, session, delta, **values):
    """Publish an assignment due `delta` from now, whatever the session's own dates allow."""
    created = draft(db, org, teacher, session, days=delta / timedelta(days=1), **values)
    publish_assignment(db, tenant_for(db, org, teacher), created.id)
    return created


def notifications(db, student):
    return db.scalars(select(SchoolNotificationRecord).where(SchoolNotificationRecord.user_id == student.id)).all()


@pytest.mark.parametrize(
    "delta, event_key",
    [
        (timedelta(hours=23), DUE_24H),
        (timedelta(hours=24) - timedelta(minutes=1), DUE_24H),
        (timedelta(minutes=50), DUE_1H),
    ],
)
def test_student_is_reminded_before_the_deadline(delta, event_key):
    db, org, teacher, student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, delta)
    assert process_assignment_reminders(db) == 1
    assert [item.recipient for item in sent_events(db, event_key)] == [student.email]
    [notice] = notifications(db, student)
    assert notice.action_path.startswith("/app/student/assignments#assignment-")


@pytest.mark.parametrize("delta", [timedelta(hours=25), timedelta(hours=10), timedelta(minutes=70), timedelta(minutes=-5)])
def test_no_reminder_outside_the_windows(delta):
    db, org, teacher, _student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, delta)
    assert process_assignment_reminders(db) == 0


def test_a_second_run_does_not_repeat_the_reminder():
    db, org, teacher, _student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    assert process_assignment_reminders(db) == 1
    assert process_assignment_reminders(db) == 0
    assert len(sent_events(db, DUE_24H)) == 1


def test_each_window_sends_its_own_reminder():
    db, org, teacher, _student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    assert process_assignment_reminders(db) == 1
    assert process_assignment_reminders(db, now=datetime.now(UTC) + timedelta(hours=22, minutes=30)) == 1
    assert len(sent_events(db, DUE_24H)) == 1
    assert len(sent_events(db, DUE_1H)) == 1


def test_a_moved_deadline_gets_a_new_reminder():
    db, org, teacher, _student, session, _enrollment = school()
    created = published_due_in(db, org, teacher, session, timedelta(hours=23))
    assert process_assignment_reminders(db) == 1
    update_assignment(
        db, tenant_for(db, org, teacher), created.id, AssignmentUpdate(due_date=datetime.now(UTC) + timedelta(hours=23, minutes=30)),
    )
    assert process_assignment_reminders(db) == 1


def test_a_draft_is_never_reminded():
    db, org, teacher, _student, session, _enrollment = school()
    draft(db, org, teacher, session, days=23 / 24)
    assert process_assignment_reminders(db) == 0


def test_student_who_already_submitted_is_left_alone():
    db, org, teacher, student, session, enrollment = school()
    other = member(db, org, "other@school.test", "student")
    db.add(EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=other.id, status="active"))
    created = published_due_in(db, org, teacher, session, timedelta(hours=23))
    db.add(AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=created.id, enrollment_id=enrollment.id,
        file_url="https://files.test/work.pdf", submitted_at=datetime.now(UTC),
    ))
    db.commit()
    assert process_assignment_reminders(db) == 1
    assert [item.recipient for item in sent_events(db, DUE_24H)] == [other.email]


@pytest.mark.parametrize("status", ["suspended", "cancelled", "completed"])
def test_only_active_enrollments_are_reminded(status):
    db, org, teacher, _student, session, enrollment = school()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    enrollment.status = status
    db.commit()
    assert process_assignment_reminders(db) == 0


@pytest.mark.parametrize("status", ["cancelled", "completed"])
def test_closed_session_sends_no_reminder(status):
    db, org, teacher, _student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    session.status = status
    db.commit()
    assert process_assignment_reminders(db) == 0


def test_inactive_school_sends_no_reminder():
    db, org, teacher, _student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    org.is_active = False
    db.commit()
    assert process_assignment_reminders(db) == 0


def test_assignment_not_open_yet_sends_no_reminder():
    db, org, teacher, _student, session, _enrollment = school()
    day = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Séance à venir",
        scheduled_at=datetime.now(UTC) + timedelta(hours=2), duration_minutes=90,
    )
    db.add(day)
    db.commit()
    published_due_in(db, org, teacher, session, timedelta(hours=23), course_day_id=day.id)
    assert process_assignment_reminders(db) == 0


def test_assignment_of_an_unpublished_lesson_sends_no_reminder():
    db, org, teacher, _student, session, _enrollment = school()
    created = published_due_in(db, org, teacher, session, timedelta(hours=23))
    teaching_outline(db, org, teacher, session, created.id)
    assert process_assignment_reminders(db) == 0


def test_deadline_is_written_in_the_school_time_zone():
    db, org, teacher, _student, session, _enrollment = school()
    org.timezone = "Africa/Douala"
    db.commit()
    due = (datetime.now(UTC) + timedelta(hours=23)).replace(second=0, microsecond=0)
    created = published_due_in(db, org, teacher, session, timedelta(hours=23))
    update_assignment(db, tenant_for(db, org, teacher), created.id, AssignmentUpdate(due_date=due))
    process_assignment_reminders(db)
    [email] = sent_events(db, DUE_24H)
    assert (due + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M") in email.body


def test_unknown_time_zone_falls_back_to_utc():
    db, org, teacher, _student, session, _enrollment = school()
    org.timezone = "Mars/Olympus"
    db.commit()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    assert process_assignment_reminders(db) == 1


def test_reminder_route_requires_the_cron_secret(monkeypatch):
    db, org, teacher, student, session, _enrollment = school()
    published_due_in(db, org, teacher, session, timedelta(hours=23))
    monkeypatch.setattr(settings, "billing_cron_secret", "cron-secret")
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        url = "/api/v1/assignments/internal/reminders"
        missing = client.post(url)
        wrong = client.post(url, headers={"X-Billing-Cron-Secret": "nope"})
        accepted = client.post(url, headers={"X-Billing-Cron-Secret": "cron-secret"})
    finally:
        app.dependency_overrides.clear()
    assert (missing.status_code, wrong.status_code) == (401, 401)
    assert accepted.status_code == 200
    assert accepted.json()["reminders"] == 1
    assert len(notifications(db, student)) == 1
