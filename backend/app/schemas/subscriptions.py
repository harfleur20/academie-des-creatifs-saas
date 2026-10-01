from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
