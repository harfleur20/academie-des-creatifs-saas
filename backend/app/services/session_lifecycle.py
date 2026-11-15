"""Session lifecycle ported from the mother site's formation_sessions.

- Enrollment stays possible until five days after the start, unless the school set
  its own closing date.
- The hourly job completes the sessions whose end date has passed, freezes the
  program of the guided sessions that have started, and warns the school once
  when a started program is still incomplete.
- A change of dates, place or status is announced to the students and teachers.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationRecord,
    SchoolNotificationRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.services.pedagogy_access import current_utc, dashboard_type, learning_is_open
from app.services.program_versions import active_program_version, ensure_program_frozen, program_readiness
from app.services.school_communications import queue_school_event
from app.services.school_notifications import notify_school_managers, notify_user

SESSION_GRACE_DAYS = 5


def enrollment_closes_at(session: FormationSessionRecord) -> datetime:
    """When enrollment closes: the school's own date, or the end of the fifth day after the start."""
    if session.enrollment_close_at is not None:
        return current_utc(session.enrollment_close_at)
    return datetime.combine(session.start_date + timedelta(days=SESSION_GRACE_DAYS), time.max, tzinfo=UTC)


def _date_label(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def notify_session_change(
    db: Session,
    *,
    org: OrganizationRecord,
    session: FormationSessionRecord,
    formation: FormationRecord,
    change_key: str,
) -> None:
    """Tell the enrolled students and the session's teachers, as the mother site does."""
    cancelled = session.status == "cancelled"
    title = "Votre session est annulée" if cancelled else "Votre session a été modifiée"
    period = f"du {_date_label(session.start_date)} au {_date_label(session.end_date)}"
    place = f", {session.campus_label}" if session.campus_label else ""
    message = (
        f"La session « {session.label} » de {formation.title} est annulée."
        if cancelled
        else f"« {formation.title} - {session.label} » : {period}{place}."
    )
    students = db.scalars(select(UserRecord).join(EnrollmentRecord, EnrollmentRecord.student_id == UserRecord.id).where(
        EnrollmentRecord.organization_id == org.id,
        EnrollmentRecord.session_id == session.id,
        EnrollmentRecord.status.in_(["active", "completed", "suspended_payment"]),
        UserRecord.status == "active",
    ).distinct()).all()
    event_key = f"session.changed:{session.id}:{change_key}"
    for student in students:
        notify_user(
            db, organization_id=org.id, user_id=student.id, event_key=event_key, audience="student",
            title=title, message=message, category="planning", tone="warning",
            action_label="Mes formations", action_path="/app/student/formations",
        )
        queue_school_event(db, org=org, user=student, event_key="student.session.updated", context={
            "formation_title": formation.title, "session_label": session.label,
            "change_summary": "La session est annulée." if cancelled else f"Elle se tient {period}{place}.",
        })
    teacher_ids = db.scalars(select(SessionTeacherRecord.teacher_id).where(
        SessionTeacherRecord.organization_id == org.id, SessionTeacherRecord.session_id == session.id,
    ).distinct()).all()
    for teacher_id in teacher_ids:
        notify_user(
            db, organization_id=org.id, user_id=teacher_id, event_key=event_key, audience="teacher",
            title="Session annulée" if cancelled else "Session mise à jour", message=message,
            category="planning", tone="warning" if cancelled else "info",
            action_label="Voir la session", action_path=f"/app/teacher/sessions/{session.id}",
        )


def _already_warned(db: Session, organization_id: int, event_key: str) -> bool:
    return db.scalar(select(SchoolNotificationRecord.id).where(
        SchoolNotificationRecord.organization_id == organization_id,
        SchoolNotificationRecord.event_key == event_key,
    )) is not None


def process_session_lifecycle(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    current = current_utc(now)
    today = current.date()
    counts = {"completed": 0, "frozen": 0, "incomplete_warnings": 0}
    sessions = db.scalars(select(FormationSessionRecord).where(
        FormationSessionRecord.status.not_in(["cancelled", "completed"]),
        FormationSessionRecord.start_date <= today,
    )).all()
    for session in sessions:
        formation = db.get(FormationRecord, session.formation_id)
        org = db.get(OrganizationRecord, session.organization_id)
        if formation is None or org is None or not org.is_active or formation.format_type == "ligne":
            continue
        if session.end_date < today:
            session.status = "completed"
            counts["completed"] += 1
            continue
        if dashboard_type(formation) != "guided" or not learning_is_open(formation, session, now=current):
            continue
        if active_program_version(db, session.id) is not None:
            continue
        if ensure_program_frozen(db, session, formation, now=current) is not None:
            counts["frozen"] += 1
            continue
        event_key = f"program.incomplete:{session.id}"
        if _already_warned(db, org.id, event_key):
            continue
        missing = "; ".join(program_readiness(db, session, formation).missing)
        notify_school_managers(
            db, organization_id=org.id, event_key=event_key, title="Programme de session incomplet",
            message=f"« {formation.title} - {session.label} » a commencé, mais son programme est incomplet : {missing}. Les badges attendent qu'il soit complet.",
            category="learning", tone="warning", action_label="Ouvrir la formation",
            action_path=f"/app/manage/formations/{formation.id}",
        )
        counts["incomplete_warnings"] += 1
    db.commit()
    return counts
