from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.formations import (
    ChapterCreate,
    CourseCreate,
    CourseUpdate,
    EnrollmentUpdate,
    FormationCreate,
    FormationDetailRead,
    FormationSummaryRead,
    FormationUpdate,
    LessonCreate,
    SessionCreate,
    SessionUpdate,
    TeacherAssignmentCreate,
)
from app.services.formations import (
    FormationConflictError,
    assign_teacher,
    create_chapter,
    create_course,
    create_formation,
    create_lesson,
    create_session,
    get_formation_detail,
    list_formations,
    remove_teacher,
    publish_lesson,
    update_course,
    update_lesson,
    update_enrollment,
    update_formation,
    update_session,
)
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/formations", tags=["formations"])


@router.get("", response_model=list[FormationSummaryRead])
def list_formations_route(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return list_formations(db, tenant)


@router.post(
    "",
    response_model=FormationSummaryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_formation_route(
    payload: FormationCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    try:
        return create_formation(db, tenant, payload)
    except FormationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{formation_id}", response_model=FormationDetailRead)
def get_formation_route(
    formation_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    formation = get_formation_detail(db, tenant, formation_id)
    if formation is None:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    return formation


@router.patch("/{formation_id}", response_model=FormationSummaryRead)
def update_formation_route(
    formation_id: int,
    payload: FormationUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return update_formation(db, tenant, formation_id, payload)


@router.post(
    "/{formation_id}/sessions",
    response_model=FormationDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def create_session_route(
    formation_id: int,
    payload: SessionCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return create_session(db, tenant, formation_id, payload)


@router.patch(
    "/{formation_id}/sessions/{session_id}",
    response_model=FormationDetailRead,
)
def update_session_route(
    formation_id: int,
    session_id: int,
    payload: SessionUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return update_session(db, tenant, formation_id, session_id, payload)


@router.post(
    "/{formation_id}/sessions/{session_id}/teachers",
    response_model=FormationDetailRead,
)
def assign_teacher_route(
    formation_id: int,
    session_id: int,
    payload: TeacherAssignmentCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return assign_teacher(db, tenant, formation_id, session_id, payload)


@router.delete(
    "/{formation_id}/sessions/{session_id}/teachers/{teacher_id}",
    response_model=FormationDetailRead,
)
def remove_teacher_route(
    formation_id: int,
    session_id: int,
    teacher_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return remove_teacher(db, tenant, formation_id, session_id, teacher_id)


@router.patch(
    "/{formation_id}/sessions/{session_id}/enrollments/{enrollment_id}",
    response_model=FormationDetailRead,
)
def update_enrollment_route(
    formation_id: int,
    session_id: int,
    enrollment_id: int,
    payload: EnrollmentUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return update_enrollment(
        db,
        tenant,
        formation_id,
        session_id,
        enrollment_id,
        payload,
    )


@router.post(
    "/{formation_id}/sessions/{session_id}/courses",
    response_model=FormationDetailRead,
)
def create_course_route(
    formation_id: int,
    session_id: int,
    payload: CourseCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return create_course(db, tenant, formation_id, session_id, payload)


@router.patch(
    "/{formation_id}/sessions/{session_id}/courses/{course_id}",
    response_model=FormationDetailRead,
)
def update_course_route(
    formation_id: int,
    session_id: int,
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return update_course(db, tenant, formation_id, session_id, course_id, payload)


@router.post(
    "/{formation_id}/sessions/{session_id}/courses/{course_id}/chapters",
    response_model=FormationDetailRead,
)
def create_chapter_route(
    formation_id: int,
    session_id: int,
    course_id: int,
    payload: ChapterCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return create_chapter(db, tenant, formation_id, session_id, course_id, payload)


@router.post(
    "/{formation_id}/sessions/{session_id}/courses/{course_id}/chapters/{chapter_id}/lessons",
    response_model=FormationDetailRead,
)
def create_lesson_route(
    formation_id: int,
    session_id: int,
    course_id: int,
    chapter_id: int,
    payload: LessonCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return create_lesson(
        db,
        tenant,
        formation_id,
        session_id,
        course_id,
        chapter_id,
        payload,
    )


@router.put(
    "/{formation_id}/sessions/{session_id}/courses/{course_id}/chapters/{chapter_id}/lessons/{lesson_id}",
    response_model=FormationDetailRead,
)
def update_lesson_route(
    formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int,
    payload: LessonCreate, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return update_lesson(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id, payload)


@router.post(
    "/{formation_id}/sessions/{session_id}/courses/{course_id}/chapters/{chapter_id}/lessons/{lesson_id}/publish",
    response_model=FormationDetailRead,
)
def publish_lesson_route(
    formation_id: int, session_id: int, course_id: int, chapter_id: int, lesson_id: int,
    db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return publish_lesson(db, tenant, formation_id, session_id, course_id, chapter_id, lesson_id)
