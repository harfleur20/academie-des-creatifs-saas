from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_super_admin
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.admin import (
    AdminActionPayload,
    AdminCommercialAccessPayload,
    AdminDashboardRead,
    AdminExtendTrialPayload,
    AdminOrganizationDetailRead,
    AdminOrganizationRead,
    AdminPlanEntitlementsPayload,
    AdminPlanRead,
    AdminPlanUpdate,
    AdminSupportSessionPayload,
    AdminSupportSessionRead,
)
from app.services.admin import (
    cancel_commercial_access,
    extend_trial,
    get_admin_dashboard,
    get_admin_organization,
    list_admin_organizations,
    grant_commercial_access,
    list_admin_plans,
    reactivate_organization,
    replace_admin_plan_entitlements,
    start_support_session,
    suspend_organization,
    update_admin_plan,
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



@router.get("/plans", response_model=list[AdminPlanRead])
def admin_plans(
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return list_admin_plans(db)


@router.patch("/plans/{plan_id}", response_model=AdminPlanRead)
def admin_update_plan(
    plan_id: int,
    payload: AdminPlanUpdate,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return update_admin_plan(
        db,
        actor=current_admin,
        plan_id=plan_id,
        values=payload.model_dump(exclude_unset=True),
        reason=reason,
    )


@router.put(
    "/plans/{plan_id}/entitlements",
    response_model=AdminPlanRead,
)
def admin_replace_plan_entitlements(
    plan_id: int,
    payload: AdminPlanEntitlementsPayload,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return replace_admin_plan_entitlements(
        db,
        actor=current_admin,
        plan_id=plan_id,
        entitlements=[
            item.model_dump()
            for item in payload.entitlements
        ],
        reason=reason,
    )



@router.post(
    "/organizations/{organization_id}/commercial-access",
    response_model=AdminOrganizationDetailRead,
)
def admin_grant_commercial_access(
    organization_id: int,
    payload: AdminCommercialAccessPayload,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return grant_commercial_access(
        db,
        actor=current_admin,
        organization_id=organization_id,
        plan_id=payload.plan_id,
        days=payload.days,
        reason=payload.reason,
    )


@router.delete(
    "/organizations/{organization_id}/commercial-access",
    response_model=AdminOrganizationDetailRead,
)
def admin_cancel_commercial_access(
    organization_id: int,
    payload: AdminActionPayload,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return cancel_commercial_access(
        db,
        actor=current_admin,
        organization_id=organization_id,
        reason=payload.reason,
    )


@router.post(
    "/organizations/{organization_id}/support-session",
    response_model=AdminSupportSessionRead,
)
def admin_start_support_session(
    organization_id: int,
    payload: AdminSupportSessionPayload,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return start_support_session(
        db,
        actor=current_admin,
        organization_id=organization_id,
        reason=payload.reason,
    )
