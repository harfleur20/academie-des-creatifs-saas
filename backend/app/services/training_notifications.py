"""Training notifications ported from the mother site's training scheduler.

The hourly job sends course reminders, payment reminders before a due date and
the end-of-session notice. Absences are announced when they are recorded.
Every message is sent once: the in-app event key doubles as the email's guard.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrderInstallmentRecord,
    OrganizationRecord,
    SchoolNotificationRecord,
    SessionCourseDayRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.services.pedagogy_access import current_utc
from app.services.school_communications import queue_school_event
from app.services.school_notifications import dismiss_event, notify_user


@dataclass(frozen=True)
class CourseWindow:
    code: str
    opens_before: timedelta
    closes_before: timedelta
    event_key: str
    title: str


# Wider than the hourly job's period, so a late run still sends the reminder. The mother
# site also reminds 20 minutes before and at the start, which an hourly job cannot time.
COURSE_WINDOWS = (
    CourseWindow("24h", timedelta(hours=24), timedelta(hours=22), "student.course.reminder_24h", "Cours demain"),
    CourseWindow("1h", timedelta(hours=1), timedelta(0), "student.course.reminder_1h", "Cours dans moins d'une heure"),
)
PAYMENT_REMINDER_DAYS = (7, 1)
SESSION_END_NOTICE_DAYS = 7


def _zone(org: OrganizationRecord):
    try:
        return ZoneInfo(org.timezone or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def school_time(org: OrganizationRecord, value: datetime) -> str:
    return current_utc(value).astimezone(_zone(org)).strftime("%d/%m/%Y à %H:%M")


def _school_date(org: OrganizationRecord, value: datetime) -> date:
    return current_utc(value).astimezone(_zone(org)).date()


def _already_sent(db: Session, organization_id: int, user_id: int, event_key: str) -> bool:
    return db.scalar(select(SchoolNotificationRecord.id).where(
        SchoolNotificationRecord.organization_id == organization_id,
        SchoolNotificationRecord.user_id == user_id,
        SchoolNotificationRecord.event_key == event_key,
    )) is not None


def _session_students(db: Session, session: FormationSessionRecord, statuses=("active",)) -> list[UserRecord]:
    return list(db.scalars(
        select(UserRecord)
        .join(EnrollmentRecord, EnrollmentRecord.student_id == UserRecord.id)
        .where(
            EnrollmentRecord.organization_id == session.organization_id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.status.in_(statuses),
            UserRecord.status == "active",
        )
        .distinct()
    ).all())


def process_course_reminders(db: Session, *, now: datetime | None = None) -> int:
    now = current_utc(now)
    days = db.scalars(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.status != "cancelled",
        SessionCourseDayRecord.report_submitted_at.is_(None),
        SessionCourseDayRecord.scheduled_at > now,
        SessionCourseDayRecord.scheduled_at <= now + COURSE_WINDOWS[0].opens_before,
    )).all()
    created = 0
    for day in days:
        starts = current_utc(day.scheduled_at)
        window = next((item for item in COURSE_WINDOWS if item.closes_before < starts - now <= item.opens_before), None)
        session = db.get(FormationSessionRecord, day.session_id)
        org = db.get(OrganizationRecord, day.organization_id)
        if window is None or not org.is_active or session.status in {"cancelled", "completed"}:
            continue
        # A moved course day gets its own reminder.
        event_key = f"course.reminder:{day.id}:{window.code}:{int(starts.timestamp())}"
        starts_at = school_time(org, day.scheduled_at)
        message = f"« {day.title} » ({session.label}) commence le {starts_at}."
        for student in _session_students(db, session):
            if _already_sent(db, org.id, student.id, event_key):
                continue
            notify_user(
                db, organization_id=org.id, user_id=student.id, event_key=event_key, audience="student",
                title=window.title, message=message, category="planning", tone="info",
                action_label="Voir le planning", action_path="/app/student/planning",
            )
            queue_school_event(db, org=org, user=student, event_key=window.event_key, context={
                "course_title": day.title, "session_label": session.label, "starts_at": starts_at,
            })
            created += 1
        if day.teacher_id and not _already_sent(db, org.id, day.teacher_id, event_key):
            notify_user(
                db, organization_id=org.id, user_id=day.teacher_id, event_key=event_key, audience="teacher",
                title=window.title, message=message, category="planning", tone="info",
                action_label="Ouvrir la session", action_path=f"/app/teacher/sessions/{session.id}",
            )
            created += 1
    return created


def process_payment_reminders(db: Session, *, now: datetime | None = None) -> int:
    """Remind a student seven days then one day before an instalment, once the previous one is paid."""
    now = current_utc(now)
    rows = db.scalars(select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.status == "pending",
        OrderInstallmentRecord.due_at > now,
        OrderInstallmentRecord.due_at <= now + timedelta(days=max(PAYMENT_REMINDER_DAYS) + 1),
    )).all()
    created = 0
    for row in rows:
        order = db.get(StudentOrderRecord, row.order_id)
        org = db.get(OrganizationRecord, row.organization_id)
        if order is None or order.status != "partially_paid" or not org.is_active:
            continue
        earlier_unpaid = db.scalar(select(OrderInstallmentRecord.id).where(
            OrderInstallmentRecord.order_id == order.id,
            OrderInstallmentRecord.sequence < row.sequence,
            OrderInstallmentRecord.status != "paid",
        ))
        if earlier_unpaid is not None:
            continue
        days_left = (_school_date(org, row.due_at) - _school_date(org, now)).days
        if days_left not in PAYMENT_REMINDER_DAYS:
            continue
        user = db.get(UserRecord, order.user_id)
        event_key = f"payment.reminder:{row.id}:J-{days_left}"
        if user is None or user.status != "active" or _already_sent(db, org.id, user.id, event_key):
            continue
        formation = db.get(FormationRecord, order.formation_id)
        due_at = school_time(org, row.due_at)
        amount_label = f"{row.amount_cents} {order.currency}"
        notify_user(
            db, organization_id=org.id, user_id=user.id, event_key=event_key, audience="student",
            title="Échéance de paiement demain" if days_left == 1 else "Échéance de paiement dans 7 jours",
            message=f"{amount_label} à régler pour {formation.title} avant le {due_at}.",
            category="payment", tone="warning" if days_left == 1 else "info",
            action_label="Régler cette échéance", action_path="/app/student/payments",
        )
        queue_school_event(db, org=org, user=user, event_key="student.payment.reminder", context={
            "amount_label": amount_label, "formation_title": formation.title, "due_at": due_at,
        })
        created += 1
    return created


def process_session_end_notices(db: Session, *, now: datetime | None = None) -> int:
    """Tell the students once that their session is over, for sessions ended in the last week."""
    today = current_utc(now).date()
    sessions = db.scalars(select(FormationSessionRecord).where(
        FormationSessionRecord.status != "cancelled",
        FormationSessionRecord.end_date < today,
        FormationSessionRecord.end_date >= today - timedelta(days=SESSION_END_NOTICE_DAYS),
    )).all()
    created = 0
    for session in sessions:
        org = db.get(OrganizationRecord, session.organization_id)
        formation = db.get(FormationRecord, session.formation_id)
        if not org.is_active or formation is None or formation.format_type == "ligne":
            continue
        event_key = f"session.ended:{session.id}"
        for student in _session_students(db, session, statuses=("active", "completed")):
            if _already_sent(db, org.id, student.id, event_key):
                continue
            notify_user(
                db, organization_id=org.id, user_id=student.id, event_key=event_key, audience="student",
                title="Votre session est terminée",
                message=f"La session {session.label} de {formation.title} est terminée. Retrouvez vos résultats et votre certificat.",
                category="learning", tone="success", action_label="Voir mes certificats",
                action_path="/app/student/certificates",
            )
            queue_school_event(db, org=org, user=student, event_key="student.session.ended", context={
                "session_label": session.label, "formation_title": formation.title,
            })
            created += 1
    return created


def process_training_notifications(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    counts = {
        "course_reminders": process_course_reminders(db, now=now),
        "payment_reminders": process_payment_reminders(db, now=now),
        "session_end_notices": process_session_end_notices(db, now=now),
    }
    db.commit()
    return counts


def _absence_key(day_id: int, enrollment_id: int) -> str:
    return f"attendance.absent:{day_id}:{enrollment_id}"


def notify_absence(db: Session, *, org: OrganizationRecord, day: SessionCourseDayRecord, enrollment: EnrollmentRecord) -> None:
    """Announce an absence on a held course day, once."""
    student = db.get(UserRecord, enrollment.student_id)
    event_key = _absence_key(day.id, enrollment.id)
    if student is None or student.status != "active" or _already_sent(db, org.id, student.id, event_key):
        return
    starts_at = school_time(org, day.scheduled_at)
    notify_user(
        db, organization_id=org.id, user_id=student.id, event_key=event_key, audience="student",
        title="Absence enregistrée", message=f"Une absence a été enregistrée pour vous au cours « {day.title} » du {starts_at}.",
        category="planning", tone="warning", action_label="Voir mes présences", action_path="/app/student/results",
    )
    queue_school_event(db, org=org, user=student, event_key="student.attendance.absent", context={
        "course_title": day.title, "starts_at": starts_at,
    })


def clear_absence(db: Session, *, organization_id: int, day_id: int, enrollment_id: int) -> None:
    dismiss_event(db, organization_id=organization_id, event_key=_absence_key(day_id, enrollment_id))


def notify_grade(db: Session, *, org: OrganizationRecord, enrollment: EnrollmentRecord, grade_id: int, label: str, score: float, max_score: float) -> None:
    """A new or changed teacher grade, as the mother site's "Nouvelle note"."""
    student = db.get(UserRecord, enrollment.student_id)
    event_key = f"grade.manual:{grade_id}:{score:g}:{max_score:g}"
    if student is None or student.status != "active" or _already_sent(db, org.id, student.id, event_key):
        return
    score_label = f"{score:g}/{max_score:g}"
    notify_user(
        db, organization_id=org.id, user_id=student.id, event_key=event_key, audience="student",
        title="Nouvelle note", message=f"{label} : {score_label}.", category="grade", tone="info",
        action_label="Voir mes résultats", action_path="/app/student/results",
    )
    queue_school_event(db, org=org, user=student, event_key="student.grade.created", context={
        "grade_label": label, "score_label": score_label,
    })


