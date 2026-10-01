from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    PlanEntitlementRecord,
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


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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


def get_current_subscription(
    db: Session,
    organization_id: int,
) -> SubscriptionRecord | None:
    now = utc_now()

    subscriptions = list(
        db.scalars(
            select(SubscriptionRecord)
            .options(
                selectinload(SubscriptionRecord.plan).selectinload(
                    PlanRecord.entitlements
                )
            )
            .where(
                SubscriptionRecord.organization_id == organization_id,
            )
            .order_by(SubscriptionRecord.created_at.desc())
        ).all()
    )

    for subscription in subscriptions:
        if subscription.status == "trialing":
            trial_end = _aware_utc(subscription.trial_ends_at)
            if trial_end is not None and trial_end <= now:
                subscription.status = "suspended"
                db.commit()
                continue

        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES:
            return subscription

    return None


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
    )
    db.add(subscription)
    db.flush()
    return subscription


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
    subscription = get_current_subscription(db, organization_id)
    if subscription is None:
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
            for item in subscription.plan.entitlements
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
