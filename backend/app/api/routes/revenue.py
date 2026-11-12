from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.revenue import LedgerEntryRead, PayoutRead, PayoutRequest, RevenueSummaryRead
from app.services.school_revenue import (
    cancel_payout,
    list_ledger,
    list_payouts,
    request_payout,
    require_finance_admin,
    revenue_summary,
)
from app.services.tenancy import TenantContext

router = APIRouter(prefix="/revenue", tags=["revenue"])


def _require_reader(tenant: TenantContext) -> None:
    if not tenant.support_mode:
        require_finance_admin(tenant)


@router.get("/summary", response_model=RevenueSummaryRead)
def get_summary(db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    _require_reader(tenant)
    return revenue_summary(db, tenant.organization_id)


@router.get("/entries", response_model=list[LedgerEntryRead])
def get_entries(db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    _require_reader(tenant)
    return list_ledger(db, tenant.organization_id)


@router.get("/payouts", response_model=list[PayoutRead])
def get_payouts(db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    _require_reader(tenant)
    return list_payouts(db, tenant.organization_id)


@router.post("/payouts", response_model=PayoutRead, status_code=201)
def post_payout(payload: PayoutRequest, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return request_payout(db, tenant, amount_cents=payload.amount_cents, method=payload.method,
                          destination=payload.destination, account_name=payload.account_name)


@router.post("/payouts/{payout_id}/cancel", response_model=PayoutRead)
def post_cancel_payout(payout_id: int, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return cancel_payout(db, tenant, payout_id)
