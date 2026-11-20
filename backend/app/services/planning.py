from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    AttendanceRecord,
    CourseDayFeedbackRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.planning import (
    SchoolMissingCourseDayReportRead,
    CourseDayCreate,
    CourseDayDraftItem,
    CourseDayFeedbackRead,
    CourseDayFeedbackReviewRead,
    CourseDayFeedbackSubmit,
    SchoolCourseDayReportRead,
    CourseDayRead,
    CourseDayReportSubmit,
    CourseDayUpdate,
    SessionPlanningRead,
)
from app.services.school_communications import queue_session_students_event
from app.services.school_notifications import notify_session_students
from app.services.live_classes import live_attendance_evidence, live_course_window, live_provider_configured, prefill_live_status
from app.services.plan_limits import allowance
from app.services.subscriptions import get_effective_plan
from app.services.tenancy import TenantContext
from app.services.training_notifications import notify_absence, notify_attendance_risks, school_time



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


def _require_live_class_length(db: Session, session: FormationSessionRecord, duration_minutes: int) -> None:
    """A live class follows its plan's live_class_hours limit; in person, any length."""
    if session.formation.format_type != "live":
        return
    rule = allowance(get_effective_plan(db, session.organization_id), "live_class_hours")
    if rule.enabled and rule.limit is not None and duration_minutes > rule.limit * 60:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Un cours en live dure {rule.limit} h au plus. Découpez-le en plusieurs séances.",
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
    *, feedback_count: int = 0, average_rating: float | None = None,
    my_feedback: CourseDayFeedbackRecord | None = None,
) -> CourseDayRead:
    can_read_report = (
        (tenant.has_role("teacher") and record.teacher_id == tenant.user.id)
        or bool(tenant.organization_roles.intersection({"owner", "admin", "manager", "super_admin"}))
    )
    return CourseDayRead(
        id=record.id,
        session_id=record.session_id,
        teacher_id=record.teacher_id,
        teacher_name=record.teacher.full_name if record.teacher else None,
        title=record.title,
        scheduled_at=record.scheduled_at,
        duration_minutes=record.duration_minutes,
        status=record.status,
        started_at=record.started_at,
        delivery_status=record.delivery_status,
        report_summary=record.report_summary if can_read_report else None,
        report_difficulties=record.report_difficulties if can_read_report else None,
        report_homework=record.report_homework if can_read_report else None,
        report_attendance_notes=record.report_attendance_notes if can_read_report else None,
        report_submitted_at=record.report_submitted_at,
        feedback_count=feedback_count,
        average_rating=average_rating,
        my_feedback=_serialize_feedback(my_feedback) if my_feedback else None,
        can_edit=(
            tenant.has_role("teacher")
            and record.teacher_id == tenant.user.id
            and not tenant.support_mode
            and record.report_submitted_at is None
        ),
        created_at=record.created_at,
    )


