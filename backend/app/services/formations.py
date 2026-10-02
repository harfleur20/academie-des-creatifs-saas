from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    LessonRecord,
    OrganizationMemberRecord,
    SessionTeacherRecord,
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
            OrganizationMemberRecord.role == role,
            OrganizationMemberRecord.status == "active",
        )
    )
    if member is None:
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
    if tenant.organization_role in {"owner", "admin", "manager"}:
        return True
    if tenant.organization_role != "teacher":
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


def _formation_counts(
    db: Session,
    organization_id: int,
    formation_id: int,
) -> tuple[int, int, int, int]:
    session_ids = select(FormationSessionRecord.id).where(
        FormationSessionRecord.organization_id == organization_id,
        FormationSessionRecord.formation_id == formation_id,
    )
    session_count = int(
        db.scalar(
            select(func.count(FormationSessionRecord.id)).where(
                FormationSessionRecord.organization_id == organization_id,
                FormationSessionRecord.formation_id == formation_id,
            )
        )
        or 0
    )
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
    session_count, teacher_count, student_count, course_count = _formation_counts(
        db,
        tenant.organization_id,
        formation.id,
    )
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
        status=formation.status,
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
    return [
        _serialize_formation_summary(db, tenant, record)
        for record in records
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

    summary = _serialize_formation_summary(db, tenant, formation)
    return FormationDetailRead(
        **summary.model_dump(),
        sessions=[
            _serialize_session(item)
            for item in sorted(
                formation.sessions,
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
    formation = FormationRecord(
        organization_id=tenant.organization_id,
        slug=payload.slug.strip().lower(),
        title=payload.title.strip(),
        description=payload.description.strip(),
        category=payload.category.strip(),
        level=payload.level.strip(),
        format_type=payload.format_type,
        training_hours=payload.training_hours,
        status=payload.status,
    )
    db.add(formation)
    try:
        db.commit()
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

    for key, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(formation, key, value)
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
        status=payload.status,
    )
    db.add(record)
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
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(session, key, value)
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
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    if session is None or session.formation_id != formation_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    _require_member(db, tenant, user_id=payload.user_id, role="student")

    active_count = int(
        db.scalar(
            select(func.count(EnrollmentRecord.id)).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.session_id == session.id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        )
        or 0
    )
    if session.seat_capacity > 0 and active_count >= session.seat_capacity:
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
    session = _get_scoped(db, tenant, FormationSessionRecord, session_id)
    enrollment = _get_scoped(db, tenant, EnrollmentRecord, enrollment_id)
    if (
        session is None
        or session.formation_id != formation_id
        or enrollment is None
        or enrollment.session_id != session_id
    ):
        raise HTTPException(status_code=404, detail="Inscription introuvable.")
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
    if tenant.organization_role == "teacher":
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
    if tenant.organization_role == "teacher":
        values.pop("teacher_id", None)
        if course.teacher_id not in {None, tenant.user.id}:
            raise HTTPException(status_code=403, detail="Ce cours appartient à un autre professeur.")
        course.teacher_id = tenant.user.id
    elif "teacher_id" in values and values["teacher_id"] is not None:
        _require_member(db, tenant, user_id=values["teacher_id"], role="teacher")

    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(course, key, value)
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
    if tenant.organization_role == "teacher" and course.teacher_id not in {None, tenant.user.id}:
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
    if tenant.organization_role == "teacher" and course.teacher_id not in {None, tenant.user.id}:
        raise HTTPException(status_code=403, detail="Ce cours appartient à un autre professeur.")

    lesson = LessonRecord(
        organization_id=tenant.organization_id,
        chapter_id=chapter.id,
        title=payload.title.strip(),
        order_index=payload.order_index,
        lesson_type=payload.lesson_type,
        content=payload.content.strip() if payload.content else None,
        video_url=payload.video_url.strip() if payload.video_url else None,
        file_url=payload.file_url.strip() if payload.file_url else None,
    )
    db.add(lesson)
    db.commit()
    return get_formation_detail(db, tenant, formation_id)
