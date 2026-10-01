from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    BillingInvoiceRecord,
    OrganizationPlanOverrideRecord,
    PlanRecord,
    SubscriptionRecord,
    UsageCounterRecord,
)
from app.services.tenancy import TenantContext


ACTIVE_SUBSCRIPTION_STATUSES = {"trialing", "active"}


@dataclass(frozen=True)
class EntitlementDecision:
    feature_key: str
    enabled: bool
    limit_value: int | None
    current_value: int | None
    allowed: bool


def utc_now() -> datetime:
    return datetime.now(UTC)


def aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def period_end(start: datetime, billing_interval: str) -> datetime:
    return start + timedelta(days=365 if billing_interval == "annual" else 30)


def configured_plan_price(plan: PlanRecord, billing_interval: str) -> int | None:
    return (
        plan.annual_price_cents
        if billing_interval == "annual"
        else plan.monthly_price_cents
    )


def list_public_plans(db: Session) -> list[PlanRecord]:
    return list(
        db.scalars(
            select(PlanRecord)
            .options(selectinload(PlanRecord.entitlements))
            .where(
                PlanRecord.is_active.is_(True),
                PlanRecord.is_public.is_(True),
            )
            .order_by(PlanRecord.id)
        ).all()
    )


def _subscription_query(organization_id: int):
    return (
        select(SubscriptionRecord)
        .options(
            selectinload(SubscriptionRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(SubscriptionRecord.organization_id == organization_id)
        .order_by(SubscriptionRecord.created_at.desc(), SubscriptionRecord.id.desc())
    )


def _create_open_renewal_invoice(
    db: Session,
    subscription: SubscriptionRecord,
    *,
    period_start_value: datetime,
    grace_end: datetime,
    now: datetime,
) -> BillingInvoiceRecord | None:
    price = configured_plan_price(subscription.plan, subscription.billing_interval)
    if price is None or price <= 0:
        return None

    existing = db.scalar(
        select(BillingInvoiceRecord).where(
            BillingInvoiceRecord.subscription_id == subscription.id,
            BillingInvoiceRecord.status == "open",
        )
    )
    if existing is not None:
        return existing

    invoice = BillingInvoiceRecord(
        organization_id=subscription.organization_id,
        subscription_id=subscription.id,
        plan_id=subscription.plan_id,
        payment_attempt_id=None,
        invoice_number=f"INV-{now:%Y%m%d}-{subscription.id}-{uuid4().hex[:8].upper()}",
        status="open",
        amount_cents=price,
        currency=subscription.plan.currency,
        billing_interval=subscription.billing_interval,
        period_start=period_start_value,
        period_end=period_end(period_start_value, subscription.billing_interval),
        issued_at=now,
        due_at=grace_end,
        paid_at=None,
    )
    db.add(invoice)
    return invoice


def apply_subscription_lifecycle(
    db: Session,
    subscription: SubscriptionRecord,
    *,
    now: datetime | None = None,
) -> bool:
    now = aware_utc(now) or utc_now()

    if subscription.status == "trialing":
        trial_end = aware_utc(subscription.trial_ends_at)
        if trial_end is not None and trial_end <= now:
            if subscription.cancel_at_period_end:
                subscription.status = "cancelled"
                subscription.cancelled_at = trial_end
                subscription.suspended_at = None
            else:
                subscription.status = "suspended"
                subscription.suspended_at = now
            subscription.grace_period_ends_at = None
            db.add(subscription)
            return True
        return False

    if subscription.status == "active":
        end = aware_utc(subscription.current_period_end)
        if end is None or end > now:
            return False

        if subscription.cancel_at_period_end:
            subscription.status = "cancelled"
            subscription.cancelled_at = end
            subscription.grace_period_ends_at = None
            db.add(subscription)
            return True

        grace_end = end + timedelta(days=settings.billing_grace_period_days)
        subscription.status = "past_due"
        subscription.grace_period_ends_at = grace_end
        _create_open_renewal_invoice(
            db,
            subscription,
            period_start_value=end,
            grace_end=grace_end,
            now=now,
        )
        db.add(subscription)
        return True

    if subscription.status == "past_due":
        grace_end = aware_utc(subscription.grace_period_ends_at)
        if grace_end is not None and grace_end <= now:
            subscription.status = "suspended"
            subscription.suspended_at = now
            db.add(subscription)
            return True

    return False


def run_subscription_lifecycle(
    db: Session,
    *,
    now: datetime | None = None,
    organization_id: int | None = None,
) -> tuple[int, int]:
    query = (
        select(SubscriptionRecord)
        .options(selectinload(SubscriptionRecord.plan))
        .where(SubscriptionRecord.status.in_(["trialing", "active", "past_due"]))
    )
    if organization_id is not None:
        query = query.where(SubscriptionRecord.organization_id == organization_id)

    subscriptions = list(db.scalars(query).all())
    transitioned = 0
    for subscription in subscriptions:
        if apply_subscription_lifecycle(db, subscription, now=now):
            transitioned += 1
    db.commit()
    return len(subscriptions), transitioned


def get_current_subscription(
    db: Session,
    organization_id: int,
) -> SubscriptionRecord | None:
    run_subscription_lifecycle(db, organization_id=organization_id)
    subscriptions = list(db.scalars(_subscription_query(organization_id)).all())
    return next(
        (
            subscription
            for subscription in subscriptions
            if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
        ),
        None,
    )


def get_latest_subscription(
    db: Session,
    organization_id: int,
) -> SubscriptionRecord | None:
    run_subscription_lifecycle(db, organization_id=organization_id)
    return db.scalar(_subscription_query(organization_id).limit(1))


def list_invoices(
    db: Session,
    organization_id: int,
) -> list[BillingInvoiceRecord]:
    return list(
        db.scalars(
            select(BillingInvoiceRecord)
            .options(
                selectinload(BillingInvoiceRecord.plan).selectinload(
                    PlanRecord.entitlements
                )
            )
            .where(BillingInvoiceRecord.organization_id == organization_id)
            .order_by(
                BillingInvoiceRecord.issued_at.desc(),
                BillingInvoiceRecord.id.desc(),
            )
        ).all()
    )


def request_cancel_at_period_end(
    db: Session,
    tenant: TenantContext,
) -> SubscriptionRecord:
    if tenant.user.platform_role != "super_admin" and tenant.organization_role not in {
        "owner",
        "admin",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission insuffisante pour modifier l'abonnement.",
        )

    subscription = get_latest_subscription(db, tenant.organization_id)
    if subscription is None or subscription.status not in {"trialing", "active", "past_due"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun abonnement résiliable.",
        )

    if subscription.status == "past_due":
        now = utc_now()
        subscription.status = "cancelled"
        subscription.cancelled_at = now
        subscription.cancel_at_period_end = False
        subscription.grace_period_ends_at = None

        open_invoices = list(
            db.scalars(
                select(BillingInvoiceRecord).where(
                    BillingInvoiceRecord.subscription_id == subscription.id,
                    BillingInvoiceRecord.status == "open",
                )
            ).all()
        )
        for invoice in open_invoices:
            invoice.status = "void"
            invoice.due_at = None
            db.add(invoice)
    else:
        subscription.cancel_at_period_end = True

    db.commit()
    db.refresh(subscription)
    return db.scalar(_subscription_query(tenant.organization_id).limit(1))


def resume_scheduled_cancellation(
    db: Session,
    tenant: TenantContext,
) -> SubscriptionRecord:
    if tenant.user.platform_role != "super_admin" and tenant.organization_role not in {
        "owner",
        "admin",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission insuffisante pour modifier l'abonnement.",
        )

    subscription = get_latest_subscription(db, tenant.organization_id)
    if subscription is None or subscription.status not in {"trialing", "active", "past_due"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet abonnement ne peut pas être réactivé.",
        )

    subscription.cancel_at_period_end = False
    db.commit()
    db.refresh(subscription)
    return db.scalar(_subscription_query(tenant.organization_id).limit(1))


def start_default_trial(
    db: Session,
    *,
    organization_id: int,
) -> SubscriptionRecord | None:
    plan = db.scalar(
        select(PlanRecord).where(
            PlanRecord.code == "starter",
            PlanRecord.is_active.is_(True),
        )
    )
    if plan is None:
        return None

    existing = db.scalar(
        select(SubscriptionRecord).where(
            SubscriptionRecord.organization_id == organization_id,
            SubscriptionRecord.status.in_(["trialing", "active"]),
        )
    )
    if existing is not None:
        return existing

    now = utc_now()
    trial_end = now + timedelta(days=plan.trial_days) if plan.trial_days > 0 else None
    subscription = SubscriptionRecord(
        organization_id=organization_id,
        plan_id=plan.id,
        status="trialing" if trial_end is not None else "active",
        billing_interval="monthly",
        started_at=now,
        trial_ends_at=trial_end,
        current_period_start=now,
        current_period_end=trial_end,
        grace_period_ends_at=None,
        suspended_at=None,
    )
    db.add(subscription)
    db.flush()
    return subscription


def get_active_plan_override(
    db: Session,
    organization_id: int,
    *,
    now: datetime | None = None,
) -> OrganizationPlanOverrideRecord | None:
    now = aware_utc(now) or utc_now()
    return db.scalar(
        select(OrganizationPlanOverrideRecord)
        .options(
            selectinload(OrganizationPlanOverrideRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(
            OrganizationPlanOverrideRecord.organization_id == organization_id,
            OrganizationPlanOverrideRecord.status == "active",
            OrganizationPlanOverrideRecord.starts_at <= now,
            OrganizationPlanOverrideRecord.ends_at > now,
        )
        .order_by(
            OrganizationPlanOverrideRecord.created_at.desc(),
            OrganizationPlanOverrideRecord.id.desc(),
        )
        .limit(1)
    )


def get_effective_plan(
    db: Session,
    organization_id: int,
) -> PlanRecord | None:
    override = get_active_plan_override(db, organization_id)
    if override is not None:
        return override.plan

    subscription = get_current_subscription(db, organization_id)
    return subscription.plan if subscription is not None else None


def get_usage(
    db: Session,
    *,
    organization_id: int,
    metric_key: str,
    window_key: str = "lifetime",
) -> int:
    counter = db.scalar(
        select(UsageCounterRecord).where(
            UsageCounterRecord.organization_id == organization_id,
            UsageCounterRecord.metric_key == metric_key,
            UsageCounterRecord.window_key == window_key,
        )
    )
    return counter.current_value if counter is not None else 0


def set_usage(
    db: Session,
    *,
    organization_id: int,
    metric_key: str,
    current_value: int,
    window_key: str = "lifetime",
) -> UsageCounterRecord:
    if current_value < 0:
        raise ValueError("current_value must be non-negative")

    counter = db.scalar(
        select(UsageCounterRecord).where(
            UsageCounterRecord.organization_id == organization_id,
            UsageCounterRecord.metric_key == metric_key,
            UsageCounterRecord.window_key == window_key,
        )
    )
    if counter is None:
        counter = UsageCounterRecord(
            organization_id=organization_id,
            metric_key=metric_key,
            window_key=window_key,
            current_value=current_value,
        )
        db.add(counter)
    else:
        counter.current_value = current_value
    db.flush()
    return counter


def check_entitlement(
    db: Session,
    *,
    organization_id: int,
    feature_key: str,
    usage_metric_key: str | None = None,
) -> EntitlementDecision:
    plan = get_effective_plan(db, organization_id)
    if plan is None:
        return EntitlementDecision(
            feature_key=feature_key,
            enabled=False,
            limit_value=None,
            current_value=None,
            allowed=False,
        )

    entitlement = next(
        (
            item
            for item in plan.entitlements
            if item.feature_key == feature_key
        ),
        None,
    )
    if entitlement is None or not entitlement.enabled:
        return EntitlementDecision(
            feature_key=feature_key,
            enabled=False,
            limit_value=None,
            current_value=None,
            allowed=False,
        )

    current_value = None
    allowed = True
    if entitlement.limit_value is not None and usage_metric_key is not None:
        current_value = get_usage(
            db,
            organization_id=organization_id,
            metric_key=usage_metric_key,
        )
        allowed = current_value < entitlement.limit_value

    return EntitlementDecision(
        feature_key=feature_key,
        enabled=True,
        limit_value=entitlement.limit_value,
        current_value=current_value,
        allowed=allowed,
    )


def require_entitlement(
    db: Session,
    tenant: TenantContext,
    *,
    feature_key: str,
    usage_metric_key: str | None = None,
) -> EntitlementDecision:
    decision = check_entitlement(
        db,
        organization_id=tenant.organization_id,
        feature_key=feature_key,
        usage_metric_key=usage_metric_key,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette fonctionnalité ou ce quota n'est pas disponible avec l'abonnement actuel.",
        )
    return decision
