"""Remind students of the assignments they still have to hand in."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationRecord,
    SchoolNotificationRecord,
    UserRecord,
)
from app.services.assignments import assignment_open_for_students, due_date_label
from app.services.pedagogy_access import current_utc
from app.services.school_communications import queue_school_event
from app.services.school_notifications import notify_user


@dataclass(frozen=True)
class ReminderWindow:
    code: str
    opens_before: timedelta
    closes_before: timedelta
    event_key: str
    title: str


# The windows are wider than the job's period, so a late run still sends the reminder.
WINDOWS = (
    ReminderWindow("24h", timedelta(hours=24), timedelta(hours=22), "student.assignment.due_24h", "Devoir à rendre dans 24 h"),
    ReminderWindow("1h", timedelta(hours=1), timedelta(0), "student.assignment.due_1h", "Devoir à rendre dans moins d'une heure"),
)


def _window_for(remaining: timedelta) -> ReminderWindow | None:
    return next((item for item in WINDOWS if item.closes_before < remaining <= item.opens_before), None)


def _students_to_remind(db: Session, assignment: AssignmentRecord) -> list[UserRecord]:
    submitted = select(AssignmentSubmissionRecord.enrollment_id).where(
        AssignmentSubmissionRecord.organization_id == assignment.organization_id,
        AssignmentSubmissionRecord.assignment_id == assignment.id,
    )
    return list(db.scalars(
        select(UserRecord)
        .join(EnrollmentRecord, EnrollmentRecord.student_id == UserRecord.id)
        .where(
            EnrollmentRecord.organization_id == assignment.organization_id,
            EnrollmentRecord.session_id == assignment.session_id,
            EnrollmentRecord.status == "active",
            EnrollmentRecord.id.not_in(submitted),
            UserRecord.status == "active",
        )
    ).all())


def _already_reminded(db: Session, organization_id: int, user_id: int, event_key: str) -> bool:
    return db.scalar(select(SchoolNotificationRecord.id).where(
        SchoolNotificationRecord.organization_id == organization_id,
        SchoolNotificationRecord.user_id == user_id,
        SchoolNotificationRecord.event_key == event_key,
    )) is not None


def process_assignment_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Queue the due reminders of every school and return how many were created."""
    now = current_utc(now)
    assignments = db.scalars(select(AssignmentRecord).where(
        AssignmentRecord.publication_status == "published",
        AssignmentRecord.due_date > now,
        AssignmentRecord.due_date <= now + WINDOWS[0].opens_before,
    )).all()
    created = 0
    for assignment in assignments:
        due = current_utc(assignment.due_date)
        window = _window_for(due - now)
        session = db.get(FormationSessionRecord, assignment.session_id)
        org = db.get(OrganizationRecord, assignment.organization_id)
        if window is None or not org.is_active or session.status == "completed":
            continue
        formation = db.get(FormationRecord, session.formation_id)
        if not assignment_open_for_students(db, session, formation, assignment, now=now):
            continue
        due_at = due_date_label(org, assignment.due_date)
        # A moved deadline gets its own reminder.
        event_key = f"assignment.due:{assignment.id}:{window.code}:{int(due.timestamp())}"
        for student in _students_to_remind(db, assignment):
            if _already_reminded(db, org.id, student.id, event_key):
                continue
            notify_user(
                db, organization_id=org.id, user_id=student.id, event_key=event_key, audience="student",
                title=window.title, message=f"« {assignment.title} » est à remettre avant le {due_at}.",
                category="assignment", tone="warning", action_label="Rendre le devoir",
                action_path=f"/app/student/assignments#assignment-{assignment.id}",
            )
            queue_school_event(
                db, org=org, user=student, event_key=window.event_key,
                context={"assignment_title": assignment.title, "due_at": due_at},
            )
            created += 1
    db.commit()
    return created
