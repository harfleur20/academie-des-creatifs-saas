from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import create_access_token
from app.models.entities import (
    BillingInvoiceRecord,
    FormationRecord,
    OrganizationDomainRecord,
    OrganizationMemberRecord,
    OrganizationPlanOverrideRecord,
    OrganizationRecord,
    PlatformAdminAuditRecord,
    PlatformSupportSessionRecord,
    PlanEntitlementRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.schemas.admin import (
    AdminAuditRead,
    AdminDashboardRead,
    AdminCommercialAccessRead,
    AdminOrganizationDetailRead,
    AdminOrganizationRead,
    AdminSupportSessionRead,
    AdminOrganizationSubscriptionRead,
    AdminUsageMetricRead,
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

    role_count_rows = db.execute(
        select(
            OrganizationMemberRecord.organization_id,
            OrganizationMemberRecord.role,
            func.count(OrganizationMemberRecord.id),
        )
        .where(
            OrganizationMemberRecord.organization_id.in_(organization_ids),
            OrganizationMemberRecord.status == "active",
            OrganizationMemberRecord.role.in_(["student", "teacher"]),
        )
        .group_by(
            OrganizationMemberRecord.organization_id,
            OrganizationMemberRecord.role,
        )
    ).all()
    role_counts: dict[tuple[int, str], int] = {
        (organization_id, role): int(count or 0)
        for organization_id, role, count in role_count_rows
    }

    formation_counts = dict(
        db.execute(
            select(
                FormationRecord.organization_id,
                func.count(FormationRecord.id),
            )
            .where(
                FormationRecord.organization_id.in_(organization_ids),
                FormationRecord.status.notin_(["archived", "cancelled"]),
            )
            .group_by(FormationRecord.organization_id)
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
                student_count=int(role_counts.get((organization.id, "student"), 0)),
                teacher_count=int(role_counts.get((organization.id, "teacher"), 0)),
                formation_count=int(formation_counts.get(organization.id, 0)),
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


USAGE_LABELS = {
    "students": "Étudiants",
    "teachers": "Professeurs",
    "active_formations": "Formations",
    "custom_domain": "Domaines personnalisés",
}


def _usage_metrics_for_plan(
    *,
    item: AdminOrganizationRead,
    plan: PlanRecord | None,
) -> list[AdminUsageMetricRead]:
    actual_values = {
        "students": item.student_count,
        "teachers": item.teacher_count,
        "active_formations": item.formation_count,
        "custom_domain": item.verified_domain_count,
    }

    if plan is None:
        return [
            AdminUsageMetricRead(
                feature_key=key,
                label=label,
                current_value=actual_values[key],
                limit_value=None,
                enabled=False,
                over_limit=actual_values[key] > 0,
            )
            for key, label in USAGE_LABELS.items()
        ]

    entitlements = {
        entitlement.feature_key: entitlement
        for entitlement in plan.entitlements
    }

    metrics: list[AdminUsageMetricRead] = []
    for key, label in USAGE_LABELS.items():
        entitlement = entitlements.get(key)
        current_value = actual_values[key]
        enabled = bool(entitlement and entitlement.enabled)
        limit_value = (
            entitlement.limit_value
            if entitlement is not None and entitlement.enabled
            else None
        )
        metrics.append(
            AdminUsageMetricRead(
                feature_key=key,
                label=label,
                current_value=current_value,
                limit_value=limit_value,
                enabled=enabled,
                over_limit=(
                    (not enabled and current_value > 0)
                    or (
                        enabled
                        and limit_value is not None
                        and current_value > limit_value
                    )
                ),
            )
        )
    return metrics


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

    now = _utc_now()
    active_override = db.scalar(
        select(OrganizationPlanOverrideRecord)
        .options(
            selectinload(OrganizationPlanOverrideRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(
            OrganizationPlanOverrideRecord.organization_id == organization.id,
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

    commercial_access = None
    if active_override is not None:
        commercial_access = AdminCommercialAccessRead(
            id=active_override.id,
            plan_id=active_override.plan_id,
            plan_code=active_override.plan.code,
            plan_name=active_override.plan.name,
            starts_at=active_override.starts_at,
            ends_at=active_override.ends_at,
            reason=active_override.reason,
            status=active_override.status,
        )

    effective_plan = active_override.plan if active_override is not None else None
    effective_plan_source = "commercial_access" if effective_plan is not None else None

    if effective_plan is None and item.subscription is not None and item.subscription.status in {"trialing", "active"}:
        effective_plan = db.scalar(
            select(PlanRecord)
            .options(selectinload(PlanRecord.entitlements))
            .where(PlanRecord.id == db.scalar(
                select(SubscriptionRecord.plan_id).where(
                    SubscriptionRecord.id == item.subscription.id
                )
            ))
        )
        effective_plan_source = "subscription" if effective_plan is not None else None

    return AdminOrganizationDetailRead(
        **item.model_dump(),
        commercial_access=commercial_access,
        effective_plan_name=effective_plan.name if effective_plan is not None else None,
        effective_plan_source=effective_plan_source,
        usage_metrics=_usage_metrics_for_plan(item=item, plan=effective_plan),
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
    db.expire(plan, ["entitlements"])

    refreshed = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .execution_options(populate_existing=True)
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
    db.expire(plan, ["entitlements"])

    refreshed = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .execution_options(populate_existing=True)
        .where(PlanRecord.id == plan.id)
    )
    return _plan_to_admin_read(refreshed)



def grant_commercial_access(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int,
    plan_id: int,
    days: int,
    reason: str,
) -> AdminOrganizationDetailRead:
    organization = _get_organization_or_404(db, organization_id)
    plan = db.get(PlanRecord, plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce forfait n'est pas disponible pour une dérogation.",
        )

    now = _utc_now()
    existing = list(
        db.scalars(
            select(OrganizationPlanOverrideRecord).where(
                OrganizationPlanOverrideRecord.organization_id == organization.id,
                OrganizationPlanOverrideRecord.status == "active",
                OrganizationPlanOverrideRecord.ends_at > now,
            )
        ).all()
    )
    for item in existing:
        item.status = "cancelled"
        item.cancelled_at = now
        db.add(item)

    override = OrganizationPlanOverrideRecord(
        organization_id=organization.id,
        plan_id=plan.id,
        granted_by_user_id=actor.id,
        status="active",
        reason=reason.strip(),
        starts_at=now,
        ends_at=now + timedelta(days=days),
        cancelled_at=None,
    )
    db.add(override)
    db.flush()

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=organization.id,
        action="commercial_access.granted",
        reason=reason,
        details={
            "override_id": override.id,
            "plan_id": plan.id,
            "plan_code": plan.code,
            "days": days,
            "starts_at": override.starts_at.isoformat(),
            "ends_at": override.ends_at.isoformat(),
        },
    )
    db.commit()
    return get_admin_organization(db, organization.id)


def cancel_commercial_access(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int,
    reason: str,
) -> AdminOrganizationDetailRead:
    organization = _get_organization_or_404(db, organization_id)
    now = _utc_now()
    override = db.scalar(
        select(OrganizationPlanOverrideRecord)
        .where(
            OrganizationPlanOverrideRecord.organization_id == organization.id,
            OrganizationPlanOverrideRecord.status == "active",
            OrganizationPlanOverrideRecord.ends_at > now,
        )
        .order_by(
            OrganizationPlanOverrideRecord.created_at.desc(),
            OrganizationPlanOverrideRecord.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )
    if override is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun accès commercial temporaire actif.",
        )

    override.status = "cancelled"
    override.cancelled_at = now
    db.add(override)

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=organization.id,
        action="commercial_access.cancelled",
        reason=reason,
        details={
            "override_id": override.id,
            "plan_id": override.plan_id,
            "scheduled_end": override.ends_at.isoformat(),
            "cancelled_at": now.isoformat(),
        },
    )
    db.commit()
    return get_admin_organization(db, organization.id)


def start_support_session(
    db: Session,
    *,
    actor: UserRecord,
    organization_id: int,
    reason: str,
    minutes: int = 30,
) -> AdminSupportSessionRead:
    organization = _get_organization_or_404(db, organization_id)
    if not organization.is_active or organization.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Réactivez l'école avant d'ouvrir une session support.",
        )

    now = _utc_now()
    open_sessions = list(
        db.scalars(
            select(PlatformSupportSessionRecord).where(
                PlatformSupportSessionRecord.actor_user_id == actor.id,
                PlatformSupportSessionRecord.ended_at.is_(None),
                PlatformSupportSessionRecord.expires_at > now,
            )
        ).all()
    )
    for item in open_sessions:
        item.ended_at = now
        db.add(item)

    support_session = PlatformSupportSessionRecord(
        actor_user_id=actor.id,
        organization_id=organization.id,
        reason=reason.strip(),
        expires_at=now + timedelta(minutes=minutes),
        ended_at=None,
    )
    db.add(support_session)
    db.flush()

    _write_admin_audit(
        db,
        actor=actor,
        organization_id=organization.id,
        action="support.started",
        reason=reason,
        details={
            "support_session_id": support_session.id,
            "expires_at": support_session.expires_at.isoformat(),
            "mode": "read_only",
        },
    )
    db.commit()

    token = create_access_token(
        actor.id,
        minutes=minutes,
        additional_claims={
            "support_session_id": support_session.id,
            "support_org_id": organization.id,
            "support_mode": "read_only",
        },
    )
    return AdminSupportSessionRead(
        session_id=support_session.id,
        organization_id=organization.id,
        organization_name=organization.name,
        access_token=token,
        expires_at=support_session.expires_at,
    )


def end_support_session(
    db: Session,
    *,
    actor: UserRecord,
    support_session: PlatformSupportSessionRecord,
) -> None:
    if support_session.ended_at is not None:
        return

    now = _utc_now()
    support_session.ended_at = now
    db.add(support_session)
    _write_admin_audit(
        db,
        actor=actor,
        organization_id=support_session.organization_id,
        action="support.ended",
        reason="Fin de la session support.",
        details={
            "support_session_id": support_session.id,
            "ended_at": now.isoformat(),
        },
    )
    db.commit()
