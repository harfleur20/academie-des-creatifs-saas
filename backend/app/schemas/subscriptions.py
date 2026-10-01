from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanEntitlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feature_key: str
    enabled: bool
    limit_value: int | None


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str
    currency: str
    monthly_price_cents: int | None
    annual_price_cents: int | None
    trial_days: int
    is_public: bool
    entitlements: list[PlanEntitlementRead]


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    status: str
    billing_interval: str
    started_at: datetime
    trial_ends_at: datetime | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    provider: str | None
    plan: PlanRead


class EntitlementCheckRead(BaseModel):
    feature_key: str
    enabled: bool
    limit_value: int | None
    current_value: int | None
    allowed: bool


class PaymentModeRead(BaseModel):
    mode: str
    demo_enabled: bool
    tara_configured: bool


class DemoCheckoutCreate(BaseModel):
    plan_code: str = Field(min_length=1, max_length=64)
    billing_interval: str = Field(pattern=r"^(monthly|annual)$")


class DemoPaymentAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    plan_id: int
    billing_interval: str
    provider: str
    provider_reference: str
    status: str
    amount_cents: int
    currency: str
    confirmed_at: datetime | None
    checkout_url: str | None
    provider_transaction_id: str | None
    activated_subscription_id: int | None
    failure_reason: str | None
    plan: PlanRead


class DemoPaymentConfirmationRead(BaseModel):
    payment: DemoPaymentAttemptRead
    subscription: SubscriptionRead


class TaraCheckoutCreate(BaseModel):
    plan_code: str = Field(min_length=1, max_length=64)
    billing_interval: str = Field(pattern=r"^(monthly|annual)$")


class TaraCheckoutRead(BaseModel):
    payment: DemoPaymentAttemptRead
    checkout_url: str


class TaraReconcileRead(BaseModel):
    payment: DemoPaymentAttemptRead
    subscription: SubscriptionRead | None
    status: str
