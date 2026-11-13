from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    LessonRecord,
    LessonVersionRecord,
    LessonProgressRecord,
    LessonVideoProgressRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    QuizRecord,
    QuizAttemptRecord,
    ResourceRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.academic import QUIZ_PASS_PCT
from app.schemas.formations import (
    ChapterCreate,
    CourseCreate,
    CourseUpdate,
    EnrollmentCreate,
    EnrollmentUpdate,
    FormationCreate,
    FormationDetailRead,
    FormationNextSessionRead,
    FormationSummaryRead,
    FormationUpdate,
    LessonCreate,
    SessionCreate,
    SessionRead,
    SessionUpdate,
    TeacherAssignmentCreate,
    TeacherAssignmentRead,
    EnrollmentRead,
    CourseRead,
    ChapterRead,
    LessonRead,
    LessonVersionRead,
)
from app.services.assets import delete_presentation_video, presentation_video_location
from app.services.assignments import release_assignment
from app.services.membership_roles import member_has_role
from app.services.online_formations import ensure_online_content_session
from app.services.onboarding import get_onboarding_status
from app.services.pdf_lessons import pdf_asset
from app.services.pedagogy_access import current_utc
from app.services.program_versions import FROZEN_MESSAGE, ensure_program_frozen, is_frozen_requirement, program_readiness
from app.services.session_lifecycle import notify_session_change
from app.services.publication import formation_content_issues, formation_publication_issues
from app.services.school_communications import queue_session_students_event
from app.services.school_notifications import notify_session_students, notify_user
from app.services.plan_limits import require_capacity, require_feature
from app.services.tenancy import TenantContext, scoped_select


class FormationConflictError(ValueError):
    pass


def _get_scoped(db: Session, tenant: TenantContext, model, object_id: int):
    return db.scalar(
        scoped_select(model, tenant).where(model.id == object_id)
    )


def _require_member(
    db: Session,
    tenant: TenantContext,
    *,
    user_id: int,
    role: str,
) -> UserRecord:
    member = db.scalar(
        select(OrganizationMemberRecord)
        .where(
            OrganizationMemberRecord.organization_id == tenant.organization_id,
            OrganizationMemberRecord.user_id == user_id,
            OrganizationMemberRecord.status == "active",
        )
    )
    if member is None or not member_has_role(db, member, role):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cet utilisateur n'est pas un "
                + ("professeur" if role == "teacher" else "étudiant")
                + " actif de cette école."
            ),
        )
    user = db.get(UserRecord, user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le compte utilisateur n'est pas actif.",
        )
    return user


def _teacher_can_manage_session(
    db: Session,
    tenant: TenantContext,
    session: FormationSessionRecord,
) -> bool:
    if tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        return True
    if not tenant.has_role("teacher"):
        return False
    return db.scalar(
        select(SessionTeacherRecord.id).where(
            SessionTeacherRecord.organization_id == tenant.organization_id,
            SessionTeacherRecord.session_id == session.id,
            SessionTeacherRecord.teacher_id == tenant.user.id,
        )
    ) is not None


def _serialize_course(course: CourseRecord) -> CourseRead:
    return CourseRead(
        id=course.id,
        title=course.title,
        description=course.description,
        teacher_id=course.teacher_id,
        teacher_name=course.teacher.full_name if course.teacher else None,
        status=course.status,
        chapters=[
            ChapterRead(
                id=chapter.id,
                title=chapter.title,
                order_index=chapter.order_index,
                lessons=[
                    LessonRead.model_validate(lesson)
                    for lesson in sorted(chapter.lessons, key=lambda item: (item.order_index, item.id))
                ],
            )
            for chapter in sorted(course.chapters, key=lambda item: (item.order_index, item.id))
        ],
        created_at=course.created_at,
    )


def _with_program_status(db: Session, formation: FormationRecord, session: FormationSessionRecord) -> SessionRead:
    read = _serialize_session(session)
    if formation.format_type not in {"live", "presentiel"}:
        return read
    version = ensure_program_frozen(db, session, formation)
    if version is not None:
        read.program_frozen_at = version.frozen_at
    elif session.status != "cancelled":
        read.program_missing = list(program_readiness(db, session, formation).missing)
    return read


def _serialize_session(session: FormationSessionRecord) -> SessionRead:
    return SessionRead(
        id=session.id,
        label=session.label,
        start_date=session.start_date,
        end_date=session.end_date,
        campus_label=session.campus_label,
        seat_capacity=session.seat_capacity,
        enrollment_open_at=session.enrollment_open_at,
        enrollment_close_at=session.enrollment_close_at,
        price_override_cents=session.price_override_cents,
        status=session.status,
        teachers=[
            TeacherAssignmentRead(
                id=item.id,
                teacher_id=item.teacher_id,
                teacher_name=item.teacher.full_name,
                teacher_email=item.teacher.email,
                role=item.role,
                assigned_at=item.assigned_at,
            )
            for item in sorted(session.teachers, key=lambda item: (item.role != "principal", item.id))
        ],
        enrollments=[
            EnrollmentRead(
                id=item.id,
                student_id=item.student_id,
                student_name=item.student.full_name,
                student_email=item.student.email,
                student_avatar_url=item.student.avatar_url,
                status=item.status,
                created_at=item.created_at,
            )
            for item in sorted(session.enrollments, key=lambda item: item.id)
        ],
        courses=[
            _serialize_course(item)
            for item in sorted(session.courses, key=lambda item: item.id)
        ],
        created_at=session.created_at,
    )


def _visible_session_ids(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
) -> set[int] | None:
    if (
        tenant.user.platform_role == "super_admin"
        or tenant.support_mode
        or tenant.organization_roles.intersection({"owner", "admin", "manager"})
    ):
        return None

    visible: set[int] = set()
    if tenant.has_role("teacher"):
        visible.update(
            db.scalars(
                select(FormationSessionRecord.id)
                .join(
                    SessionTeacherRecord,
                    SessionTeacherRecord.session_id == FormationSessionRecord.id,
                )
                .where(
                    FormationSessionRecord.organization_id == tenant.organization_id,
                    FormationSessionRecord.formation_id == formation_id,
                    SessionTeacherRecord.organization_id == tenant.organization_id,
                    SessionTeacherRecord.teacher_id == tenant.user.id,
                )
            ).all()
        )
    return visible


