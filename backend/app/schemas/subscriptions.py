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
    # Share of each student payment the platform keeps, in basis points (800 = 8 %).
    sales_commission_bps: int = 800
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
    grace_period_ends_at: datetime | None
    suspended_at: datetime | None
    cancel_at_period_end: bool
    cancelled_at: datetime | None
    provider: str | None
    chosen_plan_code: str | None = None
    chosen_billing_interval: str | None = None
    plan: PlanRead


class BillingInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    subscription_id: int | None
    plan_id: int
    payment_attempt_id: int | None
    invoice_number: str
    status: str
    amount_cents: int
    lines: list["BillingLineRead"] | None = None
    currency: str
    billing_interval: str
    period_start: datetime
    period_end: datetime
    issued_at: datetime
    due_at: datetime | None
    paid_at: datetime | None
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


class BillingLifecycleRunRead(BaseModel):
    processed: int
    transitioned: int


class BillingLineRead(BaseModel):
    label: str
    quantity: int
    unit_amount_cents: int
    amount_cents: int


class AddonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    description: str
    feature_key: str | None
    unit_label: str
    unit_price_cents: int | None
    currency: str
    status: str
    plan_codes: list[str]


class UsageMetricRead(BaseModel):
    feature_key: str
    label: str
    current: int | float
    limit: int | None  # None: unlimited
    extra: int
    unit_price_cents: int | None
    extra_amount_cents: int


class BillingQuoteRead(BaseModel):
    currency: str
    lines: list[BillingLineRead]
    total_cents: int


class BillingUsageRead(BaseModel):
    """What the school uses against its plan, and what its next payment would be."""

    plan_code: str | None
    plan_name: str | None
    billing_interval: str
    commission_bps: int
    live_included: bool
    custom_domain_included: bool
    metrics: list[UsageMetricRead]
    next_payment: BillingQuoteRead | None


BillingInvoiceRead.model_rebuild()
