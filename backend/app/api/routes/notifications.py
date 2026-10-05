from fastapi import APIRouter, Depends, Query, status
from typing import Literal
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.notifications import NotificationIds, SchoolNotificationRead
from app.services.school_notifications import list_notifications, update_notification_state
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[SchoolNotificationRead])
def list_my_notifications(
    space: Literal["manage", "teacher", "student"] = Query(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_notifications(db, tenant, space)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def read_my_notifications(
    payload: NotificationIds,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> None:
    update_notification_state(db, tenant, payload.ids, dismiss=False)


@router.post("/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_my_notifications(
    payload: NotificationIds,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> None:
    update_notification_state(db, tenant, payload.ids, dismiss=True)
