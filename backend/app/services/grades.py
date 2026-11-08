from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    EnrollmentRecord,
    FormationSessionRecord,
    GradeRecord,
    SessionCourseDayRecord,
    UserRecord,
)
from app.schemas.academic import (
    GradebookCourseDayRead,
    GradebookStudentRead,
    TeacherGradebookRead,
    TeacherGradeEntry,
    TeacherGradeRead,
)
from app.services.academic_access import (
    formation_for_session,
    get_session,
    require_owned_course_day,
    require_teacher_assignment,
)
from app.services.pedagogy_access import current_utc, dashboard_type, session_ends_at
from app.services.training_notifications import notify_grade
from app.services.tenancy import TenantContext


def upsert_grade(
    db: Session,
    *,
    organization_id: int,
    session_id: int,
    enrollment_id: int,
    teacher_id: int | None,
    source_type: str,
    source_id: int | None,
    label: str,
    score: float,
    max_score: float = 20,
    note: str = "",
) -> GradeRecord:
    row = None
    if source_id is not None:
        row = db.scalar(
            select(GradeRecord).where(
                GradeRecord.organization_id == organization_id,
                GradeRecord.enrollment_id == enrollment_id,
                GradeRecord.source_type == source_type,
                GradeRecord.source_id == source_id,
            )
        )

    if row is None:
        row = GradeRecord(
            organization_id=organization_id,
            session_id=session_id,
            enrollment_id=enrollment_id,
            teacher_id=teacher_id,
            source_type=source_type,
            source_id=source_id,
            label=label,
            score=score,
            max_score=max_score,
            note=note,
        )
        db.add(row)
    else:
        row.teacher_id = teacher_id
        row.label = label
        row.score = score
        row.max_score = max_score
        row.note = note

    return row


def grade_average_pct(db: Session, *, organization_id: int, enrollment_id: int) -> float | None:
    rows = list(
        db.scalars(
            select(GradeRecord).where(
                GradeRecord.organization_id == organization_id,
                GradeRecord.enrollment_id == enrollment_id,
            )
        ).all()
    )
    # Quiz mastery has its own badge measure: counting its automatic grade here
    # would reward the same proof twice. Exams stay in the average.
    values = [
        (row.score / row.max_score) * 100
        for row in rows
        if row.max_score and row.max_score > 0
        and not (row.source_type == "quiz" and row.label.startswith("Quiz"))
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _course_day_open_for_grades(
    session: FormationSessionRecord,
    day: SessionCourseDayRecord,
    now: datetime,
) -> bool:
    if session.status == "cancelled" or day.status == "cancelled" or day.delivery_status == "not_held":
        return False
    return now >= current_utc(day.scheduled_at) + timedelta(minutes=day.duration_minutes)


def _session_open_for_grades(session: FormationSessionRecord, now: datetime) -> bool:
    return session.status != "cancelled" and now >= session_ends_at(session)


def teacher_gradebook(db: Session, tenant: TenantContext, session_id: int) -> TeacherGradebookRead:
    require_teacher_assignment(db, tenant, session_id)
    session = get_session(db, tenant, session_id)
    now = datetime.now(UTC)
    enrollments = db.execute(
        select(EnrollmentRecord.id, EnrollmentRecord.status, UserRecord.full_name)
        .join(UserRecord, UserRecord.id == EnrollmentRecord.student_id)
        .where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session_id,
        )
        .order_by(UserRecord.full_name)
    ).all()
    days = db.scalars(
        select(SessionCourseDayRecord)
        .where(
            SessionCourseDayRecord.organization_id == tenant.organization_id,
            SessionCourseDayRecord.session_id == session_id,
        )
        .order_by(SessionCourseDayRecord.scheduled_at)
    ).all()
    rows = db.scalars(
        select(GradeRecord)
        .where(
            GradeRecord.organization_id == tenant.organization_id,
            GradeRecord.session_id == session_id,
        )
        .order_by(GradeRecord.label, GradeRecord.id)
    ).all()
    names = {item.id: item.full_name for item in enrollments}
    day_titles = {item.id: item.title for item in days}
    teachers = {
        item.id: item.full_name
        for item in db.scalars(select(UserRecord).where(
            UserRecord.id.in_({row.teacher_id for row in rows if row.teacher_id is not None})
        )).all()
    }
    return TeacherGradebookRead(
        session_id=session_id,
        can_grade_session=_session_open_for_grades(session, now),
        students=[
            GradebookStudentRead(enrollment_id=item.id, student_name=item.full_name)
            for item in enrollments
            if item.status in {"active", "completed"}
        ],
        course_days=[
            GradebookCourseDayRead(
                id=item.id,
                title=item.title,
                scheduled_at=item.scheduled_at,
                can_grade=item.teacher_id == tenant.user.id and _course_day_open_for_grades(session, item, now),
            )
            for item in days
            if item.status != "cancelled"
        ],
        grades=[
            TeacherGradeRead(
                id=row.id,
                enrollment_id=row.enrollment_id,
                student_name=names.get(row.enrollment_id, "Étudiant"),
                course_day_id=row.course_day_id,
                course_day_title=day_titles.get(row.course_day_id),
                teacher_name=teachers.get(row.teacher_id),
                is_own=row.teacher_id == tenant.user.id,
                source_type=row.source_type,
                label=row.label,
                score=row.score,
                max_score=row.max_score,
                note=row.note,
            )
            for row in rows
        ],
    )


