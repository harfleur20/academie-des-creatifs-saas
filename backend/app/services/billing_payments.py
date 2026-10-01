from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    BillingPaymentAttemptRecord,
    PlanRecord,
    SubscriptionRecord,
)
from app.services.tenancy import TenantContext


def _utc_now() -> datetime:
    return datetime.now(UTC)


def require_demo_payments_enabled() -> None:
    if not settings.demo_payments_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le mode paiement démo est désactivé.",
        )


def _require_billing_admin(tenant: TenantContext) -> None:
    if tenant.user.platform_role == "super_admin":
        return
    if tenant.organization_role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls le propriétaire ou un administrateur peuvent gérer l'abonnement.",
        )


def _price_for_plan(
    plan: PlanRecord,
    billing_interval: str,
) -> int:
    configured = (
        plan.annual_price_cents
        if billing_interval == "annual"
        else plan.monthly_price_cents
    )
    if configured is not None and configured > 0:
        return configured
    return settings.demo_payment_amount_cents


def create_demo_payment_attempt(
    db: Session,
    tenant: TenantContext,
    *,
    plan_code: str,
    billing_interval: str,
) -> BillingPaymentAttemptRecord:
    require_demo_payments_enabled()
    _require_billing_admin(tenant)

    plan = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .where(
            PlanRecord.code == plan_code.strip().lower(),
            PlanRecord.is_active.is_(True),
            PlanRecord.is_public.is_(True),
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forfait introuvable.",
        )

    if billing_interval not in {"monthly", "annual"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Période de facturation invalide.",
        )

    attempt = BillingPaymentAttemptRecord(
        organization_id=tenant.organization_id,
        plan_id=plan.id,
        billing_interval=billing_interval,
        provider="demo",
        provider_reference=f"DEMO-{tenant.organization_id}-{uuid4().hex}",
        status="pending",
        amount_cents=_price_for_plan(plan, billing_interval),
        currency=plan.currency,
    )
    db.add(attempt)
    db.commit()
    return db.scalar(
        select(BillingPaymentAttemptRecord)
        .options(
            selectinload(BillingPaymentAttemptRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(BillingPaymentAttemptRecord.id == attempt.id)
    )


def _period_end(now: datetime, billing_interval: str) -> datetime:
    if billing_interval == "annual":
        return now + timedelta(days=365)
    return now + timedelta(days=30)


def confirm_demo_payment_attempt(
    db: Session,
    tenant: TenantContext,
    *,
    payment_attempt_id: int,
) -> tuple[BillingPaymentAttemptRecord, SubscriptionRecord]:
    require_demo_payments_enabled()
    _require_billing_admin(tenant)

    attempt = db.scalar(
        select(BillingPaymentAttemptRecord)
        .options(
            selectinload(BillingPaymentAttemptRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(
            BillingPaymentAttemptRecord.id == payment_attempt_id,
            BillingPaymentAttemptRecord.organization_id == tenant.organization_id,
            BillingPaymentAttemptRecord.provider == "demo",
        )
        .with_for_update()
    )
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paiement démo introuvable.",
        )

    existing = db.scalar(
        select(SubscriptionRecord)
        .options(
            selectinload(SubscriptionRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(
            SubscriptionRecord.organization_id == tenant.organization_id,
            SubscriptionRecord.provider_subscription_id
            == f"demo:{attempt.provider_reference}",
        )
    )
    if attempt.status == "paid" and existing is not None:
        return attempt, existing

    if attempt.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce paiement démo ne peut plus être confirmé.",
        )

    now = _utc_now()

    active_subscriptions = list(
        db.scalars(
            select(SubscriptionRecord)
            .where(
                SubscriptionRecord.organization_id == tenant.organization_id,
                SubscriptionRecord.status.in_(["trialing", "active", "past_due"]),
            )
            .with_for_update()
        ).all()
    )
    for subscription in active_subscriptions:
        subscription.status = "cancelled"
        subscription.cancelled_at = now
        subscription.cancel_at_period_end = False
        db.add(subscription)

    subscription = SubscriptionRecord(
        organization_id=tenant.organization_id,
        plan_id=attempt.plan_id,
        status="active",
        billing_interval=attempt.billing_interval,
        started_at=now,
        trial_ends_at=None,
        current_period_start=now,
        current_period_end=_period_end(now, attempt.billing_interval),
        cancel_at_period_end=False,
        provider="demo",
        provider_subscription_id=f"demo:{attempt.provider_reference}",
    )
    db.add(subscription)

    attempt.status = "paid"
    attempt.confirmed_at = now
    db.add(attempt)
    db.commit()

    payment = db.scalar(
        select(BillingPaymentAttemptRecord)
        .options(
            selectinload(BillingPaymentAttemptRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(BillingPaymentAttemptRecord.id == attempt.id)
    )
    subscription = db.scalar(
        select(SubscriptionRecord)
        .options(
            selectinload(SubscriptionRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(SubscriptionRecord.id == subscription.id)
    )
    return payment, subscription