def _formation_counts(
    db: Session,
    organization_id: int,
    formation_id: int,
    visible_session_ids: set[int] | None = None,
) -> tuple[int, int, int, int]:
    session_ids_query = select(FormationSessionRecord.id).where(
        FormationSessionRecord.organization_id == organization_id,
        FormationSessionRecord.formation_id == formation_id,
    )
    if visible_session_ids is not None:
        session_ids_query = session_ids_query.where(
            FormationSessionRecord.id.in_(visible_session_ids)
        )
    session_ids = session_ids_query
    session_count_stmt = select(func.count(FormationSessionRecord.id)).where(
        FormationSessionRecord.organization_id == organization_id,
        FormationSessionRecord.formation_id == formation_id,
    )
    if visible_session_ids is not None:
        session_count_stmt = session_count_stmt.where(
            FormationSessionRecord.id.in_(visible_session_ids)
        )
    session_count = int(db.scalar(session_count_stmt) or 0)
    teacher_count = int(
        db.scalar(
            select(func.count(func.distinct(SessionTeacherRecord.teacher_id))).where(
                SessionTeacherRecord.organization_id == organization_id,
                SessionTeacherRecord.session_id.in_(session_ids),
            )
        )
        or 0
    )
    student_count = int(
        db.scalar(
            select(func.count(func.distinct(EnrollmentRecord.student_id))).where(
                EnrollmentRecord.organization_id == organization_id,
                EnrollmentRecord.session_id.in_(session_ids),
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        )
        or 0
    )
    course_count = int(
        db.scalar(
            select(func.count(CourseRecord.id)).where(
                CourseRecord.organization_id == organization_id,
                CourseRecord.session_id.in_(session_ids),
                CourseRecord.status != "archived",
            )
        )
        or 0
    )
    return session_count, teacher_count, student_count, course_count


def _next_session(
    db: Session,
    organization_id: int,
    formation: FormationRecord,
    visible_session_ids: set[int] | None,
) -> FormationNextSessionRead | None:
    """The session running now, else the first one to come; online formations have none."""
    if formation.format_type == "ligne":
        return None
    query = select(FormationSessionRecord).where(
        FormationSessionRecord.organization_id == organization_id,
        FormationSessionRecord.formation_id == formation.id,
        FormationSessionRecord.status.not_in(["cancelled", "completed"]),
        FormationSessionRecord.end_date >= date.today(),
    ).order_by(FormationSessionRecord.start_date, FormationSessionRecord.id).limit(1)
    if visible_session_ids is not None:
        query = query.where(FormationSessionRecord.id.in_(visible_session_ids))
    session = db.scalar(query)
    if session is None:
        return None
    enrolled = int(db.scalar(select(func.count(EnrollmentRecord.id)).where(
        EnrollmentRecord.organization_id == organization_id,
        EnrollmentRecord.session_id == session.id,
        EnrollmentRecord.status.in_(["active", "completed", "suspended_payment"]),
    )) or 0)
    return FormationNextSessionRead(
        id=session.id, label=session.label, start_date=session.start_date, end_date=session.end_date,
        enrolled_count=enrolled, seat_capacity=session.seat_capacity or 0,
    )


def _serialize_formation_summary(
    db: Session,
    tenant: TenantContext,
    formation: FormationRecord,
) -> FormationSummaryRead:
    visible_session_ids = _visible_session_ids(db, tenant, formation.id)
    session_count, teacher_count, student_count, course_count = _formation_counts(
        db,
        tenant.organization_id,
        formation.id,
        visible_session_ids,
    )
    if formation.format_type == "ligne":
        session_count = 0
    return FormationSummaryRead(
        next_session=_next_session(db, tenant.organization_id, formation, visible_session_ids),
        id=formation.id,
        organization_id=formation.organization_id,
        slug=formation.slug,
        title=formation.title,
        description=formation.description,
        category=formation.category,
        level=formation.level,
        format_type=formation.format_type,
        training_hours=formation.training_hours,
        short_description=formation.short_description,
        cover_image_url=formation.cover_image_url,
        presentation_video_url=formation.presentation_video_url,
        objectives=formation.objectives,
        prerequisites=formation.prerequisites,
        public_program=formation.public_program,
        price_cents=formation.price_cents,
        currency=formation.currency,
        allow_installments=formation.allow_installments,
        installment_count=formation.installment_count,
        reservation_deposit_enabled=formation.reservation_deposit_enabled,
        reservation_deposit_percent=formation.reservation_deposit_percent,
        is_featured=formation.is_featured,
        featured_order=formation.featured_order,
        status=formation.status,
        publication_issues=formation_publication_issues(db, formation),
        session_count=session_count,
        teacher_count=teacher_count,
        student_count=student_count,
        course_count=course_count,
        created_at=formation.created_at,
    )


def _require_no_running_session(db: Session, formation: FormationRecord) -> None:
    """As on the mother site, a formation cannot be archived while one of its sessions is running."""
    today = datetime.now(UTC).date()
    running = db.scalar(select(FormationSessionRecord).where(
        FormationSessionRecord.organization_id == formation.organization_id,
        FormationSessionRecord.formation_id == formation.id,
        FormationSessionRecord.status.not_in(["cancelled", "completed"]),
        FormationSessionRecord.start_date <= today,
        FormationSessionRecord.end_date >= today,
    ).order_by(FormationSessionRecord.start_date))
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail=f"La session « {running.label} » est en cours : terminez-la ou annulez-la avant d'archiver la formation.",
        )


def list_formations(
    db: Session,
    tenant: TenantContext,
) -> list[FormationSummaryRead]:
    records = list(
        db.scalars(
            scoped_select(FormationRecord, tenant)
            .where(FormationRecord.status != "archived")
            .order_by(FormationRecord.created_at.desc())
        ).all()
    )
    if (
        tenant.user.platform_role == "super_admin"
        or tenant.support_mode
        or tenant.organization_roles.intersection({"owner", "admin", "manager"})
    ):
        return [
            _serialize_formation_summary(db, tenant, record)
            for record in records
        ]

    visible_records = [
        record
        for record in records
        if _visible_session_ids(db, tenant, record.id)
    ]
    return [
        _serialize_formation_summary(db, tenant, record)
        for record in visible_records
    ]


def get_formation_record(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
) -> FormationRecord | None:
    return _get_scoped(db, tenant, FormationRecord, formation_id)