def _serialize_feedback(record: CourseDayFeedbackRecord) -> CourseDayFeedbackRead:
    return CourseDayFeedbackRead(
        id=record.id, rating=record.rating, delivery_status=record.delivery_status,
        comment=record.comment, created_at=record.created_at, updated_at=record.updated_at,
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
    day_ids = [day.id for day in days]
    feedback_summary: dict[int, tuple[int, float | None]] = {}
    my_feedback: dict[int, CourseDayFeedbackRecord] = {}
    if day_ids:
        feedback_summary = {
            day_id: (count, round(float(average), 1) if average is not None else None)
            for day_id, count, average in db.execute(select(
                CourseDayFeedbackRecord.course_day_id,
                func.count(CourseDayFeedbackRecord.id),
                func.avg(CourseDayFeedbackRecord.rating),
            ).where(
                CourseDayFeedbackRecord.organization_id == tenant.organization_id,
                CourseDayFeedbackRecord.course_day_id.in_(day_ids),
            ).group_by(CourseDayFeedbackRecord.course_day_id)).all()
        }
        enrollment = _student_enrollment(db, tenant, session.id) if tenant.has_role("student") else None
        if enrollment:
            my_feedback = {item.course_day_id: item for item in db.scalars(select(CourseDayFeedbackRecord).where(
                CourseDayFeedbackRecord.organization_id == tenant.organization_id,
                CourseDayFeedbackRecord.enrollment_id == enrollment.id,
                CourseDayFeedbackRecord.course_day_id.in_(day_ids),
            )).all()}
    return SessionPlanningRead(
        session_id=session.id,
        formation_id=session.formation_id,
        formation_title=session.formation.title,
        format_type=session.formation.format_type,
        live_enabled=live_provider_configured() if session.formation.format_type == "live" else False,
        session_label=session.label,
        session_start_date=session.start_date.isoformat(),
        session_end_date=session.end_date.isoformat(),
        course_days=[_serialize_day(
            tenant, item, feedback_count=feedback_summary.get(item.id, (0, None))[0],
            average_rating=feedback_summary.get(item.id, (0, None))[1],
            my_feedback=my_feedback.get(item.id),
        ) for item in days],
    )


def submit_course_day_feedback(
    db: Session, tenant: TenantContext, course_day_id: int, payload: CourseDayFeedbackSubmit,
    *, now: datetime | None = None,
) -> SessionPlanningRead:
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == course_day_id,
        SessionCourseDayRecord.organization_id == tenant.organization_id,
    ))
    if day is None:
        raise HTTPException(404, "Séance introuvable.")
    if day.status == "cancelled":
        raise HTTPException(409, "Aucun avis n'est attendu pour une séance annulée.")
    enrollment = _student_enrollment(db, tenant, day.session_id) if tenant.has_role("student") else None
    if enrollment is None:
        raise HTTPException(403, "Vous n'êtes pas inscrit à cette séance.")
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")
    if _aware(now or datetime.now(UTC)) < _aware(day.scheduled_at) + timedelta(minutes=day.duration_minutes):
        raise HTTPException(409, "Vous pourrez noter cette séance une fois terminée.")
    feedback = db.scalar(select(CourseDayFeedbackRecord).where(
        CourseDayFeedbackRecord.organization_id == tenant.organization_id,
        CourseDayFeedbackRecord.course_day_id == day.id,
        CourseDayFeedbackRecord.enrollment_id == enrollment.id,
    ))
    if feedback is None:
        feedback = CourseDayFeedbackRecord(
            organization_id=tenant.organization_id, session_id=day.session_id,
            course_day_id=day.id, enrollment_id=enrollment.id,
        )
    feedback.rating = payload.rating
    feedback.delivery_status = payload.delivery_status
    feedback.comment = payload.comment
    db.add(feedback)
    db.commit()
    return get_session_planning(db, tenant, day.session_id)


def list_course_day_feedback(
    db: Session, tenant: TenantContext, course_day_id: int,
) -> list[CourseDayFeedbackReviewRead]:
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == course_day_id,
        SessionCourseDayRecord.organization_id == tenant.organization_id,
    ))
    if day is None:
        raise HTTPException(404, "Séance introuvable.")
    if not _can_manage_school(tenant):
        raise HTTPException(403, "Consultation des avis réservée à l'administration.")
    rows = db.execute(select(CourseDayFeedbackRecord, UserRecord.full_name)
        .join(EnrollmentRecord, EnrollmentRecord.id == CourseDayFeedbackRecord.enrollment_id)
        .join(UserRecord, UserRecord.id == EnrollmentRecord.student_id)
        .where(
            CourseDayFeedbackRecord.organization_id == tenant.organization_id,
            CourseDayFeedbackRecord.course_day_id == day.id,
            EnrollmentRecord.organization_id == tenant.organization_id,
        ).order_by(CourseDayFeedbackRecord.created_at.desc())).all()
    return [CourseDayFeedbackReviewRead(**_serialize_feedback(item).model_dump(), student_name=name) for item, name in rows]


