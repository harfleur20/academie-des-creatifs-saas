from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    BillingInvoiceRecord,
    OrganizationDomainRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.schemas.admin import (
    AdminDashboardRead,
    AdminOrganizationRead,
    AdminOrganizationSubscriptionRead,
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