def _session_teacher_ids(db: Session, session: FormationSessionRecord) -> list[int]:
    from app.models.entities import SessionTeacherRecord

    return list(db.scalars(select(SessionTeacherRecord.teacher_id).where(
        SessionTeacherRecord.organization_id == session.organization_id,
        SessionTeacherRecord.session_id == session.id,
    ).distinct()).all())


def notify_new_enrollment(db: Session, *, org: OrganizationRecord, session: FormationSessionRecord, formation: FormationRecord, student: UserRecord) -> None:
    """The mother site emails the session's teachers about each new student."""
    event_key = f"enrollment.created:{session.id}:{student.id}"
    for teacher_id in _session_teacher_ids(db, session):
        teacher = db.get(UserRecord, teacher_id)
        if teacher is None or teacher.status != "active" or _already_sent(db, org.id, teacher.id, event_key):
            continue
        notify_user(
            db, organization_id=org.id, user_id=teacher.id, event_key=event_key, audience="teacher",
            title="Nouvel inscrit", message=f"{student.full_name} rejoint la session {session.label}.",
            category="learning", tone="info", action_label="Voir mes étudiants", action_path="/app/teacher/students",
        )
        queue_school_event(db, org=org, user=teacher, event_key="teacher.enrollment.created", context={
            "student_name": student.full_name, "session_label": session.label, "formation_title": formation.title,
        })


def email_new_submission(db: Session, *, org: OrganizationRecord, teacher_id: int, student: UserRecord, assignment_title: str, session_label: str) -> None:
    """The mother site emails the teacher when a new piece of work awaits correction."""
    teacher = db.get(UserRecord, teacher_id)
    if teacher is None or teacher.status != "active":
        return
    queue_school_event(db, org=org, user=teacher, event_key="teacher.assignment.submitted", context={
        "student_name": student.full_name, "assignment_title": assignment_title, "session_label": session_label,
    })
