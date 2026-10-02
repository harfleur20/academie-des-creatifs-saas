from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    EnrollmentRecord,
    FormationSessionRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
)
from app.schemas.planning import (
    CourseDayCreate,
    CourseDayDraftItem,
    CourseDayRead,
    CourseDayUpdate,
    SessionPlanningRead,
)
from app.services.tenancy import TenantContext


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _session_or_404(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> FormationSessionRecord:
    record = db.scalar(
        select(FormationSessionRecord)
        .options(selectinload(FormationSessionRecord.formation))
        .where(
            FormationSessionRecord.id == session_id,
            FormationSessionRecord.organization_id == tenant.organization_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    return record


def _teacher_assignment(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> SessionTeacherRecord | None:
    return db.scalar(
        select(SessionTeacherRecord).where(
            SessionTeacherRecord.organization_id == tenant.organization_id,
            SessionTeacherRecord.session_id == session_id,
            SessionTeacherRecord.teacher_id == tenant.user.id,
        )
    )


def _student_enrollment(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> EnrollmentRecord | None:
    return db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session_id,
            EnrollmentRecord.student_id == tenant.user.id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )
    )


def _can_manage_school(tenant: TenantContext) -> bool:
    return bool(
        tenant.organization_roles.intersection({"owner", "admin", "manager", "super_admin"})
    )


def _require_planning_view(
    db: Session,
    tenant: TenantContext,
    session: FormationSessionRecord,
) -> None:
    if _can_manage_school(tenant):
        return
    if tenant.has_role("teacher") and _teacher_assignment(db, tenant, session.id):
        return
    if tenant.has_role("student") and _student_enrollment(db, tenant, session.id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Vous n'avez pas accès au planning de cette session.",
    )


def _require_teacher_assignment(
    db: Session,
    tenant: TenantContext,
    session: FormationSessionRecord,
) -> SessionTeacherRecord:
    if not tenant.has_role("teacher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès professeur requis.",
        )
    assignment = _teacher_assignment(db, tenant, session.id)
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette session ne vous est pas affectée.",
        )
    return assignment


def _validate_interval_in_session(
    session: FormationSessionRecord,
    scheduled_at: datetime,
    duration_minutes: int,
) -> None:
    start = _aware(scheduled_at)
    end = start + timedelta(minutes=duration_minutes)

    if start.date() < session.start_date or start.date() > session.end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"La séance doit être planifiée entre le "
                f"{session.start_date.isoformat()} et le {session.end_date.isoformat()}."
            ),
        )
    if end.date() != start.date():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Une séance ne peut pas se terminer le lendemain.",
        )


def _intervals_overlap(
    first_at: datetime,
    first_duration: int,
    second_at: datetime,
    second_duration: int,
) -> bool:
    first_start = _aware(first_at)
    second_start = _aware(second_at)
    first_end = first_start + timedelta(minutes=first_duration)
    second_end = second_start + timedelta(minutes=second_duration)
    return first_start < second_end and second_start < first_end