# Backward-compatible tenant-scoped accessor used by the isolation tests and
# by older service callers. Detailed API responses use get_formation_detail.
def get_formation(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
) -> FormationRecord | None:
    return get_formation_record(db, tenant, formation_id)


def get_formation_detail(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
) -> FormationDetailRead | None:
    formation = db.scalar(
        scoped_select(FormationRecord, tenant)
        .options(
            selectinload(FormationRecord.sessions)
            .selectinload(FormationSessionRecord.teachers)
            .selectinload(SessionTeacherRecord.teacher),
            selectinload(FormationRecord.sessions)
            .selectinload(FormationSessionRecord.enrollments)
            .selectinload(EnrollmentRecord.student),
            selectinload(FormationRecord.sessions)
            .selectinload(FormationSessionRecord.courses)
            .selectinload(CourseRecord.teacher),
            selectinload(FormationRecord.sessions)
            .selectinload(FormationSessionRecord.courses)
            .selectinload(CourseRecord.chapters)
            .selectinload(ChapterRecord.lessons),
        )
        .where(FormationRecord.id == formation_id)
        .execution_options(populate_existing=True)
    )
    if formation is None:
        return None

    visible_session_ids = _visible_session_ids(db, tenant, formation.id)
    if visible_session_ids is not None and not visible_session_ids:
        return None

    visible_sessions = (
        formation.sessions
        if visible_session_ids is None
        else [
            item
            for item in formation.sessions
            if item.id in visible_session_ids
        ]
    )
    summary = _serialize_formation_summary(db, tenant, formation)
    return FormationDetailRead(
        **summary.model_dump(),
        sessions=[
            _with_program_status(db, formation, item)
            for item in sorted(
                visible_sessions,
                key=lambda item: (item.start_date, item.id),
                reverse=True,
            )
        ],
    )


