from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_super_admin
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.admin import (
    AdminActionPayload,
    AdminDashboardRead,
    AdminExtendTrialPayload,
    AdminOrganizationDetailRead,
    AdminOrganizationRead,
)
from app.services.admin import (
    extend_trial,
    get_admin_dashboard,
    get_admin_organization,
    list_admin_organizations,
    reactivate_organization,
    suspend_organization,
)


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardRead)
def admin_dashboard(
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return get_admin_dashboard(db)


@router.get("/organizations", response_model=list[AdminOrganizationRead])
def admin_organizations(
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return list_admin_organizations(db)



@router.get(
    "/organizations/{organization_id}",
    response_model=AdminOrganizationDetailRead,
)
def admin_organization_detail(
    organization_id: int,
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return get_admin_organization(db, organization_id)


@router.post(
    "/organizations/{organization_id}/suspend",
    response_model=AdminOrganizationDetailRead,
)
def admin_suspend_organization(
    organization_id: int,
    payload: AdminActionPayload,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return suspend_organization(
        db,
        actor=current_admin,
        organization_id=organization_id,
        reason=payload.reason,
    )


@router.post(
    "/organizations/{organization_id}/reactivate",
    response_model=AdminOrganizationDetailRead,
)
def admin_reactivate_organization(
    organization_id: int,
    payload: AdminActionPayload,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return reactivate_organization(
        db,
        actor=current_admin,
        organization_id=organization_id,
        reason=payload.reason,
    )


@router.post(
    "/organizations/{organization_id}/extend-trial",
    response_model=AdminOrganizationDetailRead,
)
def admin_extend_trial(
    organization_id: int,
    payload: AdminExtendTrialPayload,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return extend_trial(
        db,
        actor=current_admin,
        organization_id=organization_id,
        days=payload.days,
        reason=payload.reason,
    )
