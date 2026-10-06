from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.planning import (
    CourseDayCreate,
    CourseDayDraftPublish,
    CourseDayUpdate,
    CourseDayReportSubmit,
    CourseDayFeedbackSubmit,
    CourseDayFeedbackReviewRead,
    SchoolCourseDayReportRead,
    SessionPlanningRead,
    LiveRoomRead,
    LiveStartRead,
)
from app.services.live_classes import join_live_class, start_live_class
from app.services.planning import (
    create_course_day,
    get_session_planning,
    publish_course_day_draft,
    update_course_day,
    submit_course_day_report,
    submit_course_day_feedback,
    list_course_day_feedback,
    list_school_course_day_reports,
)
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/reports", response_model=list[SchoolCourseDayReportRead])
def read_school_course_day_reports(
    db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    return list_school_course_day_reports(db, tenant)


@router.post("/course-days/{course_day_id}/live/join", response_model=LiveRoomRead)
def join_course_day_live(
    course_day_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return join_live_class(db, tenant, course_day_id)


@router.post("/course-days/{course_day_id}/live/start", response_model=LiveStartRead)
def start_course_day_live(
    course_day_id: int, db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return start_live_class(db, tenant, course_day_id)


@router.get(
    "/sessions/{session_id}/course-days",
    response_model=SessionPlanningRead,
)
def read_session_planning(
    session_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return get_session_planning(db, tenant, session_id)


@router.post(
    "/sessions/{session_id}/course-days",
    response_model=SessionPlanningRead,
    status_code=status.HTTP_201_CREATED,
)
def create_session_course_day(
    session_id: int,
    payload: CourseDayCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_course_day(db, tenant, session_id, payload)


@router.post(
    "/sessions/{session_id}/course-days/publish-draft",
    response_model=SessionPlanningRead,
    status_code=status.HTTP_201_CREATED,
)
def publish_session_course_day_draft(
    session_id: int,
    payload: CourseDayDraftPublish,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return publish_course_day_draft(db, tenant, session_id, payload.days)


@router.patch(
    "/course-days/{course_day_id}",
    response_model=SessionPlanningRead,
)
def update_session_course_day(
    course_day_id: int,
    payload: CourseDayUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return update_course_day(db, tenant, course_day_id, payload)


@router.post("/course-days/{course_day_id}/report", response_model=SessionPlanningRead)
def submit_session_course_day_report(
    course_day_id: int, payload: CourseDayReportSubmit,
    db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    return submit_course_day_report(db, tenant, course_day_id, payload)


@router.post("/course-days/{course_day_id}/feedback", response_model=SessionPlanningRead)
def submit_session_course_day_feedback(
    course_day_id: int, payload: CourseDayFeedbackSubmit,
    db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    return submit_course_day_feedback(db, tenant, course_day_id, payload)


@router.get("/course-days/{course_day_id}/feedback", response_model=list[CourseDayFeedbackReviewRead])
def read_session_course_day_feedback(
    course_day_id: int, db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_course_day_feedback(db, tenant, course_day_id)
