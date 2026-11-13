"""The student's transcript ("relevé de notes"), for one enrollment: one formation, one session.

Every grade of the enrollment, grouped by kind, with the official average (the one the
badge and the pedagogical follow-up use: automatic quiz grades are shown but left out),
the attendance and the badge reached. The student reads their own transcripts, the
school's management any of its students', a teacher those of the sessions they teach.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    OrganizationStudentProfileRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.transcripts import TranscriptGroupRead, TranscriptLineRead, TranscriptRead, TranscriptSummaryRead
from app.services.learning_progress import _attendance_stats, badge_for_enrollment
from app.services.public_catalog import school_white_label
from app.services.school_branding import branding_snapshot
from app.services.tenancy import TenantContext

MANAGER_ROLES = frozenset({"owner", "admin", "manager", "super_admin"})
VISIBLE_STATUSES = ("active", "completed", "suspended_payment")
FORMAT_LABELS = {"live": "Live", "ligne": "En ligne", "presentiel": "Présentiel"}
GROUP_LABELS = {
    "assignments": "Travaux pratiques",
    "exams": "Examens",
    "session_grades": "Notes de séance",
    "teacher_grades": "Notes du professeur",
    "quizzes": "Quiz (hors moyenne)",
}
MENTIONS = ((16, "Très bien"), (14, "Bien"), (12, "Assez bien"), (10, "Passable"))
# Written by the platform, not by the teacher: the transcript keeps only the teacher's comments.
SYSTEM_NOTES = frozenset({"Note automatique calculée depuis le meilleur score.", "Note issue de la correction du devoir."})
# The group already says what each grade is.
LABEL_PREFIXES = ("Examen : ", "Quiz : ", "Devoir : ")


def mention_for(average_20: float | None) -> str | None:
    if average_20 is None:
        return None
    return next((label for floor, label in MENTIONS if average_20 >= floor), None)


def _counts(row: GradeRecord) -> bool:
    """The grades of the official average (app/services/grades.py: grade_average_pct)."""
    return bool(row.max_score and row.max_score > 0) and not (row.source_type == "quiz" and row.label.startswith("Quiz"))


def _average_20(rows: list[GradeRecord]) -> float | None:
    values = [row.score / row.max_score * 20 for row in rows if _counts(row)]
    return round(sum(values) / len(values), 2) if values else None


def _grades(db: Session, organization_id: int, enrollment_id: int) -> list[GradeRecord]:
    return list(db.scalars(select(GradeRecord).where(
        GradeRecord.organization_id == organization_id,
        GradeRecord.enrollment_id == enrollment_id,
    )).all())


def _group_of(row: GradeRecord) -> str:
    if row.source_type == "assignment":
        return "assignments"
    if row.source_type == "quiz":
        return "quizzes" if row.label.startswith("Quiz") else "exams"
    return "session_grades" if row.course_day_id else "teacher_grades"


def readable_enrollment(db: Session, tenant: TenantContext, enrollment_id: int) -> EnrollmentRecord:
    """The enrollment, when this person may read its transcript."""
    enrollment = db.scalar(select(EnrollmentRecord).where(
        EnrollmentRecord.id == enrollment_id,
        EnrollmentRecord.organization_id == tenant.organization_id,
        EnrollmentRecord.status.in_(VISIBLE_STATUSES),
    ))
    if enrollment is None:
        raise HTTPException(404, "Relevé introuvable.")
    if tenant.organization_roles & MANAGER_ROLES or enrollment.student_id == tenant.user.id:
        return enrollment
    if tenant.has_role("teacher") and db.scalar(select(SessionTeacherRecord.id).where(
        SessionTeacherRecord.organization_id == tenant.organization_id,
        SessionTeacherRecord.session_id == enrollment.session_id,
        SessionTeacherRecord.teacher_id == tenant.user.id,
    )) is not None:
        return enrollment
    raise HTTPException(403, "Ce relevé ne vous est pas accessible.")


def _status(enrollment: EnrollmentRecord, formation: FormationRecord, session: FormationSessionRecord, today: date) -> str:
    if enrollment.status == "completed":
        return "final"
    if formation.format_type != "ligne" and session.end_date < today:
        return "final"
    return "provisional"


def build_transcript(db: Session, tenant: TenantContext, enrollment: EnrollmentRecord) -> TranscriptRead:
    org = tenant.organization
    now = datetime.now(UTC)
    session = db.get(FormationSessionRecord, enrollment.session_id)
    formation = db.get(FormationRecord, session.formation_id)
    student = db.get(UserRecord, enrollment.student_id)
    profile = db.scalar(select(OrganizationStudentProfileRecord).where(
        OrganizationStudentProfileRecord.organization_id == org.id,
        OrganizationStudentProfileRecord.user_id == enrollment.student_id,
    ))
    snapshot = branding_snapshot(db, org)

    rows = _grades(db, org.id, enrollment.id)
    day_dates = {
        day.id: day.scheduled_at.date()
        for day in db.scalars(select(SessionCourseDayRecord).where(
            SessionCourseDayRecord.id.in_({row.course_day_id for row in rows if row.course_day_id}),
        ))
    } if any(row.course_day_id for row in rows) else {}
    grouped: dict[str, list[TranscriptLineRead]] = {key: [] for key in GROUP_LABELS}
    for row in rows:
        if not row.max_score or row.max_score <= 0:
            continue
        group = _group_of(row)
        when = day_dates.get(row.course_day_id) if row.course_day_id else None
        label = next((row.label[len(prefix):] for prefix in LABEL_PREFIXES if row.label.startswith(prefix)), row.label)
        grouped[group].append(TranscriptLineRead(
            label=label,
            date=when or (row.updated_at or row.created_at).date(),
            score=row.score,
            max_score=row.max_score,
            score_20=round(row.score / row.max_score * 20, 2),
            note="" if (row.note or "").strip() in SYSTEM_NOTES else (row.note or "").strip(),
            counted=_counts(row),
        ))
    groups = [
        TranscriptGroupRead(key=key, label=GROUP_LABELS[key], lines=sorted(lines, key=lambda line: (line.date or date.min, line.label)))
        for key, lines in grouped.items() if lines
    ]

    average_20 = _average_20(rows)
    counted, attended = _attendance_stats(db, tenant, enrollment)
    try:
        badge_label = badge_for_enrollment(db, tenant, enrollment).label
    except HTTPException:
        badge_label = None

    return TranscriptRead(
        enrollment_id=enrollment.id,
        status=_status(enrollment, formation, session, now.date()),
        issued_at=now,
        school_name=str(snapshot.get("school_name") or org.name),
        logo_url=snapshot.get("logo_url"),
        legal_name=snapshot.get("legal_name"),
        legal_address=snapshot.get("legal_address"),
        signer_name=snapshot.get("signer_name"),
        signer_title=snapshot.get("signer_title"),
        white_label=school_white_label(db, org.id),
        student_name=student.full_name,
        student_code=profile.student_code if profile else None,
        formation_title=formation.title,
        format_label=FORMAT_LABELS.get(formation.format_type, formation.format_type),
        training_hours=formation.training_hours,
        session_label="Accès en ligne" if formation.format_type == "ligne" else session.label,
        session_start=session.start_date,
        session_end=session.end_date,
        groups=groups,
        average_20=average_20,
        mention=mention_for(average_20),
        counted_sessions=counted,
        attended_sessions=attended,
        attendance_pct=round(attended / counted * 100, 1) if counted else None,
        badge_label=badge_label,
    )


def my_transcripts(db: Session, tenant: TenantContext) -> list[TranscriptSummaryRead]:
    """The student's own enrollments, the latest session first."""
    rows = db.execute(
        select(EnrollmentRecord, FormationSessionRecord, FormationRecord)
        .join(FormationSessionRecord, FormationSessionRecord.id == EnrollmentRecord.session_id)
        .join(FormationRecord, FormationRecord.id == FormationSessionRecord.formation_id)
        .where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.student_id == tenant.user.id,
            EnrollmentRecord.status.in_(VISIBLE_STATUSES),
        )
        .order_by(FormationSessionRecord.start_date.desc(), EnrollmentRecord.id.desc())
    ).all()
    today = datetime.now(UTC).date()
    summaries = []
    for enrollment, session, formation in rows:
        summaries.append(TranscriptSummaryRead(
            enrollment_id=enrollment.id,
            formation_title=formation.title,
            session_label="Accès en ligne" if formation.format_type == "ligne" else session.label,
            status=_status(enrollment, formation, session, today),
            average_20=_average_20(_grades(db, tenant.organization_id, enrollment.id)),
        ))
    return summaries
