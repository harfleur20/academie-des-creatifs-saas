from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminRevenueTotal(BaseModel):
    currency: str
    amount: int
    paid_invoices: int


class AdminDashboardRead(BaseModel):
    organizations_total: int
    organizations_active: int
    organizations_suspended: int
    subscriptions_trialing: int
    subscriptions_active: int
    subscriptions_past_due: int
    subscriptions_suspended: int
    users_total: int
    revenue: list[AdminRevenueTotal]


class AdminOrganizationSubscriptionRead(BaseModel):
    id: int
    status: str
    billing_interval: str
    plan_code: str
    plan_name: str
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    grace_period_ends_at: datetime | None
    provider: str | None


class AdminOrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    subdomain: str | None
    status: str
    is_active: bool
    contact_email: str | None
    logo_url: str | None
    created_at: datetime
    owner_name: str | None
    owner_email: str | None
    member_count: int
    verified_domain_count: int
    subscription: AdminOrganizationSubscriptionRead | None



class AdminActionPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminExtendTrialPayload(AdminActionPayload):
    days: int = Field(ge=1, le=365)


class AdminAuditRead(BaseModel):
    id: int
    action: str
    reason: str
    details: str | None
    actor_user_id: int | None
    actor_name: str | None
    actor_email: str | None
    created_at: datetime


class AdminOrganizationDetailRead(AdminOrganizationRead):
    audit_logs: list[AdminAuditRead]
