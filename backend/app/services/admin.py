from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    BillingInvoiceRecord,
    OrganizationDomainRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    PlatformAdminAuditRecord,
    PlanEntitlementRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.schemas.admin import (
    AdminAuditRead,
    AdminDashboardRead,
    AdminOrganizationDetailRead,
    AdminOrganizationRead,
    AdminOrganizationSubscriptionRead,
    AdminPlanRead,
    AdminRevenueTotal,
)


CURRENT_SUBSCRIPTION_STATUSES = {
    "trialing",
    "active",
    "past_due",
    "suspended",
}


def get_admin_dashboard(db: Session) -> AdminDashboardRead:
    organizations_total = int(
        db.scalar(select(func.count(OrganizationRecord.id))) or 0
    )
    organizations_active = int(
        db.scalar(
            select(func.count(OrganizationRecord.id)).where(
                OrganizationRecord.is_active.is_(True),
                OrganizationRecord.status == "active",
            )
        )
        or 0
    )
    organizations_suspended = int(
        db.scalar(
            select(func.count(OrganizationRecord.id)).where(
                (OrganizationRecord.is_active.is_(False))
                | (OrganizationRecord.status != "active")
            )
        )
        or 0
    )
    users_total = int(db.scalar(select(func.count(UserRecord.id))) or 0)

    subscription_counts = dict(
        db.execute(
            select(
                SubscriptionRecord.status,
                func.count(SubscriptionRecord.id),
            )
            .where(
                SubscriptionRecord.status.in_(
                    ["trialing", "active", "past_due", "suspended"]
                )
            )
            .group_by(SubscriptionRecord.status)
        ).all()
    )

    revenue_rows = db.execute(
        select(
            BillingInvoiceRecord.currency,
            func.coalesce(func.sum(BillingInvoiceRecord.amount_cents), 0),
            func.count(BillingInvoiceRecord.id),
        )
        .where(BillingInvoiceRecord.status == "paid")
        .group_by(BillingInvoiceRecord.currency)
        .order_by(BillingInvoiceRecord.currency)
    ).all()

    return AdminDashboardRead(
        organizations_total=organizations_total,
        organizations_active=organizations_active,
        organizations_suspended=organizations_suspended,
        subscriptions_trialing=int(subscription_counts.get("trialing", 0)),
        subscriptions_active=int(subscription_counts.get("active", 0)),
        subscriptions_past_due=int(subscription_counts.get("past_due", 0)),
        subscriptions_suspended=int(subscription_counts.get("suspended", 0)),
        users_total=users_total,
        revenue=[
            AdminRevenueTotal(
                currency=currency,
                amount=int(amount or 0),
                paid_invoices=int(count or 0),
            )
            for currency, amount, count in revenue_rows
        ],
    )


