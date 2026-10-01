from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.schemas.subscriptions import (
    DemoCheckoutCreate,
    DemoPaymentAttemptRead,
    DemoPaymentConfirmationRead,
    EntitlementCheckRead,
    PaymentModeRead,
    PlanRead,
    SubscriptionRead,
)
from app.services.billing_payments import (
    confirm_demo_payment_attempt,
    create_demo_payment_attempt,
)
from app.services.subscriptions import (
    check_entitlement,
    get_current_subscription,
    list_public_plans,
)
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/payment-mode", response_model=PaymentModeRead)
def get_payment_mode() -> PaymentModeRead:
    return PaymentModeRead(
        mode=settings.payment_mode,
        demo_enabled=settings.demo_payments_enabled,
    )


@router.get("/plans", response_model=list[PlanRead])
def get_plans(
    db: Session = Depends(get_db),
):
    return list_public_plans(db)


@router.get("/subscription", response_model=SubscriptionRead)
def get_subscription(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    subscription = get_current_subscription(db, tenant.organization_id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun abonnement actif pour cette école.",
        )
    return subscription


@router.get(
    "/entitlements/{feature_key}",
    response_model=EntitlementCheckRead,
)
def get_entitlement(
    feature_key: str,
    usage_metric_key: str | None = None,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    decision = check_entitlement(
        db,
        organization_id=tenant.organization_id,
        feature_key=feature_key,
        usage_metric_key=usage_metric_key,
    )
    return EntitlementCheckRead(
        feature_key=decision.feature_key,
        enabled=decision.enabled,
        limit_value=decision.limit_value,
        current_value=decision.current_value,
        allowed=decision.allowed,
    )


@router.post(
    "/demo/checkout",
    response_model=DemoPaymentAttemptRead,
    status_code=status.HTTP_201_CREATED,
)
def create_demo_checkout(
    payload: DemoCheckoutCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_demo_payment_attempt(
        db,
        tenant,
        plan_code=payload.plan_code,
        billing_interval=payload.billing_interval,
    )


@router.post(
    "/demo/payments/{payment_attempt_id}/confirm",
    response_model=DemoPaymentConfirmationRead,
)
def confirm_demo_checkout(
    payment_attempt_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    payment, subscription = confirm_demo_payment_attempt(
        db,
        tenant,
        payment_attempt_id=payment_attempt_id,
    )
    return DemoPaymentConfirmationRead(
        payment=payment,
        subscription=subscription,
    )
