"""Live classes in every plan, sized for good classes, and lower prices (docs/FORFAITS.md).

- Découverte gets live classes to try them: 10 students, one at a time, 6 hours a month
  (live_hours).
- Every paid plan publishes formations without limit; the extra-formation add-on stops.
- Students per live class: 10, 15, 30 and 30. A school with more students opens another
  session. Live classes at once: 1, 2, 5 and 10.
- A live class lasts 4 hours at most in every plan (live_class_hours).
- Pro costs 30 000 FCFA a month, Business 65 000 FCFA, -20 % a year as before.

Revision ID: 20261114_0066
Revises: 20261113_0065
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20261114_0066"
down_revision = "20261113_0065"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

PLANS = {
    # code: (name, description, monthly, annual, commission in basis points, trial days, entitlements)
    "decouverte": (
        "Découverte",
        "Pour lancer votre école sans abonnement : vous ne payez que lorsque vous vendez.",
        0, 0, 1_000, 0,
        [("students", True, None), ("teachers", True, 1), ("active_formations", True, 1),
         ("live", True, 10), ("live_rooms", True, 1), ("live_hours", True, 6), ("live_class_hours", True, 4),
         ("custom_domain", False, None)],
    ),
    "starter": (
        "Starter",
        "Pour les formateurs et les petites écoles qui lancent leurs cours en live.",
        15_000, 144_000, 800, 14,
        [("students", True, None), ("teachers", True, 2), ("active_formations", True, None),
         ("live", True, 15), ("live_rooms", True, 2), ("live_class_hours", True, 4),
         ("replays", True, 2), ("replay_retention_days", True, 0), ("custom_domain", False, None)],
    ),
    "pro": (
        "Pro",
        "Pour les écoles qui grandissent : plus de live, des replays et des statistiques.",
        30_000, 288_000, 600, 14,
        [("students", True, None), ("teachers", True, 10), ("active_formations", True, None),
         ("live", True, 30), ("live_rooms", True, 5), ("live_class_hours", True, 4),
         ("replays", True, 15), ("replay_retention_days", True, 30), ("transcription", True, 5),
         ("advanced_stats", True, None), ("custom_domain", True, None), ("whatsapp_support", True, None)],
    ),
    "business": (
        "Business",
        "Pour les grandes écoles, avec plus de lives et leur seule marque.",
        65_000, 624_000, 400, 14,
        [("students", True, None), ("teachers", True, None), ("active_formations", True, None),
         ("live", True, 30), ("live_rooms", True, 10), ("live_class_hours", True, 4),
         ("replays", True, 50), ("replay_retention_days", True, 180), ("transcription", True, 50),
         ("advanced_stats", True, None), ("custom_domain", True, None), ("white_label", True, None),
         ("whatsapp_support", True, None), ("priority_support", True, None)],
    ),
}

# What 0062 left, to go back to.
PREVIOUS_PLANS = {
    "decouverte": (
        "Découverte",
        "Pour lancer votre école sans abonnement : vous ne payez que lorsque vous vendez.",
        0, 0, 1_000, 0,
        [("students", True, None), ("teachers", True, 1), ("active_formations", True, 1),
         ("live", False, None), ("custom_domain", False, None)],
    ),
    "starter": (
        "Starter",
        "Pour les formateurs et les petites écoles qui lancent leurs cours en live.",
        15_000, 144_000, 800, 14,
        [("students", True, None), ("teachers", True, 2), ("active_formations", True, 3),
         ("live", True, 10), ("live_rooms", True, 1), ("replays", True, 2), ("replay_retention_days", True, 0),
         ("custom_domain", False, None)],
    ),
    "pro": (
        "Pro",
        "Pour les écoles qui grandissent : plus de live, des replays et des statistiques.",
        35_000, 336_000, 600, 14,
        [("students", True, None), ("teachers", True, 10), ("active_formations", True, None),
         ("live", True, 50), ("live_rooms", True, 2), ("replays", True, 15), ("replay_retention_days", True, 30),
         ("transcription", True, 5), ("advanced_stats", True, None), ("custom_domain", True, None),
         ("whatsapp_support", True, None)],
    ),
    "business": (
        "Business",
        "Pour les grandes écoles, avec plus de lives et leur seule marque.",
        75_000, 720_000, 400, 14,
        [("students", True, None), ("teachers", True, None), ("active_formations", True, None),
         ("live", True, 100), ("live_rooms", True, 5), ("replays", True, 50), ("replay_retention_days", True, 180),
         ("transcription", True, 50), ("advanced_stats", True, None), ("custom_domain", True, None),
         ("white_label", True, None), ("whatsapp_support", True, None), ("priority_support", True, None)],
    ),
}


def _write_plans(grid: dict) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for code, (name, description, monthly, annual, commission, trial_days, entitlements) in grid.items():
        plan = bind.execute(sa.text("SELECT id FROM plans WHERE code = :code"), {"code": code}).first()
        if plan is None:
            continue  # 0062 created the grid; an administrator may have removed a plan since.
        bind.execute(sa.text(
            "UPDATE plans SET name = :name, description = :description, monthly_price_cents = :monthly, "
            "annual_price_cents = :annual, sales_commission_bps = :commission, trial_days = :trial_days, "
            "updated_at = :now WHERE id = :id"
        ), {"name": name, "description": description, "monthly": monthly, "annual": annual,
            "commission": commission, "trial_days": trial_days, "now": now, "id": plan.id})
        bind.execute(sa.text("DELETE FROM plan_entitlements WHERE plan_id = :id"), {"id": plan.id})
        for feature_key, enabled, limit in entitlements:
            bind.execute(sa.text(
                "INSERT INTO plan_entitlements (plan_id, feature_key, enabled, limit_value, created_at, updated_at) "
                "VALUES (:plan_id, :feature_key, :enabled, :limit, :now, :now)"
            ), {"plan_id": plan.id, "feature_key": feature_key, "enabled": enabled, "limit": limit, "now": now})


def _formation_addon(status: str) -> None:
    op.get_bind().execute(sa.text("UPDATE addons SET status = :status, updated_at = :now WHERE code = 'extra_formation'"),
                          {"status": status, "now": datetime.now(UTC)})


def upgrade() -> None:
    _write_plans(PLANS)
    _formation_addon("inactive")


def downgrade() -> None:
    _write_plans(PREVIOUS_PLANS)
    _formation_addon("active")
