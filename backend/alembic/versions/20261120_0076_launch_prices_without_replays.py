"""Launch prices, without replays or transcription until they work (docs/FORFAITS.md).

- Starter costs 10 000 FCFA a month, Pro 25 000 FCFA, Business 45 000 FCFA; -20 % a year.
- Replays, their retention and transcription leave every plan, with their two add-ons. Their
  limits stay in place, switched off: the administration turns them back on when they work.
- Pro no longer promises replays in its description.

Revision ID: 20261120_0076
Revises: 20261119_0075
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision: str = "20261120_0076"
down_revision: str | None = "20261119_0075"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# code: (monthly, annual, description or None to leave it)
PRICES = {
    "starter": (10_000, 96_000, None),
    "pro": (25_000, 240_000, "Pour les écoles qui grandissent : plus de live, votre propre domaine et des statistiques."),
    "business": (45_000, 432_000, None),
}
PREVIOUS_PRICES = {
    "starter": (15_000, 144_000, None),
    "pro": (30_000, 288_000, "Pour les écoles qui grandissent : plus de live, des replays et des statistiques."),
    "business": (65_000, 624_000, None),
}
NOT_YET = ("replays", "replay_retention_days", "transcription")
NOT_YET_ADDONS = ("live_replays", "live_transcription")


def _prices(grid: dict) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for code, (monthly, annual, description) in grid.items():
        values = {"code": code, "monthly": monthly, "annual": annual, "now": now}
        sql = "UPDATE plans SET monthly_price_cents = :monthly, annual_price_cents = :annual, updated_at = :now"
        if description is not None:
            sql += ", description = :description"
            values["description"] = description
        bind.execute(sa.text(sql + " WHERE code = :code"), values)


def _not_yet(enabled: bool, addon_status: str) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    bind.execute(
        sa.text("UPDATE plan_entitlements SET enabled = :enabled, updated_at = :now WHERE feature_key IN :keys")
        .bindparams(sa.bindparam("keys", expanding=True)),
        {"enabled": enabled, "now": now, "keys": list(NOT_YET)},
    )
    bind.execute(
        sa.text("UPDATE addons SET status = :status, updated_at = :now WHERE code IN :codes")
        .bindparams(sa.bindparam("codes", expanding=True)),
        {"status": addon_status, "now": now, "codes": list(NOT_YET_ADDONS)},
    )


def upgrade() -> None:
    _prices(PRICES)
    _not_yet(False, "inactive")


def downgrade() -> None:
    _prices(PREVIOUS_PRICES)
    _not_yet(True, "coming_soon")
