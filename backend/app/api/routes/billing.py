from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    TaraCheckoutCreate,
    TaraCheckoutRead,
    TaraReconcileRead,
)
from app.services.billing_payments import (
    confirm_demo_payment_attempt,
    create_demo_payment_attempt,
    create_tara_payment_attempt,
    reconcile_tara_attempt,
)
from app.services.subscriptions import (
    check_entitlement,
    get_current_subscription,
    list_public_plans,
)
from app.services.tara_webhook import verify_webhook_authentication
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/billing", tags=["billing"])
MAX_TARA_WEBHOOK_BYTES = 16 * 1024


@router.get("/payment-mode", response_model=PaymentModeRead)
def get_payment_mode() -> PaymentModeRead:
    return PaymentModeRead(
        mode=settings.payment_mode,
        demo_enabled=settings.demo_payments_enabled,
        tara_configured=settings.tara_configured,
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


@router.post(
    "/tara/checkout",
    response_model=TaraCheckoutRead,
    status_code=status.HTTP_201_CREATED,
)
def create_tara_checkout(
    payload: TaraCheckoutCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    payment, checkout_url = create_tara_payment_attempt(
        db,
        tenant,
        plan_code=payload.plan_code,
        billing_interval=payload.billing_interval,
    )
    return TaraCheckoutRead(
        payment=payment,
        checkout_url=checkout_url,
    )


@router.post(
    "/tara/reconcile/{provider_reference}",
    response_model=TaraReconcileRead,
)
def reconcile_tara_checkout(
    provider_reference: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    payment, subscription, payment_status = reconcile_tara_attempt(
        db,
        provider_reference=provider_reference,
        organization_id=tenant.organization_id,
    )
    return TaraReconcileRead(
        payment=payment,
        subscription=subscription,
        status=payment_status,
    )


@router.post("/tara/webhook")
async def tara_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    if len(raw_body) > MAX_TARA_WEBHOOK_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Notification TaraMoney trop volumineuse.",
        )

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload TaraMoney non JSON.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload TaraMoney invalide.",
        )

    authenticated = verify_webhook_authentication(raw_body, request.headers)

    product_id = payload.get("productId") or payload.get("product_id")
    business_id = payload.get("businessId")

    if not isinstance(product_id, str) or not product_id.startswith("SAAS-"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Référence TaraMoney invalide.",
        )

    # Un webhook non authentifié est seulement un indice. On exige alors au
    # minimum le businessId attendu avant la vérification serveur-to-server.
    if not authenticated and business_id != settings.tara_business_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Notification TaraMoney non vérifiable.",
        )

    payment, subscription, payment_status = reconcile_tara_attempt(
        db,
        provider_reference=product_id,
    )
    return {
        "received": True,
        "authenticated": authenticated,
        "status": payment_status,
        "payment_id": payment.id,
        "subscription_id": subscription.id if subscription else None,
    }