def create_formation(
    db: Session,
    tenant: TenantContext,
    payload: FormationCreate,
    *,
    accept_addon: bool = False,
) -> FormationSummaryRead:
    setup = get_onboarding_status(db, tenant)
    missing = next((step for step in setup.steps if step.key != "formation" and not step.completed), None)
    if missing:
        raise HTTPException(status_code=409, detail=f"Terminez d'abord l'étape « {missing.label} » avant de créer une formation.")

    formation = FormationRecord(
        organization_id=tenant.organization_id,
        slug=payload.slug.strip().lower(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category.strip(),
        level=payload.level.strip(),
        format_type=payload.format_type,
        training_hours=payload.training_hours,
        short_description=payload.short_description.strip(),
        cover_image_url=payload.cover_image_url,
        presentation_video_url=_checked_presentation_video(payload.presentation_video_url, tenant.organization_id),
        objectives=payload.objectives.strip(),
        prerequisites=payload.prerequisites.strip(),
        public_program=payload.public_program.strip(),
        price_cents=payload.price_cents,
        currency=payload.currency.upper(),
        allow_installments=payload.allow_installments,
        installment_count=payload.installment_count,
        reservation_deposit_enabled=payload.reservation_deposit_enabled,
        reservation_deposit_percent=payload.reservation_deposit_percent,
        is_featured=payload.is_featured,
        featured_order=payload.featured_order,
        status=payload.status,
    )
    db.add(formation)
    try:
        db.flush()
        ensure_online_content_session(db, formation)
        if formation.status == "published":
            issues = formation_publication_issues(db, formation)
            if issues:
                raise HTTPException(status_code=422, detail="Publication impossible : " + " ".join(issues))
            _require_plan_room(db, tenant, formation, newly_published=True, accept_addon=accept_addon)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise FormationConflictError(
            "Une formation avec ce slug existe déjà dans cette école."
        ) from exc
    db.refresh(formation)
    return _serialize_formation_summary(db, tenant, formation)


def update_formation(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    payload: FormationUpdate,
    *,
    accept_addon: bool = False,
) -> FormationSummaryRead:
    formation = get_formation_record(db, tenant, formation_id)
    if formation is None:
        raise HTTPException(status_code=404, detail="Formation introuvable.")

    if payload.status == "archived" and formation.status != "archived":
        _require_no_running_session(db, formation)
    previously_published = formation.status == "published"
    previously_live = formation.format_type == "live"
    previously_complete = not formation_content_issues(formation)
    previous_video = formation.presentation_video_url
    changes = payload.model_dump(exclude_unset=True)
    if "presentation_video_url" in changes and (changes["presentation_video_url"] or None) != previous_video:
        changes["presentation_video_url"] = _checked_presentation_video(changes["presentation_video_url"], tenant.organization_id)
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        if key == "currency" and value:
            value = value.upper()
        setattr(formation, key, value)
    ensure_online_content_session(db, formation)
    if formation.status == "published":
        issues = (formation_publication_issues(db, formation)
                  if not previously_published else formation_content_issues(formation))
        if issues and (not previously_published or previously_complete):
            db.rollback()
            raise HTTPException(status_code=422, detail="Publication impossible : " + " ".join(issues))
        if not previously_published or (formation.format_type == "live" and not previously_live):
            try:
                _require_plan_room(db, tenant, formation, newly_published=not previously_published, accept_addon=accept_addon)
            except HTTPException:
                db.rollback()
                raise
    db.commit()
    db.refresh(formation)
    _forget_presentation_video(db, tenant.organization_id, previous_video, formation.presentation_video_url)
    return _serialize_formation_summary(db, tenant, formation)


def _checked_presentation_video(url: str | None, organization_id: int) -> str | None:
    """Only a video imported from the formation's page, stored for this school (no outside address)."""
    url = (url or "").strip() or None
    if url is not None and presentation_video_location(url, organization_id) is None:
        raise HTTPException(status_code=422, detail="Importez la vidéo de présentation depuis la fiche de la formation.")
    return url


def _forget_presentation_video(db: Session, organization_id: int, previous: str | None, current: str | None) -> None:
    """A replaced or removed presentation video is deleted, unless another formation still shows it."""
    location = presentation_video_location(previous, organization_id) if previous != current else None
    if location is None:
        return
    still_used = db.scalar(select(FormationRecord.id).where(
        FormationRecord.organization_id == organization_id,
        FormationRecord.presentation_video_url == previous,
    ).limit(1))
    if still_used is None:
        delete_presentation_video(location)


def _require_plan_room(
    db: Session,
    tenant: TenantContext,
    formation: FormationRecord,
    *,
    newly_published: bool,
    accept_addon: bool,
) -> None:
    """A published formation counts in the plan's quota; live classes come with some plans only."""
    if formation.format_type == "live":
        require_feature(db, tenant.organization_id, "live")
    if newly_published:
        # The formation is already flushed as published: the quota counts it, so check room for zero more.
        require_capacity(db, tenant.organization_id, "active_formations", adding=0, accept_addon=accept_addon)


def _guided_session_place(
    formation: FormationRecord,
    *,
    campus_label: str | None,
    seat_capacity: int,
) -> str | None:
    """Apply the mother site's live and onsite rules and return the place to store."""
    place = (campus_label or "").strip() or None
    if formation.format_type == "ligne":
        return place
    if seat_capacity < 1:
        raise HTTPException(status_code=422, detail="Une session doit proposer au moins une place.")
    if formation.format_type == "live":
        return None
    if place is None:
        raise HTTPException(status_code=422, detail="Le lieu est obligatoire pour une formation en présentiel.")
    return place


def _occupied_seats(db: Session, organization_id: int, session_id: int) -> int:
    enrolled = db.scalar(select(func.count(EnrollmentRecord.id)).where(
        EnrollmentRecord.organization_id == organization_id,
        EnrollmentRecord.session_id == session_id,
        EnrollmentRecord.status.in_(["active", "completed", "suspended_payment"]),
    )) or 0
    reservation_cutoff = datetime.now(UTC) - timedelta(minutes=settings.commerce_reservation_minutes)
    reserved = db.scalar(select(func.count(StudentOrderRecord.id)).where(
        StudentOrderRecord.organization_id == organization_id,
        StudentOrderRecord.session_id == session_id,
        StudentOrderRecord.status == "pending",
        StudentOrderRecord.created_at > reservation_cutoff,
    )) or 0
    return int(enrolled) + int(reserved)


def _require_course_days_within(
    db: Session,
    session: FormationSessionRecord,
    start_date: date,
    end_date: date,
) -> None:
    scheduled_days = db.scalars(select(SessionCourseDayRecord.scheduled_at).where(
        SessionCourseDayRecord.organization_id == session.organization_id,
        SessionCourseDayRecord.session_id == session.id,
        SessionCourseDayRecord.status != "cancelled",
    )).all()
    if any(not start_date <= current_utc(item).date() <= end_date for item in scheduled_days):
        raise HTTPException(
            status_code=409,
            detail="Une séance déjà planifiée se trouve hors des nouvelles dates de la session.",
        )


def create_session(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    payload: SessionCreate,
) -> FormationDetailRead:
    formation = get_formation_record(db, tenant, formation_id)
    if formation is None:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    campus_label = _guided_session_place(
        formation,
        campus_label=payload.campus_label,
        seat_capacity=payload.seat_capacity,
    )
    record = FormationSessionRecord(
        organization_id=tenant.organization_id,
        formation_id=formation.id,
        label=payload.label.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        campus_label=campus_label,
        seat_capacity=payload.seat_capacity,
        enrollment_open_at=payload.enrollment_open_at,
        enrollment_close_at=payload.enrollment_close_at,
        price_override_cents=payload.price_override_cents,
        status=payload.status,
    )
    db.add(record)
    db.flush()
    if record.status == "open":
        issues = formation_publication_issues(db, formation)
        if formation.status != "published" or issues or record.end_date < datetime.now(UTC).date():
            db.rollback()
            raise HTTPException(status_code=422, detail="Ouverture impossible : publiez d'abord une formation complète. " + " ".join(issues))
        if record.price_override_cents == 0:
            db.rollback()
            raise HTTPException(status_code=422, detail="Le prix de la session doit être supérieur à zéro.")
    if payload.copy_content_from_session_id:
        from app.services.session_content_copy import copy_session_content, copy_source_for

        source = copy_source_for(db, tenant, formation.id, payload.copy_content_from_session_id)
        copy_session_content(db, tenant, source, record, with_teachers=payload.copy_teachers)
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def update_session(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    payload: SessionUpdate,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    if session is None or session.formation_id != formation_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    formation = get_formation_record(db, tenant, formation_id)

    values = payload.model_dump(exclude_unset=True)
    before_change = (session.label, session.start_date, session.end_date, session.campus_label, session.status == "cancelled")
    next_start = values.get("start_date", session.start_date)
    next_end = values.get("end_date", session.end_date)
    if next_end < next_start:
        raise HTTPException(
            status_code=422,
            detail="La date de fin doit être postérieure ou égale à la date de début.",
        )
    next_open = values.get("enrollment_open_at", session.enrollment_open_at)
    next_close = values.get("enrollment_close_at", session.enrollment_close_at)
    if next_open and next_close and next_close.replace(tzinfo=next_close.tzinfo or UTC) < next_open.replace(tzinfo=next_open.tzinfo or UTC):
        raise HTTPException(status_code=422, detail="La clôture des inscriptions doit suivre leur ouverture.")
    if (next_start, next_end) != (session.start_date, session.end_date):
        _require_course_days_within(db, session, next_start, next_end)
    next_capacity = values.get("seat_capacity", session.seat_capacity)
    if (
        next_capacity != session.seat_capacity
        and 0 < next_capacity < _occupied_seats(db, tenant.organization_id, session.id)
    ):
        raise HTTPException(
            status_code=409,
            detail="La capacité ne peut pas être inférieure aux places déjà occupées ou réservées.",
        )
    # Older sessions may miss a place: they stay closable, and must be fixed to reopen.
    if {"campus_label", "seat_capacity"} & values.keys() or values.get("status", session.status) == "open":
        values["campus_label"] = _guided_session_place(
            formation,
            campus_label=values.get("campus_label", session.campus_label),
            seat_capacity=next_capacity,
        )
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(session, key, value)
    if session.status == "open":
        issues = formation_publication_issues(db, formation)
        if formation.status != "published" or issues or session.end_date < datetime.now(UTC).date():
            db.rollback()
            raise HTTPException(status_code=422, detail="Ouverture impossible : formation ou session incomplète. " + " ".join(issues))
        if session.price_override_cents == 0:
            db.rollback()
            raise HTTPException(status_code=422, detail="Le prix de la session doit être supérieur à zéro.")
    after_change = (session.label, session.start_date, session.end_date, session.campus_label, session.status == "cancelled")
    if after_change != before_change:
        # Opening or closing the sale is not a change for the enrolled students; dates, place, name and cancellation are.
        notify_session_change(
            db, org=tenant.organization, session=session, formation=formation,
            change_key=datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"),
        )
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def assign_teacher(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    payload: TeacherAssignmentCreate,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    if session is None or session.formation_id != formation_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    _require_member(db, tenant, user_id=payload.user_id, role="teacher")

    existing = db.scalar(
        select(SessionTeacherRecord).where(
            SessionTeacherRecord.organization_id == tenant.organization_id,
            SessionTeacherRecord.session_id == session.id,
            SessionTeacherRecord.teacher_id == payload.user_id,
        )
    )
    if existing is None:
        existing = SessionTeacherRecord(
            organization_id=tenant.organization_id,
            session_id=session.id,
            teacher_id=payload.user_id,
            role=payload.role,
        )
    else:
        existing.role = payload.role
    if payload.role == "principal":
        principals = list(
            db.scalars(
                select(SessionTeacherRecord).where(
                    SessionTeacherRecord.organization_id == tenant.organization_id,
                    SessionTeacherRecord.session_id == session.id,
                    SessionTeacherRecord.role == "principal",
                    SessionTeacherRecord.teacher_id != payload.user_id,
                )
            ).all()
        )
        for item in principals:
            item.role = "intervenant"
            db.add(item)
    db.add(existing)
    db.flush()
    notify_user(
        db, organization_id=tenant.organization_id, user_id=payload.user_id,
        event_key=f"teacher.assigned:{session.id}",
        audience="teacher",
        title="Formation attribuée",
        message=f"Vous intervenez dans {get_formation_record(db, tenant, formation_id).title} ({session.label}).",
        category="session", action_label="Voir la session",
        action_path=f"/app/teacher/sessions/{session.id}",
    )
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def remove_teacher(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    teacher_id: int,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    if session is None or session.formation_id != formation_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    assignment = db.scalar(
        select(SessionTeacherRecord).where(
            SessionTeacherRecord.organization_id == tenant.organization_id,
            SessionTeacherRecord.session_id == session.id,
            SessionTeacherRecord.teacher_id == teacher_id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Affectation professeur introuvable.")
    remaining_teacher = db.scalar(select(SessionTeacherRecord.id).where(
        SessionTeacherRecord.organization_id == tenant.organization_id,
        SessionTeacherRecord.session_id == session.id,
        SessionTeacherRecord.teacher_id != teacher_id,
    ))
    active_enrollment = db.scalar(select(EnrollmentRecord.id).where(
        EnrollmentRecord.organization_id == tenant.organization_id,
        EnrollmentRecord.session_id == session.id,
        EnrollmentRecord.status.in_(["active", "completed"]),
    ))
    if remaining_teacher is None and active_enrollment is not None:
        raise HTTPException(409, "Affectez un autre professeur avant de retirer le dernier enseignant de cette session.")
    if active_enrollment is not None and (
        db.scalar(select(SessionCourseDayRecord.id).where(
            SessionCourseDayRecord.organization_id == tenant.organization_id,
            SessionCourseDayRecord.session_id == session.id,
            SessionCourseDayRecord.teacher_id == teacher_id,
        )) is not None
        or db.scalar(select(CourseRecord.id).where(
            CourseRecord.organization_id == tenant.organization_id,
            CourseRecord.session_id == session.id,
            CourseRecord.teacher_id == teacher_id,
        )) is not None
    ):
        raise HTTPException(409, "Réattribuez les cours et séances de ce professeur avant son retrait.")
    db.delete(assignment)
    notify_user(
        db, organization_id=tenant.organization_id, user_id=teacher_id,
        event_key=f"teacher.removed:{session.id}:{assignment.id}",
        audience="teacher", title="Affectation retirée",
        message=f"Vous n'intervenez plus dans {get_formation_record(db, tenant, formation_id).title} ({session.label}).",
        category="session", tone="warning", action_label="Mes sessions",
        action_path="/app/teacher/sessions",
    )
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def enroll_student(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    payload: EnrollmentCreate,
) -> FormationDetailRead:
    db.scalar(select(OrganizationRecord).where(OrganizationRecord.id == tenant.organization_id).with_for_update())
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    if session is None or session.formation_id != formation_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    _require_member(db, tenant, user_id=payload.user_id, role="student")

    active_count = int(
        db.scalar(
            select(func.count(EnrollmentRecord.id)).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.session_id == session.id,
                EnrollmentRecord.status.in_(["active", "completed", "suspended_payment"]),
            )
        )
        or 0
    )
    pending_count = int(db.scalar(select(func.count(StudentOrderRecord.id)).where(
        StudentOrderRecord.organization_id == tenant.organization_id,
        StudentOrderRecord.session_id == session.id,
        StudentOrderRecord.status == "pending",
    )) or 0)
    if session.seat_capacity > 0 and active_count + pending_count >= session.seat_capacity:
        raise HTTPException(status_code=409, detail="La capacité de cette session est atteinte.")

    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.student_id == payload.user_id,
        )
    )
    if enrollment is None:
        enrollment = EnrollmentRecord(
            organization_id=tenant.organization_id,
            session_id=session.id,
            student_id=payload.user_id,
            status="active",
        )
    else:
        enrollment.status = "active"
    db.add(enrollment)
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def update_enrollment(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    enrollment_id: int,
    payload: EnrollmentUpdate,
) -> FormationDetailRead:
    db.scalar(select(OrganizationRecord).where(OrganizationRecord.id == tenant.organization_id).with_for_update())
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    enrollment = _get_scoped(db, tenant, EnrollmentRecord, enrollment_id)
    if (
        session is None
        or session.formation_id != formation_id
        or enrollment is None
        or enrollment.session_id != session_id
    ):
        raise HTTPException(status_code=404, detail="Inscription introuvable.")
    if enrollment.status not in {"active", "completed", "suspended_payment"} and payload.status in {"active", "completed", "suspended_payment"} and session.seat_capacity > 0:
        active_count = int(db.scalar(select(func.count(EnrollmentRecord.id)).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.status.in_(["active", "completed", "suspended_payment"]),
        )) or 0)
        pending_count = int(db.scalar(select(func.count(StudentOrderRecord.id)).where(
            StudentOrderRecord.organization_id == tenant.organization_id,
            StudentOrderRecord.session_id == session.id,
            StudentOrderRecord.status == "pending",
        )) or 0)
        if active_count + pending_count >= session.seat_capacity:
            raise HTTPException(status_code=409, detail="La capacité de cette session est atteinte.")
    enrollment.status = payload.status
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def create_course(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    payload: CourseCreate,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    if session is None or session.formation_id != formation_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    if not _teacher_can_manage_session(db, tenant, session):
        raise HTTPException(status_code=403, detail="Vous n'êtes pas affecté à cette session.")

    teacher_id = payload.teacher_id
    if tenant.has_role("teacher") and not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        teacher_id = tenant.user.id
    elif teacher_id is not None:
        _require_member(db, tenant, user_id=teacher_id, role="teacher")

    course = CourseRecord(
        organization_id=tenant.organization_id,
        session_id=session.id,
        teacher_id=teacher_id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        status=payload.status,
    )
    db.add(course)
    db.flush()
    if course.status == "published":
        queue_session_students_event(
            db,
            org=tenant.organization,
            session_id=session.id,
            event_key="student.course.published",
            context={
                "course_title": course.title,
                "session_label": session.label,
            },
        )
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def update_course(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    course_id: int,
    payload: CourseUpdate,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    course = _get_scoped(db, tenant, CourseRecord, course_id)
    if (
        session is None
        or session.formation_id != formation_id
        or course is None
        or course.session_id != session.id
    ):
        raise HTTPException(status_code=404, detail="Cours introuvable.")
    if not _teacher_can_manage_session(db, tenant, session):
        raise HTTPException(status_code=403, detail="Vous n'êtes pas affecté à cette session.")

    values = payload.model_dump(exclude_unset=True)
    if tenant.has_role("teacher") and not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        values.pop("teacher_id", None)
        if course.teacher_id not in {None, tenant.user.id}:
            raise HTTPException(status_code=403, detail="Ce cours appartient à un autre professeur.")
        course.teacher_id = tenant.user.id
    elif "teacher_id" in values and values["teacher_id"] is not None:
        _require_member(db, tenant, user_id=values["teacher_id"], role="teacher")

    previous_status = course.status
    if previous_status == "published" and values.get("status") not in (None, "published"):
        course_lesson_ids = db.scalars(select(LessonRecord.id).join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id).where(ChapterRecord.course_id == course.id)).all()
        if any(is_frozen_requirement(db, course.session_id, "lesson_ids", lesson_id) for lesson_id in course_lesson_ids):
            raise HTTPException(409, FROZEN_MESSAGE)
    if values.get("status") == "published" and previous_status != "published":
        lessons = list(db.scalars(
            select(LessonRecord)
            .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
            .where(ChapterRecord.course_id == course.id)
        ).all())
        if not lessons:
            raise HTTPException(422, "Ajoutez au moins une leçon avant de publier ce cours.")
        for lesson in lessons:
            _validate_lesson_publication(db, tenant, lesson, session.id)
        for lesson in lessons:
            _release_linked_assignment(db, tenant, lesson)
            if lesson.publication_status != "published":
                _ensure_lesson_baseline(db, lesson)
                lesson.publication_status = "published"
                _record_lesson_version(db, tenant, lesson, "published")
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(course, key, value)
    if course.status == "published" and previous_status != "published":
        queue_session_students_event(
            db,
            org=tenant.organization,
            session_id=session.id,
            event_key="student.course.published",
            context={
                "course_title": course.title,
                "session_label": session.label,
            },
        )
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def create_chapter(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    course_id: int,
    payload: ChapterCreate,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    course = _get_scoped(db, tenant, CourseRecord, course_id)
    if (
        session is None
        or session.formation_id != formation_id
        or course is None
        or course.session_id != session.id
    ):
        raise HTTPException(status_code=404, detail="Cours introuvable.")
    if not _teacher_can_manage_session(db, tenant, session):
        raise HTTPException(status_code=403, detail="Vous n'êtes pas affecté à cette session.")
    if tenant.has_role("teacher") and not tenant.organization_roles.intersection({"owner", "admin", "manager"}) and course.teacher_id not in {None, tenant.user.id}:
        raise HTTPException(status_code=403, detail="Ce cours appartient à un autre professeur.")

    chapter = ChapterRecord(
        organization_id=tenant.organization_id,
        course_id=course.id,
        title=payload.title.strip(),
        order_index=payload.order_index,
    )
    db.add(chapter)
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def create_lesson(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    session_id: int,
    course_id: int,
    chapter_id: int,
    payload: LessonCreate,
) -> FormationDetailRead:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    course = _get_scoped(db, tenant, CourseRecord, course_id)
    chapter = _get_scoped(db, tenant, ChapterRecord, chapter_id)
    if (
        session is None
        or session.formation_id != formation_id
        or course is None
        or course.session_id != session.id
        or chapter is None
        or chapter.course_id != course.id
    ):
        raise HTTPException(status_code=404, detail="Module introuvable.")
    if not _teacher_can_manage_session(db, tenant, session):
        raise HTTPException(status_code=403, detail="Vous n'êtes pas affecté à cette session.")
    if tenant.has_role("teacher") and not tenant.organization_roles.intersection({"owner", "admin", "manager"}) and course.teacher_id not in {None, tenant.user.id}:
        raise HTTPException(status_code=403, detail="Ce cours appartient à un autre professeur.")

    _validate_lesson_links(db, tenant, session.id, payload)
    lesson = LessonRecord(
        organization_id=tenant.organization_id,
        chapter_id=chapter.id,
        title=payload.title.strip(),
        order_index=payload.order_index,
        lesson_type=payload.lesson_type,
        publication_status="draft",
        content=payload.content.strip() if payload.content else None,
        video_url=payload.video_url.strip() if payload.video_url else None,
        file_url=payload.file_url.strip() if payload.file_url else None,
        quiz_id=payload.quiz_id,
        assignment_id=payload.assignment_id,
        resource_id=payload.resource_id,
        available_at=payload.available_at,
    )
    db.add(lesson)
    db.flush()
    _record_lesson_version(db, tenant, lesson, "created")
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def _validate_lesson_links(
    db: Session, tenant: TenantContext, session_id: int, payload: LessonCreate, *, lesson_id: int | None = None,
) -> None:
    linked = (("quiz", QuizRecord, payload.quiz_id), ("assignment", AssignmentRecord, payload.assignment_id), ("resource", ResourceRecord, payload.resource_id))
    for label, model, linked_id in linked:
        if linked_id is None:
            continue
        activity = _get_scoped(db, tenant, model, linked_id)
        if activity is None or activity.session_id != session_id:
            raise HTTPException(422, f"{label.capitalize()} lié introuvable dans cette session.")
        # As on the mother site, a video lesson can carry one complementary quiz, assignment or resource.
        if label == "quiz" and payload.lesson_type not in {"quiz", "pdf", "text", "video"}:
            raise HTTPException(422, "Ce type de leçon ne peut pas valider un quiz.")
        if label == "assignment" and payload.lesson_type not in {"assignment", "video"}:
            raise HTTPException(422, "Le devoir doit être lié à une leçon de type devoir.")
        if label == "resource" and payload.lesson_type not in {"resource", "video"}:
            raise HTTPException(422, "La ressource doit être liée à une leçon de type ressource.")
        linked_query = select(LessonRecord.id).where(LessonRecord.organization_id == tenant.organization_id, getattr(LessonRecord, f"{label}_id") == linked_id)
        if lesson_id is not None:
            linked_query = linked_query.where(LessonRecord.id != lesson_id)
        if db.scalar(linked_query) is not None:
            raise HTTPException(409, "Cette activité est déjà liée à une leçon.")
        if label == "quiz" and (lesson_id is None or db.get(LessonRecord, lesson_id).quiz_id != linked_id) and db.scalar(select(QuizAttemptRecord.id).where(QuizAttemptRecord.organization_id == tenant.organization_id, QuizAttemptRecord.quiz_id == linked_id)) is not None:
            raise HTTPException(409, "Ce quiz a déjà été passé. Créez un nouveau quiz pour cette leçon.")
        if label == "assignment" and (lesson_id is None or db.get(LessonRecord, lesson_id).assignment_id != linked_id) and db.scalar(select(AssignmentSubmissionRecord.id).where(AssignmentSubmissionRecord.organization_id == tenant.organization_id, AssignmentSubmissionRecord.assignment_id == linked_id)) is not None:
            raise HTTPException(409, "Ce devoir a déjà été remis. Créez un nouveau devoir pour cette leçon.")
    if payload.lesson_type == "video" and sum(item is not None for item in (payload.quiz_id, payload.assignment_id, payload.resource_id)) > 1:
        raise HTTPException(422, "Une leçon vidéo ne porte qu'une activité complémentaire.")
    if payload.lesson_type == "quiz" and payload.quiz_id is None:
        raise HTTPException(422, "Choisissez un quiz pour cette leçon.")
    if payload.lesson_type == "assignment" and payload.assignment_id is None:
        raise HTTPException(422, "Choisissez un devoir pour cette leçon.")
    if payload.lesson_type == "pdf" and payload.quiz_id is not None:
        asset = pdf_asset(db, tenant.organization_id, payload.file_url)
        if asset is None:
            raise HTTPException(422, "Importez le PDF dans le stockage privé de cette école avant de lier son quiz.")
        quiz = _get_scoped(db, tenant, QuizRecord, payload.quiz_id)
        if quiz is None or len(quiz.questions) != 20:
            raise HTTPException(422, "Le quiz de validation PDF doit contenir exactement 20 questions.")
        quiz.pass_pct = QUIZ_PASS_PCT
        quiz.status = "active"


def _validate_lesson_publication(db: Session, tenant: TenantContext, lesson: LessonRecord, session_id: int) -> None:
    if lesson.lesson_type == "text" and not (lesson.content or "").strip():
        raise HTTPException(422, "Rédigez le contenu de cette leçon avant publication.")
    if lesson.lesson_type == "video" and not (lesson.video_url or "").strip():
        raise HTTPException(422, "Ajoutez la vidéo avant publication.")
    if lesson.lesson_type == "pdf":
        if not (lesson.file_url or "").strip():
            raise HTTPException(422, "Ajoutez le PDF avant publication.")
        if lesson.quiz_id is not None and pdf_asset(db, tenant.organization_id, lesson.file_url) is None:
            raise HTTPException(422, "Réimportez ce PDF dans le stockage privé de l'école.")
    for kind, model, linked_id in (("quiz", QuizRecord, lesson.quiz_id), ("assignment", AssignmentRecord, lesson.assignment_id), ("resource", ResourceRecord, lesson.resource_id)):
        if lesson.lesson_type == kind and linked_id is None:
            raise HTTPException(422, f"Associez un {kind} avant publication.")
        if linked_id is not None:
            activity = _get_scoped(db, tenant, model, linked_id)
            if activity is None or activity.session_id != session_id or (kind == "quiz" and activity.status not in {"active", "closed"}):
                raise HTTPException(422, f"Le {kind} lié doit appartenir à cette session et être disponible.")


def _release_linked_assignment(db: Session, tenant: TenantContext, lesson: LessonRecord) -> None:
    if lesson.assignment_id is not None:
        release_assignment(db, tenant.organization, _get_scoped(db, tenant, AssignmentRecord, lesson.assignment_id))


def _lesson_for_edit(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int) -> tuple[CourseRecord, LessonRecord]:
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    course = _get_scoped(db, tenant, CourseRecord, course_id)
    chapter = _get_scoped(db, tenant, ChapterRecord, chapter_id)
    lesson = _get_scoped(db, tenant, LessonRecord, lesson_id)
    if session is None or session.formation_id != formation_id or course is None or course.session_id != session_id or chapter is None or chapter.course_id != course_id or lesson is None or lesson.chapter_id != chapter_id:
        raise HTTPException(404, "Leçon introuvable.")
    if not _teacher_can_manage_session(db, tenant, session) or (tenant.has_role("teacher") and not tenant.organization_roles.intersection({"owner", "admin", "manager"}) and course.teacher_id not in {None, tenant.user.id}):
        raise HTTPException(403, "Vous ne pouvez pas modifier cette leçon.")
    return course, lesson


def _lesson_snapshot(lesson: LessonRecord) -> dict:
    return {
        "title": lesson.title,
        "order_index": lesson.order_index,
        "lesson_type": lesson.lesson_type,
        "publication_status": lesson.publication_status,
        "content": lesson.content,
        "video_url": lesson.video_url,
        "file_url": lesson.file_url,
        "quiz_id": lesson.quiz_id,
        "assignment_id": lesson.assignment_id,
        "resource_id": lesson.resource_id,
        "available_at": lesson.available_at.isoformat() if lesson.available_at else None,
    }


def _ensure_lesson_baseline(db: Session, lesson: LessonRecord) -> None:
    existing = db.scalar(select(LessonVersionRecord.id).where(
        LessonVersionRecord.organization_id == lesson.organization_id,
        LessonVersionRecord.lesson_id == lesson.id,
        LessonVersionRecord.version_number == lesson.version_number,
    ))
    if existing is None:
        db.add(LessonVersionRecord(
            organization_id=lesson.organization_id,
            lesson_id=lesson.id,
            version_number=lesson.version_number,
            snapshot=_lesson_snapshot(lesson),
            reason="initial",
        ))


def _record_lesson_version(db: Session, tenant: TenantContext, lesson: LessonRecord, reason: str) -> None:
    if reason != "created":
        lesson.version_number += 1
    db.add(LessonVersionRecord(
        organization_id=tenant.organization_id,
        lesson_id=lesson.id,
        version_number=lesson.version_number,
        snapshot=_lesson_snapshot(lesson),
        reason=reason,
        edited_by_user_id=tenant.user.id,
    ))


def list_lesson_versions(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int) -> list[LessonVersionRead]:
    _, lesson = _lesson_for_edit(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
    versions = db.scalars(select(LessonVersionRecord).where(
        LessonVersionRecord.organization_id == tenant.organization_id,
        LessonVersionRecord.lesson_id == lesson.id,
    ).order_by(LessonVersionRecord.version_number.desc())).all()
    return [LessonVersionRead.model_validate(version, from_attributes=True) for version in versions]


def update_lesson(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int, payload: LessonCreate, *, reason: str = "edited") -> FormationDetailRead:
    _, lesson = _lesson_for_edit(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
    _ensure_lesson_baseline(db, lesson)
    old_snapshot = _lesson_snapshot(lesson)
    old_identity = (lesson.lesson_type, lesson.video_url, lesson.file_url, lesson.quiz_id, lesson.assignment_id, lesson.resource_id)
    if lesson.lesson_type == "pdf" and lesson.file_url != payload.file_url and lesson.quiz_id == payload.quiz_id and payload.quiz_id is not None and db.scalar(select(QuizAttemptRecord.id).where(QuizAttemptRecord.organization_id == tenant.organization_id, QuizAttemptRecord.quiz_id == payload.quiz_id)) is not None:
        raise HTTPException(409, "Créez un nouveau quiz pour remplacer un PDF déjà évalué.")
    _validate_lesson_links(db, tenant, session_id, payload, lesson_id=lesson.id)
    if is_frozen_requirement(db, session_id, "lesson_ids", lesson.id):
        def _structure(values):
            return tuple((value.strip() or None) if isinstance(value, str) else (current_utc(value) if isinstance(value, datetime) else value) for value in values)
        before = _structure((lesson.lesson_type, lesson.video_url, lesson.file_url, lesson.quiz_id, lesson.assignment_id, lesson.resource_id, lesson.order_index, lesson.available_at))
        after = _structure((payload.lesson_type, payload.video_url, payload.file_url, payload.quiz_id, payload.assignment_id, payload.resource_id, payload.order_index, payload.available_at))
        if before != after:
            raise HTTPException(409, FROZEN_MESSAGE + " Pour une leçon figée : le titre et le texte.")
    for field in ("title", "order_index", "lesson_type", "content", "video_url", "file_url", "quiz_id", "assignment_id", "resource_id", "available_at"):
        value = getattr(payload, field)
        setattr(lesson, field, value.strip() if isinstance(value, str) else value)
    if lesson.publication_status == "published":
        try:
            _validate_lesson_publication(db, tenant, lesson, session_id)
        except HTTPException:
            db.rollback()
            raise
        _release_linked_assignment(db, tenant, lesson)
    new_identity = (lesson.lesson_type, lesson.video_url, lesson.file_url, lesson.quiz_id, lesson.assignment_id, lesson.resource_id)
    # A video lesson is earned by watching it: switching its complementary activity keeps the progress.
    complementary_only = old_identity[0] == "video" and lesson.lesson_type == "video" and old_identity[:3] == new_identity[:3]
    if old_identity != new_identity and not complementary_only:
        db.execute(delete(LessonProgressRecord).where(LessonProgressRecord.organization_id == tenant.organization_id, LessonProgressRecord.lesson_id == lesson.id))
    if old_identity[:2] != (lesson.lesson_type, lesson.video_url):
        db.execute(delete(LessonVideoProgressRecord).where(LessonVideoProgressRecord.organization_id == tenant.organization_id, LessonVideoProgressRecord.lesson_id == lesson.id))
    if _lesson_snapshot(lesson) != old_snapshot:
        _record_lesson_version(db, tenant, lesson, reason)
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def publish_lesson(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int) -> FormationDetailRead:
    course, lesson = _lesson_for_edit(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
    if course.status != "published":
        raise HTTPException(409, "Publiez d'abord le cours parent.")
    _validate_lesson_publication(db, tenant, lesson, session_id)
    _release_linked_assignment(db, tenant, lesson)
    if lesson.publication_status != "published":
        _ensure_lesson_baseline(db, lesson)
        lesson.publication_status = "published"
        _record_lesson_version(db, tenant, lesson, "published")
        if lesson.available_at is None or current_utc(lesson.available_at) <= current_utc():
            notify_session_students(
                db, organization_id=tenant.organization_id, session_id=session_id,
                event_key=f"lesson.published:{lesson.id}", title="Nouvelle leçon disponible",
                message=f"« {lesson.title} » est disponible dans « {course.title} ».",
                action_label="Ouvrir le cours", action_path="/app/student/courses",
            )
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def restore_lesson_version(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int, version_number: int) -> FormationDetailRead:
    _, lesson = _lesson_for_edit(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
    version = db.scalar(select(LessonVersionRecord).where(
        LessonVersionRecord.organization_id == tenant.organization_id,
        LessonVersionRecord.lesson_id == lesson.id,
        LessonVersionRecord.version_number == version_number,
    ))
    if version is None:
        raise HTTPException(404, "Version introuvable.")
    payload = LessonCreate.model_validate({key: value for key, value in version.snapshot.items() if key != "publication_status"})
    return update_lesson(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id, payload, reason="restored")