def list_admin_organizations(db: Session) -> list[AdminOrganizationRead]:
    organizations = list(
        db.scalars(
            select(OrganizationRecord).order_by(
                OrganizationRecord.created_at.desc(),
                OrganizationRecord.id.desc(),
            )
        ).all()
    )
    if not organizations:
        return []

    organization_ids = [organization.id for organization in organizations]

    member_counts = dict(
        db.execute(
            select(
                OrganizationMemberRecord.organization_id,
                func.count(OrganizationMemberRecord.id),
            )
            .where(
                OrganizationMemberRecord.organization_id.in_(organization_ids)
            )
            .group_by(OrganizationMemberRecord.organization_id)
        ).all()
    )

    domain_counts = dict(
        db.execute(
            select(
                OrganizationDomainRecord.organization_id,
                func.count(OrganizationDomainRecord.id),
            )
            .where(
                OrganizationDomainRecord.organization_id.in_(organization_ids),
                OrganizationDomainRecord.status == "verified",
            )
            .group_by(OrganizationDomainRecord.organization_id)
        ).all()
    )

    owner_rows = db.execute(
        select(
            OrganizationMemberRecord.organization_id,
            UserRecord.full_name,
            UserRecord.email,
        )
        .join(UserRecord, UserRecord.id == OrganizationMemberRecord.user_id)
        .where(
            OrganizationMemberRecord.organization_id.in_(organization_ids),
            OrganizationMemberRecord.role == "owner",
            OrganizationMemberRecord.status == "active",
        )
        .order_by(
            OrganizationMemberRecord.organization_id,
            OrganizationMemberRecord.id,
        )
    ).all()
    owners: dict[int, tuple[str, str]] = {}
    for organization_id, full_name, email in owner_rows:
        owners.setdefault(organization_id, (full_name, email))

    subscriptions = db.execute(
        select(
            SubscriptionRecord,
            PlanRecord.code,
            PlanRecord.name,
        )
        .join(PlanRecord, PlanRecord.id == SubscriptionRecord.plan_id)
        .where(
            SubscriptionRecord.organization_id.in_(organization_ids),
            SubscriptionRecord.status.in_(CURRENT_SUBSCRIPTION_STATUSES),
        )
        .order_by(
            SubscriptionRecord.organization_id,
            SubscriptionRecord.created_at.desc(),
            SubscriptionRecord.id.desc(),
        )
    ).all()

    current_subscriptions: dict[
        int,
        tuple[SubscriptionRecord, str, str],
    ] = {}
    for subscription, plan_code, plan_name in subscriptions:
        current_subscriptions.setdefault(
            subscription.organization_id,
            (subscription, plan_code, plan_name),
        )

    result: list[AdminOrganizationRead] = []
    for organization in organizations:
        owner = owners.get(organization.id)
        current = current_subscriptions.get(organization.id)
        subscription_read = None

        if current is not None:
            subscription, plan_code, plan_name = current
            subscription_read = AdminOrganizationSubscriptionRead(
                id=subscription.id,
                status=subscription.status,
                billing_interval=subscription.billing_interval,
                plan_code=plan_code,
                plan_name=plan_name,
                trial_ends_at=subscription.trial_ends_at,
                current_period_end=subscription.current_period_end,
                grace_period_ends_at=subscription.grace_period_ends_at,
                provider=subscription.provider,
            )

        result.append(
            AdminOrganizationRead(
                id=organization.id,
                name=organization.name,
                slug=organization.slug,
                subdomain=organization.subdomain,
                status=organization.status,
                is_active=organization.is_active,
                contact_email=organization.contact_email,
                logo_url=organization.logo_url,
                created_at=organization.created_at,
                owner_name=owner[0] if owner else None,
                owner_email=owner[1] if owner else None,
                member_count=int(member_counts.get(organization.id, 0)),
                verified_domain_count=int(domain_counts.get(organization.id, 0)),
                subscription=subscription_read,
            )
        )

    return result



def _utc_now() -> datetime:
    return datetime.now(UTC)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _write_admin_audit(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int | None,
    action: str,
    reason: str,
    details: dict[str, object] | None = None,
) -> PlatformAdminAuditRecord:
    record = PlatformAdminAuditRecord(
        actor_user_id=actor.id,
        organization_id=organization_id,
        action=action,
        reason=reason.strip(),
        details=json.dumps(details, ensure_ascii=False, sort_keys=True)
        if details
        else None,
    )
    db.add(record)
    return record


def _get_organization_or_404(
    db: Session,
    organization_id: int,
) -> OrganizationRecord:
    organization = db.get(OrganizationRecord, organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="École introuvable.",
        )
    return organization