def _active_course_days(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    *,
    exclude_id: int | None = None,
) -> list[SessionCourseDayRecord]:
    stmt = (
        select(SessionCourseDayRecord)
        .options(selectinload(SessionCourseDayRecord.teacher))
        .where(
            SessionCourseDayRecord.organization_id == tenant.organization_id,
            SessionCourseDayRecord.session_id == session_id,
            SessionCourseDayRecord.status != "cancelled",
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(SessionCourseDayRecord.id != exclude_id)
    return list(db.scalars(stmt).all())


def _ensure_no_overlap(
    *,
    scheduled_at: datetime,
    duration_minutes: int,
    existing_days: list[SessionCourseDayRecord],
) -> None:
    if any(
        _intervals_overlap(
            scheduled_at,
            duration_minutes,
            item.scheduled_at,
            item.duration_minutes,
        )
        for item in existing_days
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce créneau chevauche une séance déjà planifiée.",
        )


def _serialize_day(
    tenant: TenantContext,
    record: SessionCourseDayRecord,
) -> CourseDayRead:
    return CourseDayRead(
        id=record.id,
        session_id=record.session_id,
        teacher_id=record.teacher_id,
        teacher_name=record.teacher.full_name if record.teacher else None,
        title=record.title,
        scheduled_at=record.scheduled_at,
        duration_minutes=record.duration_minutes,
        status=record.status,
        can_edit=(
            tenant.has_role("teacher")
            and record.teacher_id == tenant.user.id
            and not tenant.support_mode
        ),
        created_at=record.created_at,
    )


def get_session_planning(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> SessionPlanningRead:
    session = _session_or_404(db, tenant, session_id)
    _require_planning_view(db, tenant, session)

    days = list(
        db.scalars(
            select(SessionCourseDayRecord)
            .options(selectinload(SessionCourseDayRecord.teacher))
            .where(
                SessionCourseDayRecord.organization_id == tenant.organization_id,
                SessionCourseDayRecord.session_id == session.id,
            )
            .order_by(
                SessionCourseDayRecord.scheduled_at,
                SessionCourseDayRecord.id,
            )
        ).all()
    )
    return SessionPlanningRead(
        session_id=session.id,
        formation_id=session.formation_id,
        formation_title=session.formation.title,
        session_label=session.label,
        session_start_date=session.start_date.isoformat(),
        session_end_date=session.end_date.isoformat(),
        course_days=[_serialize_day(tenant, item) for item in days],
    )


def create_course_day(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    payload: CourseDayCreate,
) -> SessionPlanningRead:
    session = _session_or_404(db, tenant, session_id)
    _require_teacher_assignment(db, tenant, session)

    if tenant.support_mode:
        raise HTTPException(status_code=403, detail="Le mode support est en lecture seule.")
    if session.status in {"cancelled", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette session n'accepte plus de nouvelles séances.",
        )

    _validate_interval_in_session(
        session,
        payload.scheduled_at,
        payload.duration_minutes,
    )
    _ensure_no_overlap(
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        existing_days=_active_course_days(db, tenant, session.id),
    )

    db.add(
        SessionCourseDayRecord(
            organization_id=tenant.organization_id,
            session_id=session.id,
            teacher_id=tenant.user.id,
            title=payload.title,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            status="planned",
        )
    )
    db.commit()
    return get_session_planning(db, tenant, session.id)


def publish_course_day_draft(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    items: list[CourseDayDraftItem],
) -> SessionPlanningRead:
    session = _session_or_404(db, tenant, session_id)
    _require_teacher_assignment(db, tenant, session)

    if tenant.support_mode:
        raise HTTPException(status_code=403, detail="Le mode support est en lecture seule.")
    if session.status in {"cancelled", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette session n'accepte plus de nouvelles séances.",
        )

    ordered = sorted(items, key=lambda item: _aware(item.scheduled_at))
    existing = _active_course_days(db, tenant, session.id)

    for index, item in enumerate(ordered):
        _validate_interval_in_session(
            session,
            item.scheduled_at,
            item.duration_minutes,
        )
        _ensure_no_overlap(
            scheduled_at=item.scheduled_at,
            duration_minutes=item.duration_minutes,
            existing_days=existing,
        )
        for earlier in ordered[:index]:
            if _intervals_overlap(
                item.scheduled_at,
                item.duration_minutes,
                earlier.scheduled_at,
                earlier.duration_minutes,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Deux séances du brouillon se chevauchent.",
                )

    for item in ordered:
        db.add(
            SessionCourseDayRecord(
                organization_id=tenant.organization_id,
                session_id=session.id,
                teacher_id=tenant.user.id,
                title=item.title,
                scheduled_at=item.scheduled_at,
                duration_minutes=item.duration_minutes,
                status="planned",
            )
        )
    db.commit()
    return get_session_planning(db, tenant, session.id)


def update_course_day(
    db: Session,
    tenant: TenantContext,
    course_day_id: int,
    payload: CourseDayUpdate,
) -> SessionPlanningRead:
    record = db.scalar(
        select(SessionCourseDayRecord).where(
            SessionCourseDayRecord.id == course_day_id,
            SessionCourseDayRecord.organization_id == tenant.organization_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Séance introuvable.")

    session = _session_or_404(db, tenant, record.session_id)
    _require_teacher_assignment(db, tenant, session)
    if tenant.support_mode:
        raise HTTPException(status_code=403, detail="Le mode support est en lecture seule.")
    if record.teacher_id != tenant.user.id:
        owner = db.get(type(tenant.user), record.teacher_id) if record.teacher_id else None
        owner_name = owner.full_name if owner else "un autre professeur"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Ce créneau appartient à {owner_name}. "
                "Vous pouvez le consulter, mais pas le modifier."
            ),
        )
    if session.status in {"cancelled", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette session n'accepte plus de modification du planning.",
        )

    values = payload.model_dump(exclude_unset=True)
    next_at = values.get("scheduled_at", record.scheduled_at)
    next_duration = values.get("duration_minutes", record.duration_minutes)

    if values.get("status") != "cancelled":
        _validate_interval_in_session(session, next_at, next_duration)
        _ensure_no_overlap(
            scheduled_at=next_at,
            duration_minutes=next_duration,
            existing_days=_active_course_days(
                db,
                tenant,
                session.id,
                exclude_id=record.id,
            ),
        )

    for key, value in values.items():
        setattr(record, key, value)
    db.commit()
    return get_session_planning(db, tenant, session.id)