def list_school_course_day_reports(
    db: Session, tenant: TenantContext,
) -> list[SchoolCourseDayReportRead]:
    if not _can_manage_school(tenant):
        raise HTTPException(403, "Accès gestion requis.")
    rows = db.execute(select(
        SessionCourseDayRecord, FormationSessionRecord.label,
        FormationRecord.title, UserRecord.full_name, FormationRecord.id,
    ).join(
        FormationSessionRecord, FormationSessionRecord.id == SessionCourseDayRecord.session_id,
    ).join(
        FormationRecord, FormationRecord.id == FormationSessionRecord.formation_id,
    ).outerjoin(
        UserRecord, UserRecord.id == SessionCourseDayRecord.teacher_id,
    ).where(
        SessionCourseDayRecord.organization_id == tenant.organization_id,
        FormationSessionRecord.organization_id == tenant.organization_id,
        FormationRecord.organization_id == tenant.organization_id,
        SessionCourseDayRecord.report_submitted_at.is_not(None),
    ).order_by(SessionCourseDayRecord.report_submitted_at.desc())).all()
    day_ids = [day.id for day, *_ in rows]
    feedback_summary: dict[int, tuple[int, float | None]] = {}
    if day_ids:
        feedback_summary = {
            day_id: (count, round(float(average), 1) if average is not None else None)
            for day_id, count, average in db.execute(select(
                CourseDayFeedbackRecord.course_day_id,
                func.count(CourseDayFeedbackRecord.id),
                func.avg(CourseDayFeedbackRecord.rating),
            ).where(
                CourseDayFeedbackRecord.organization_id == tenant.organization_id,
                CourseDayFeedbackRecord.course_day_id.in_(day_ids),
            ).group_by(CourseDayFeedbackRecord.course_day_id)).all()
        }
    return [SchoolCourseDayReportRead(
        course_day_id=day.id, session_id=day.session_id, formation_id=formation_id,
        formation_title=formation_title, session_label=session_label,
        teacher_id=day.teacher_id, teacher_name=teacher_name, title=day.title, scheduled_at=day.scheduled_at,
        delivery_status=day.delivery_status, summary=day.report_summary or "",
        difficulties=day.report_difficulties, homework=day.report_homework,
        attendance_notes=day.report_attendance_notes,
        submitted_at=day.report_submitted_at,
        feedback_count=feedback_summary.get(day.id, (0, None))[0],
        average_rating=feedback_summary.get(day.id, (0, None))[1],
    ) for day, session_label, formation_title, teacher_name, formation_id in rows]