def get_admin_organization(
    db: Session,
    organization_id: int,
) -> AdminOrganizationDetailRead:
    organization = _get_organization_or_404(db, organization_id)
    item = next(
        (
            candidate
            for candidate in list_admin_organizations(db)
            if candidate.id == organization.id
        ),
        None,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="École introuvable.",
        )

    audit_rows = db.execute(
        select(
            PlatformAdminAuditRecord,
            UserRecord.full_name,
            UserRecord.email,
        )
        .outerjoin(
            UserRecord,
            UserRecord.id == PlatformAdminAuditRecord.actor_user_id,
        )
        .where(
            PlatformAdminAuditRecord.organization_id == organization.id
        )
        .order_by(
            PlatformAdminAuditRecord.created_at.desc(),
            PlatformAdminAuditRecord.id.desc(),
        )
        .limit(50)
    ).all()

    return AdminOrganizationDetailRead(
        **item.model_dump(),
        audit_logs=[
            AdminAuditRead(
                id=record.id,
                action=record.action,
                reason=record.reason,
                details=record.details,
                actor_user_id=record.actor_user_id,
                actor_name=actor_name,
                actor_email=actor_email,
                created_at=record.created_at,
            )
            for record, actor_name, actor_email in audit_rows
        ],
    )


def suspend_organization(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int,
    reason: str,
) -> AdminOrganizationDetailRead:
    organization = _get_organization_or_404(db, organization_id)

    if not organization.is_active and organization.status == "suspended":
        return get_admin_organization(db, organization_id)

    previous = {
        "status": organization.status,
        "is_active": organization.is_active,
    }
    organization.status = "suspended"
    organization.is_active = False
    db.add(organization)

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=organization.id,
        action="organization.suspended",
        reason=reason,
        details={
            "previous": previous,
            "current": {"status": "suspended", "is_active": False},
        },
    )
    db.commit()
    return get_admin_organization(db, organization.id)


def reactivate_organization(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int,
    reason: str,
) -> AdminOrganizationDetailRead:
    organization = _get_organization_or_404(db, organization_id)

    if organization.is_active and organization.status == "active":
        return get_admin_organization(db, organization_id)

    previous = {
        "status": organization.status,
        "is_active": organization.is_active,
    }
    organization.status = "active"
    organization.is_active = True
    db.add(organization)

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=organization.id,
        action="organization.reactivated",
        reason=reason,
        details={
            "previous": previous,
            "current": {"status": "active", "is_active": True},
        },
    )
    db.commit()
    return get_admin_organization(db, organization.id)


def extend_trial(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int,
    days: int,
    reason: str,
) -> AdminOrganizationDetailRead:
    organization = _get_organization_or_404(db, organization_id)

    subscription = db.scalar(
        select(SubscriptionRecord)
        .where(
            SubscriptionRecord.organization_id == organization.id,
            SubscriptionRecord.trial_ends_at.is_not(None),
            SubscriptionRecord.status.in_(["trialing", "suspended"]),
        )
        .order_by(
            SubscriptionRecord.created_at.desc(),
            SubscriptionRecord.id.desc(),
        )
        .with_for_update()
    )
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette école n'a pas d'essai prolongeable.",
        )

    now = _utc_now()
    previous_end = _aware_utc(subscription.trial_ends_at)
    base = previous_end if previous_end and previous_end > now else now
    new_end = base + timedelta(days=days)

    previous_status = subscription.status
    subscription.status = "trialing"
    subscription.trial_ends_at = new_end
    subscription.current_period_end = new_end
    subscription.grace_period_ends_at = None
    subscription.suspended_at = None
    subscription.cancel_at_period_end = False
    db.add(subscription)

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=organization.id,
        action="subscription.trial_extended",
        reason=reason,
        details={
            "subscription_id": subscription.id,
            "days": days,
            "previous_status": previous_status,
            "previous_trial_end": previous_end.isoformat() if previous_end else None,
            "new_trial_end": new_end.isoformat(),
        },
    )
    db.commit()
    return get_admin_organization(db, organization.id)