def _validate_grade_entry(
    db: Session,
    tenant: TenantContext,
    session: FormationSessionRecord,
    entry: TeacherGradeEntry,
    enrollment_ids: set[int],
    now: datetime,
) -> None:
    if entry.enrollment_id not in enrollment_ids:
        raise HTTPException(422, "Cet étudiant n'appartient pas à la session.")
    if not entry.label.strip():
        raise HTTPException(422, "Saisissez un intitulé d'évaluation.")
    if entry.score > entry.max_score:
        raise HTTPException(422, "La note ne peut pas dépasser le barème.")
    day = require_owned_course_day(db, tenant, session.id, entry.course_day_id)
    if day is None:
        if not _session_open_for_grades(session, now):
            raise HTTPException(409, "Les notes globales ne sont disponibles qu'après la fin de la session.")
    elif not _course_day_open_for_grades(session, day, now):
        raise HTTPException(409, "Les notes de cette séance ouvrent à sa fin, si elle a eu lieu.")


def save_teacher_grades(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    entries: list[TeacherGradeEntry],
) -> TeacherGradebookRead:
    require_teacher_assignment(db, tenant, session_id)
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")
    session = get_session(db, tenant, session_id)
    if dashboard_type(formation_for_session(db, tenant, session_id)) != "guided":
        raise HTTPException(409, "Les notes du professeur concernent les formations live et présentiel.")
    enrollment_ids = set(db.scalars(select(EnrollmentRecord.id).where(
        EnrollmentRecord.organization_id == tenant.organization_id,
        EnrollmentRecord.session_id == session_id,
        EnrollmentRecord.status.in_(["active", "completed"]),
    )).all())
    now = datetime.now(UTC)
    for entry in entries:
        _validate_grade_entry(db, tenant, session, entry, enrollment_ids, now)

    for entry in entries:
        label = entry.label.strip()
        row = db.scalar(select(GradeRecord).where(
            GradeRecord.organization_id == tenant.organization_id,
            GradeRecord.session_id == session_id,
            GradeRecord.enrollment_id == entry.enrollment_id,
            GradeRecord.source_type == "manual",
            GradeRecord.teacher_id == tenant.user.id,
            GradeRecord.course_day_id == entry.course_day_id,
            GradeRecord.label == label,
        ))
        if row is None:
            row = GradeRecord(
                organization_id=tenant.organization_id,
                session_id=session_id,
                enrollment_id=entry.enrollment_id,
                course_day_id=entry.course_day_id,
                teacher_id=tenant.user.id,
                source_type="manual",
                label=label,
                score=entry.score,
            )
            db.add(row)
        row.score = entry.score
        row.max_score = entry.max_score
        row.note = entry.note
        db.flush()
        notify_grade(
            db, org=tenant.organization, enrollment=db.get(EnrollmentRecord, entry.enrollment_id),
            grade_id=row.id, label=label, score=row.score, max_score=row.max_score,
        )
    db.commit()
    return teacher_gradebook(db, tenant, session_id)