def list_school_missing_course_day_reports(
    db: Session, tenant: TenantContext, *, now: datetime | None = None,
) -> list[SchoolMissingCourseDayReportRead]:
    """Course days over, in sessions still running or done, whose report the teacher still owes."""
    if not _can_manage_school(tenant):
        raise HTTPException(403, "Accès gestion requis.")
    current = now or datetime.now(UTC)
    current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
    rows = db.execute(select(
        SessionCourseDayRecord, FormationSessionRecord.label, FormationRecord.id, FormationRecord.title,
        UserRecord.full_name,
    ).join(
        FormationSessionRecord, FormationSessionRecord.id == SessionCourseDayRecord.session_id,
    ).join(
        FormationRecord, FormationRecord.id == FormationSessionRecord.formation_id,
    ).outerjoin(
        UserRecord, UserRecord.id == SessionCourseDayRecord.teacher_id,
    ).where(
        SessionCourseDayRecord.organization_id == tenant.organization_id,
        FormationSessionRecord.organization_id == tenant.organization_id,
        SessionCourseDayRecord.report_submitted_at.is_(None),
        SessionCourseDayRecord.status != "cancelled",
        FormationSessionRecord.status != "cancelled",
        SessionCourseDayRecord.scheduled_at <= current,
    ).order_by(SessionCourseDayRecord.scheduled_at.desc())).all()
    missing = []
    for day, session_label, formation_id, formation_title, teacher_name in rows:
        starts = day.scheduled_at.replace(tzinfo=UTC) if day.scheduled_at.tzinfo is None else day.scheduled_at
        ends = starts + timedelta(minutes=day.duration_minutes)
        if ends > current:
            continue
        missing.append(SchoolMissingCourseDayReportRead(
            course_day_id=day.id, session_id=day.session_id, formation_id=formation_id,
            formation_title=formation_title, session_label=session_label, teacher_id=day.teacher_id,
            teacher_name=teacher_name, title=day.title, scheduled_at=starts, ends_at=ends,
        ))
    return missing


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
    _require_live_class_length(db, session, payload.duration_minutes)
    _ensure_no_overlap(
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        existing_days=_active_course_days(db, tenant, session.id),
    )

    day = SessionCourseDayRecord(
        organization_id=tenant.organization_id,
        session_id=session.id,
        teacher_id=tenant.user.id,
        title=payload.title,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        status="planned",
    )
    db.add(day)
    db.flush()
    if session.formation.format_type == "live":
        notify_session_students(
            db, organization_id=tenant.organization_id, session_id=session.id,
            event_key=f"live.scheduled:{day.id}",
            title="Nouvelle classe en direct",
            message=f"{day.title} est planifiée le {school_time(tenant.organization, day.scheduled_at)}.",
            action_label="Voir le planning", action_path="/app/student/planning",
        )
        queue_session_students_event(
            db,
            org=tenant.organization,
            session_id=session.id,
            event_key="student.live.scheduled",
            context={
                "course_day_title": payload.title,
                # The school's own hour, as in the reminders (the e-mail cannot know the reader's).
                "scheduled_at": school_time(tenant.organization, payload.scheduled_at),
                "session_label": session.label,
            },
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
        _require_live_class_length(db, session, item.duration_minutes)
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
        day = SessionCourseDayRecord(
            organization_id=tenant.organization_id,
            session_id=session.id,
            teacher_id=tenant.user.id,
            title=item.title,
            scheduled_at=item.scheduled_at,
            duration_minutes=item.duration_minutes,
            status="planned",
        )
        db.add(day)
        db.flush()
        if session.formation.format_type == "live":
            notify_session_students(
                db, organization_id=tenant.organization_id, session_id=session.id,
                event_key=f"live.scheduled:{day.id}",
                title="Nouvelle classe en direct",
                message=f"{day.title} est planifiée le {school_time(tenant.organization, day.scheduled_at)}.",
                action_label="Voir le planning", action_path="/app/student/planning",
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
    if record.report_submitted_at is not None:
        raise HTTPException(status_code=409, detail="Le rapport a clôturé cette séance.")
    if record.started_at is not None:
        raise HTTPException(status_code=409, detail="Une séance démarrée ne peut plus être modifiée.")
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
        _require_live_class_length(db, session, next_duration)
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

    previous_at = record.scheduled_at
    previous_status = record.status
    for key, value in values.items():
        setattr(record, key, value)
    if session.formation.format_type == "live" and record.status == "cancelled" and previous_status != "cancelled":
        notify_session_students(
            db, organization_id=tenant.organization_id, session_id=session.id,
            event_key=f"live.cancelled:{record.id}", title="Classe en direct annulée",
            message=f"La séance {record.title} a été annulée.",
            action_label="Voir le planning", action_path="/app/student/planning",
        )
    elif session.formation.format_type == "live" and "scheduled_at" in values and previous_at != record.scheduled_at:
        notify_session_students(
            db, organization_id=tenant.organization_id, session_id=session.id,
            event_key=f"live.rescheduled:{record.id}:{_aware(record.scheduled_at).isoformat()}",
            title="Horaire de classe live modifié",
            message=f"{record.title} est maintenant prévue le {_aware(record.scheduled_at).strftime('%d/%m/%Y à %H:%M')}.",
            action_label="Voir le planning", action_path="/app/student/planning",
        )
    db.commit()
    return get_session_planning(db, tenant, session.id)


def submit_course_day_report(
    db: Session, tenant: TenantContext, course_day_id: int, payload: CourseDayReportSubmit,
    *, now: datetime | None = None,
) -> SessionPlanningRead:
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == course_day_id,
        SessionCourseDayRecord.organization_id == tenant.organization_id,
    ))
    if day is None:
        raise HTTPException(404, "Séance introuvable.")
    session = _session_or_404(db, tenant, day.session_id)
    _require_teacher_assignment(db, tenant, session)
    if tenant.support_mode or day.teacher_id != tenant.user.id:
        raise HTTPException(403, "Seul le professeur responsable peut clôturer cette séance.")
    if day.status == "cancelled" or session.status == "cancelled":
        raise HTTPException(409, "Une séance annulée ne peut pas être clôturée.")
    if day.report_submitted_at is not None:
        raise HTTPException(409, "Le rapport de cette séance est déjà remis.")
    current = _aware(now or datetime.now(UTC))
    # As on the mother site's end-live: a started live class can be closed at any time,
    # a course day that never started only once its scheduled end has passed.
    if day.started_at is None and current < _aware(day.scheduled_at) + timedelta(minutes=day.duration_minutes):
        raise HTTPException(409, "Le rapport d'une séance non démarrée s'ouvre à sa fin prévue.")
    if payload.delivery_status in {"held", "partial", "interrupted"}:
        student_by_enrollment = dict(db.execute(select(EnrollmentRecord.id, EnrollmentRecord.student_id).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )).all())
        marked_ids = set(db.scalars(select(AttendanceRecord.enrollment_id).where(
            AttendanceRecord.organization_id == tenant.organization_id,
            AttendanceRecord.course_day_id == day.id,
        )).all())
        # Live classes prefill from what shows the student followed: half of the course in the
        # room, an answer to the roll call when there was one, late after 15 minutes. Other
        # formats, and students with nothing recorded, are absent. The teacher can still correct
        # attendance for 24 h.
        live = session.formation.format_type == "live"
        evidence, roll_calls = live_attendance_evidence(db, tenant.organization_id, day.id) if live else ({}, 0)
        course_start, course_end = live_course_window(day, current)
        for enrollment_id in sorted(set(student_by_enrollment) - marked_ids):
            status = prefill_live_status(
                evidence.get(student_by_enrollment[enrollment_id]), roll_calls, course_start, course_end,
            ) if live else "absent"
            db.add(AttendanceRecord(
                organization_id=tenant.organization_id,
                course_day_id=day.id,
                enrollment_id=enrollment_id,
                status=status,
                marked_by_user_id=tenant.user.id,
                marked_at=current,
            ))
    if payload.delivery_status in {"held", "partial"} and day.started_at is None and session.formation.format_type == "live":
        day.started_at = _aware(day.scheduled_at)
    day.delivery_status = payload.delivery_status
    day.report_summary = payload.summary
    day.report_difficulties = payload.difficulties
    day.report_homework = payload.homework
    day.report_attendance_notes = payload.attendance_notes
    day.report_submitted_at = current
    if payload.delivery_status in {"held", "partial"}:
        db.flush()
        for row in db.scalars(select(AttendanceRecord).where(
            AttendanceRecord.organization_id == tenant.organization_id,
            AttendanceRecord.course_day_id == day.id,
            AttendanceRecord.status == "absent",
        )).all():
            notify_absence(db, org=tenant.organization, day=day, enrollment=db.get(EnrollmentRecord, row.enrollment_id))
        notify_attendance_risks(db, org=tenant.organization, session=session, day=day)
    db.commit()
    return get_session_planning(db, tenant, session.id)