def _plan_to_admin_read(plan: PlanRecord) -> AdminPlanRead:
    return AdminPlanRead(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        currency=plan.currency,
        monthly_price_cents=plan.monthly_price_cents,
        annual_price_cents=plan.annual_price_cents,
        trial_days=plan.trial_days,
        is_public=plan.is_public,
        is_active=plan.is_active,
        entitlements=[
            {
                "feature_key": item.feature_key,
                "enabled": item.enabled,
                "limit_value": item.limit_value,
            }
            for item in sorted(
                plan.entitlements,
                key=lambda entitlement: entitlement.feature_key,
            )
        ],
    )


def list_admin_plans(db: Session) -> list[AdminPlanRead]:
    plans = list(
        db.scalars(
            select(PlanRecord)
            .options(selectinload(PlanRecord.entitlements))
            .order_by(PlanRecord.id)
        ).all()
    )
    return [_plan_to_admin_read(plan) for plan in plans]


def update_admin_plan(
    db: Session,
    *,
    actor: UserRecord,
    plan_id: int,
    values: dict[str, object],
    reason: str,
) -> AdminPlanRead:
    plan = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .where(PlanRecord.id == plan_id)
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forfait introuvable.",
        )

    previous = {
        "name": plan.name,
        "description": plan.description,
        "currency": plan.currency,
        "monthly_price_cents": plan.monthly_price_cents,
        "annual_price_cents": plan.annual_price_cents,
        "trial_days": plan.trial_days,
        "is_public": plan.is_public,
        "is_active": plan.is_active,
    }

    for key, value in values.items():
        if key == "currency" and isinstance(value, str):
            value = value.strip().upper()
        if key in {"name", "description"} and isinstance(value, str):
            value = value.strip()
        setattr(plan, key, value)

    db.add(plan)
    _write_admin_audit(
        db,
        actor=actor,
        organization_id=None,
        action="plan.updated",
        reason=reason,
        details={
            "plan_id": plan.id,
            "plan_code": plan.code,
            "previous": previous,
            "current": {
                "name": plan.name,
                "description": plan.description,
                "currency": plan.currency,
                "monthly_price_cents": plan.monthly_price_cents,
                "annual_price_cents": plan.annual_price_cents,
                "trial_days": plan.trial_days,
                "is_public": plan.is_public,
                "is_active": plan.is_active,
            },
        },
    )
    db.commit()

    refreshed = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .where(PlanRecord.id == plan.id)
    )
    return _plan_to_admin_read(refreshed)


def replace_admin_plan_entitlements(
    db: Session,
    *,
    actor: UserRecord,
    plan_id: int,
    entitlements: list[dict[str, object]],
    reason: str,
) -> AdminPlanRead:
    plan = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .where(PlanRecord.id == plan_id)
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forfait introuvable.",
        )

    normalized: dict[str, dict[str, object]] = {}
    for item in entitlements:
        key = str(item["feature_key"]).strip().lower()
        normalized[key] = {
            "feature_key": key,
            "enabled": bool(item.get("enabled", True)),
            "limit_value": item.get("limit_value"),
        }

    previous = [
        {
            "feature_key": item.feature_key,
            "enabled": item.enabled,
            "limit_value": item.limit_value,
        }
        for item in plan.entitlements
    ]

    existing_by_key = {item.feature_key: item for item in plan.entitlements}
    for key, item in normalized.items():
        existing = existing_by_key.get(key)
        if existing is None:
            db.add(
                PlanEntitlementRecord(
                    plan_id=plan.id,
                    feature_key=key,
                    enabled=bool(item["enabled"]),
                    limit_value=item["limit_value"],
                )
            )
        else:
            existing.enabled = bool(item["enabled"])
            existing.limit_value = item["limit_value"]
            db.add(existing)

    for key, existing in existing_by_key.items():
        if key not in normalized:
            db.delete(existing)

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=None,
        action="plan.entitlements_replaced",
        reason=reason,
        details={
            "plan_id": plan.id,
            "plan_code": plan.code,
            "previous": previous,
            "current": list(normalized.values()),
        },
    )
    db.commit()

    refreshed = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .where(PlanRecord.id == plan.id)
    )
    return _plan_to_admin_read(refreshed)
