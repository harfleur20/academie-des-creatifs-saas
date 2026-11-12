from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RevenueSummaryRead(BaseModel):
    currency: str
    gross_cents: int
    commission_cents: int
    earned_cents: int
    paid_out_cents: int
    pending_payout_cents: int
    available_cents: int
    commission_bps: int
    min_payout_cents: int


class LedgerEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    gross_cents: int
    commission_bps: int
    commission_cents: int
    amount_cents: int
    currency: str
    description: str
    occurred_at: datetime


class PayoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_cents: int
    currency: str
    method: str
    destination: str
    account_name: str
    status: str
    requested_at: datetime
    processed_at: datetime | None
    transfer_reference: str | None
    note: str | None


class PayoutRequest(BaseModel):
    amount_cents: int = Field(gt=0)
    method: Literal["mobile_money", "bank"]
    destination: str = Field(min_length=3, max_length=255)
    account_name: str = Field(min_length=2, max_length=180)


class AdminPayoutRead(PayoutRead):
    organization_id: int
    organization_name: str


class AdminPayoutProcess(BaseModel):
    transfer_reference: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=2000)


class AdminAddonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    unit_price_cents: int | None = Field(default=None, ge=0)
    status: Literal["active", "coming_soon", "inactive"] | None = None
    plan_codes: list[str] | None = None
