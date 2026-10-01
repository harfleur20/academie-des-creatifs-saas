from datetime import datetime

from pydantic import BaseModel, Field


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


class AdminEntitlementUpdate(BaseModel):
    feature_key: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$",
    )
    enabled: bool = True
    limit_value: int | None = Field(default=None, ge=0)


class AdminPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    monthly_price_cents: int | None = Field(default=None, ge=0)
    annual_price_cents: int | None = Field(default=None, ge=0)
    trial_days: int | None = Field(default=None, ge=0, le=365)
    is_public: bool | None = None
    is_active: bool | None = None


class AdminPlanRead(BaseModel):
    id: int
    code: str
    name: str
    description: str
    currency: str
    monthly_price_cents: int | None
    annual_price_cents: int | None
    trial_days: int
    is_public: bool
    is_active: bool
    entitlements: list[AdminEntitlementUpdate]


class AdminPlanEntitlementsPayload(BaseModel):
    entitlements: list[AdminEntitlementUpdate]


class AdminCommercialAccessPayload(BaseModel):
    plan_id: int = Field(gt=0)
    days: int = Field(ge=1, le=365)
    reason: str = Field(min_length=3, max_length=500)


class AdminCommercialAccessRead(BaseModel):
    id: int
    plan_id: int
    plan_code: str
    plan_name: str
    starts_at: datetime
    ends_at: datetime
    reason: str
    status: str


class AdminOrganizationDetailRead(AdminOrganizationRead):
    commercial_access: AdminCommercialAccessRead | None = None
    audit_logs: list[AdminAuditRead]


class AdminSupportSessionPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminSupportSessionRead(BaseModel):
    session_id: int
    organization_id: int
    organization_name: str
    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime
