from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    LessonRecord,
    LessonProgressRecord,
    LessonVideoProgressRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    QuizRecord,
    QuizAttemptRecord,
    ResourceRecord,
    SessionTeacherRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.formations import (
    ChapterCreate,
    CourseCreate,
    CourseUpdate,
    EnrollmentCreate,
    EnrollmentUpdate,
    FormationCreate,
    FormationDetailRead,
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
)
from app.services.membership_roles import member_has_role
from app.services.online_formations import ensure_online_content_session
from app.services.onboarding import get_onboarding_status
from app.services.pdf_lessons import pdf_asset
from app.services.publication import formation_content_issues, formation_publication_issues
from app.services.school_communications import queue_session_students_event
from app.services.school_notifications import notify_user
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
        objectives=formation.objectives,
        prerequisites=formation.prerequisites,
        public_program=formation.public_program,
        price_cents=formation.price_cents,
        currency=formation.currency,
        allow_installments=formation.allow_installments,
        installment_count=formation.installment_count,
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
            _serialize_session(item)
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
        objectives=payload.objectives.strip(),
        prerequisites=payload.prerequisites.strip(),
        public_program=payload.public_program.strip(),
        price_cents=payload.price_cents,
        currency=payload.currency.upper(),
        allow_installments=payload.allow_installments,
        installment_count=payload.installment_count,
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
) -> FormationSummaryRead:
    formation = get_formation_record(db, tenant, formation_id)
    if formation is None:
        raise HTTPException(status_code=404, detail="Formation introuvable.")

    previously_published = formation.status == "published"
    previously_complete = not formation_content_issues(formation)
    for key, value in payload.model_dump(exclude_unset=True).items():
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
    db.commit()
    db.refresh(formation)
    return _serialize_formation_summary(db, tenant, formation)


def create_session(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
    payload: SessionCreate,
) -> FormationDetailRead:
    formation = get_formation_record(db, tenant, formation_id)
    if formation is None:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    record = FormationSessionRecord(
        organization_id=tenant.organization_id,
        formation_id=formation.id,
        label=payload.label.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        campus_label=payload.campus_label.strip() if payload.campus_label else None,
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

    values = payload.model_dump(exclude_unset=True)
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
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(session, key, value)
    if session.status == "open":
        formation = get_formation_record(db, tenant, formation_id)
        issues = formation_publication_issues(db, formation)
        if formation.status != "published" or issues or session.end_date < datetime.now(UTC).date():
            db.rollback()
            raise HTTPException(status_code=422, detail="Ouverture impossible : formation ou session incomplète. " + " ".join(issues))
        if session.price_override_cents == 0:
            db.rollback()
            raise HTTPException(status_code=422, detail="Le prix de la session doit être supérieur à zéro.")
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
    db.delete(assignment)
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
            lesson.publication_status = "published"
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
        if label == "quiz" and payload.lesson_type not in {"quiz", "pdf", "text"}:
            raise HTTPException(422, "Ce type de leçon ne peut pas valider un quiz.")
        if label == "assignment" and payload.lesson_type != "assignment":
            raise HTTPException(422, "Le devoir doit être lié à une leçon de type devoir.")
        if label == "resource" and payload.lesson_type != "resource":
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
        quiz.pass_pct = 70
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


def update_lesson(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int, payload: LessonCreate) -> FormationDetailRead:
    _, lesson = _lesson_for_edit(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
    old_identity = (lesson.lesson_type, lesson.video_url, lesson.file_url, lesson.quiz_id, lesson.assignment_id, lesson.resource_id)
    if lesson.lesson_type == "pdf" and lesson.file_url != payload.file_url and lesson.quiz_id == payload.quiz_id and payload.quiz_id is not None and db.scalar(select(QuizAttemptRecord.id).where(QuizAttemptRecord.organization_id == tenant.organization_id, QuizAttemptRecord.quiz_id == payload.quiz_id)) is not None:
        raise HTTPException(409, "Créez un nouveau quiz pour remplacer un PDF déjà évalué.")
    _validate_lesson_links(db, tenant, session_id, payload, lesson_id=lesson.id)
    for field in ("title", "order_index", "lesson_type", "content", "video_url", "file_url", "quiz_id", "assignment_id", "resource_id", "available_at"):
        value = getattr(payload, field)
        setattr(lesson, field, value.strip() if isinstance(value, str) else value)
    if lesson.publication_status == "published":
        try:
            _validate_lesson_publication(db, tenant, lesson, session_id)
        except HTTPException:
            db.rollback()
            raise
    if old_identity != (lesson.lesson_type, lesson.video_url, lesson.file_url, lesson.quiz_id, lesson.assignment_id, lesson.resource_id):
        db.execute(delete(LessonProgressRecord).where(LessonProgressRecord.organization_id == tenant.organization_id, LessonProgressRecord.lesson_id == lesson.id))
    if old_identity[:2] != (lesson.lesson_type, lesson.video_url):
        db.execute(delete(LessonVideoProgressRecord).where(LessonVideoProgressRecord.organization_id == tenant.organization_id, LessonVideoProgressRecord.lesson_id == lesson.id))
    db.commit()
    return get_formation_detail(db, tenant, formation_id)


def publish_lesson(db: Session, tenant: TenantContext, formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int) -> FormationDetailRead:
    course, lesson = _lesson_for_edit(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
    if course.status != "published":
        raise HTTPException(409, "Publiez d'abord le cours parent.")
    _validate_lesson_publication(db, tenant, lesson, session_id)
    lesson.publication_status = "published"
    db.commit()
    return get_formation_detail(db, tenant, formation_id)
