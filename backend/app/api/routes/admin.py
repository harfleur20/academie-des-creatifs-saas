from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_super_admin
from app.db.session import get_db
from sqlalchemy import select

from app.models.entities import AddonRecord, OrganizationRecord, UserRecord
from app.schemas.revenue import AdminAddonUpdate, AdminPayoutProcess, AdminPayoutRead, PayoutRead
from app.schemas.subscriptions import AddonRead
from app.services.plan_limits import admin_update_addon
from app.services.school_revenue import admin_list_payouts, process_payout
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


@router.get("/addons", response_model=list[AddonRead])
def admin_addons(db: Session = Depends(get_db), _: UserRecord = Depends(get_super_admin)):
    return list(db.scalars(select(AddonRecord).order_by(AddonRecord.sort_order)).all())


@router.patch("/addons/{code}", response_model=AddonRead)
def admin_patch_addon(
    code: str,
    payload: AdminAddonUpdate,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    return admin_update_addon(db, actor=current_admin, code=code, values=payload.model_dump(exclude_unset=True), reason=reason)


def _admin_payout_read(payout, organization) -> AdminPayoutRead:
    return AdminPayoutRead.model_validate({
        **PayoutRead.model_validate(payout).model_dump(),
        "organization_id": organization.id,
        "organization_name": organization.name,
    })


@router.get("/payouts", response_model=list[AdminPayoutRead])
def admin_payouts(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return [_admin_payout_read(payout, org) for payout, org in admin_list_payouts(db, status_filter=status_filter)]


@router.post("/payouts/{payout_id}/paid", response_model=AdminPayoutRead)
def admin_mark_payout_paid(
    payout_id: int,
    payload: AdminPayoutProcess,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    payout = process_payout(db, current_admin, payout_id, paid=True,
                            transfer_reference=payload.transfer_reference, note=payload.note)
    return _admin_payout_read(payout, db.get(OrganizationRecord, payout.organization_id))


@router.post("/payouts/{payout_id}/reject", response_model=AdminPayoutRead)
def admin_reject_payout(
    payout_id: int,
    payload: AdminPayoutProcess,
    db: Session = Depends(get_db),
    current_admin: UserRecord = Depends(get_super_admin),
):
    payout = process_payout(db, current_admin, payout_id, paid=False, note=payload.note)
    return _admin_payout_read(payout, db.get(OrganizationRecord, payout.organization_id))
