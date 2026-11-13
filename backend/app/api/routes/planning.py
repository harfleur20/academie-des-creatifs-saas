import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.schemas.planning import (
    CourseDayCreate,
    CourseDayDraftPublish,
    CourseDayUpdate,
    CourseDayReportSubmit,
    CourseDayFeedbackSubmit,
    CourseDayFeedbackReviewRead,
    SchoolCourseDayReportRead,
    SchoolMissingCourseDayReportRead,
    SessionPlanningRead,
    LiveHeartbeatRead,
    LiveRollCallRead,
    LiveRoomInfoRead,
    LiveRoomRead,
    LiveStartRead,
)
from app.services.live_classes import (
    answer_roll_call, heartbeat_live_class, jaas_room_branding, join_live_class, leave_live_class, live_class_info,
    self_hosted_room_branding, start_live_class, start_roll_call,
)
from app.services.planning import (
    create_course_day,
    get_session_planning,
    publish_course_day_draft,
    update_course_day,
    submit_course_day_report,
    submit_course_day_feedback,
    list_course_day_feedback,
    list_school_course_day_reports,
    list_school_missing_course_day_reports,
)
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/live/branding")
def read_jaas_room_branding(
    conference: str = Query(max_length=512),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """JaaS Advanced Branding calls this endpoint with its configured Authorization value."""
    if not settings.jaas_branding_token:
        raise HTTPException(503, "Identité des salles JaaS non configurée.")
    if not hmac.compare_digest(authorization, settings.jaas_branding_token):
        raise HTTPException(401, "Jeton JaaS invalide.")
    branding = jaas_room_branding(db, conference)
    if branding is None:
        raise HTTPException(404, "Salle live introuvable.")
    return branding


@router.get("/live/room-branding")
def read_self_hosted_room_branding(
    response: Response,
    conference_fqn: str = Query(alias="conferenceFqn", max_length=512),
    db: Session = Depends(get_db),
):
    """The self-hosted Jitsi (BRANDING_DATA_URL in infra/live) asks this from the browser, without cookies.

    Only a school's public identity is returned: its color and logo.
    """
    if settings.jitsi_domain:
        response.headers["Access-Control-Allow-Origin"] = f"https://{settings.jitsi_domain}"
    branding = self_hosted_room_branding(db, conference_fqn)
    if branding is None:
        raise HTTPException(404, "Salle live introuvable.")
    response.headers["Cache-Control"] = "public, max-age=300"
    return branding


@router.get("/reports", response_model=list[SchoolCourseDayReportRead])
def read_school_course_day_reports(
    db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    return list_school_course_day_reports(db, tenant)


@router.get("/reports/missing", response_model=list[SchoolMissingCourseDayReportRead])
def read_school_missing_course_day_reports(
    db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context),
):
    return list_school_missing_course_day_reports(db, tenant)


@router.get("/course-days/{course_day_id}/live", response_model=LiveRoomInfoRead)
def read_course_day_live(
    course_day_id: int, db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return live_class_info(db, tenant, course_day_id)


@router.post("/course-days/{course_day_id}/live/join", response_model=LiveRoomRead)
def join_course_day_live(
    course_day_id: int,
    response: Response,
    x_live_device_id: str = Header(default="", max_length=256),
    x_live_device_label: str = Header(default="", max_length=512),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    response.headers["Cache-Control"] = "private, no-store"
    return join_live_class(db, tenant, course_day_id, device_id=x_live_device_id, device_label=x_live_device_label)


@router.post("/course-days/{course_day_id}/live/heartbeat", response_model=LiveHeartbeatRead)
def heartbeat_course_day_live(
    course_day_id: int,
    x_live_device_id: str = Header(default="", max_length=256),
    x_live_device_label: str = Header(default="", max_length=512),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return heartbeat_live_class(db, tenant, course_day_id, device_id=x_live_device_id, device_label=x_live_device_label)


@router.post("/course-days/{course_day_id}/live/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_course_day_live(
    course_day_id: int,
    x_live_device_id: str = Header(default="", max_length=256),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    leave_live_class(db, tenant, course_day_id, device_id=x_live_device_id)


@router.post("/course-days/{course_day_id}/live/roll-call", response_model=LiveRollCallRead)
def start_course_day_roll_call(
    course_day_id: int, db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return start_roll_call(db, tenant, course_day_id)


@router.post("/course-days/{course_day_id}/live/roll-call/{roll_call_id}/answer", status_code=status.HTTP_204_NO_CONTENT)
def answer_course_day_roll_call(
    course_day_id: int, roll_call_id: int, db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    answer_roll_call(db, tenant, course_day_id, roll_call_id)


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
