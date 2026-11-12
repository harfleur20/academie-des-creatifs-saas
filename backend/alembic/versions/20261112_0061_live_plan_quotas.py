"""Include live classes in every public plan and set per-room student limits.

Revision ID: 20261112_0061
Revises: 20261112_0060
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20261112_0061"
down_revision = "20261112_0060"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

PLAN_LIVE_LIMITS = {
    "starter": (
        "Pour les formateurs et les petites écoles, avec des lives jusqu’à 10 étudiants.",
        True,
        10,
    ),
    "pro": (
        "Pour les écoles qui accueillent jusqu’à 50 étudiants par live.",
        True,
        50,
    ),
    "business": (
        "Pour les écoles avec plusieurs équipes et des lives jusqu’à 100 étudiants.",
        True,
        100,
    ),
}

PREVIOUS_PLAN_VALUES = {
    "starter": (
        "Pour les formateurs et les petites écoles, en ligne et en présentiel.",
        False,
        None,
    ),
    "pro": (
        "Pour les écoles qui donnent des cours en live, avec leur propre domaine.",
        True,
        None,
    ),
    "business": (
        "Pour les écoles avec plusieurs équipes et beaucoup d'étudiants.",
        True,
        None,
    ),
}


def _update_plans(values: dict[str, tuple[str, bool, int | None]]) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for code, (description, enabled, limit) in values.items():
        plan = bind.execute(
            sa.text("SELECT id FROM plans WHERE code = :code"),
            {"code": code},
        ).first()
        if plan is None:
            continue
        entitlement = bind.execute(
            sa.text("SELECT id FROM plan_entitlements WHERE plan_id = :plan_id AND feature_key = 'live'"),
            {"plan_id": plan.id},
        ).first()
        if entitlement is None:
            bind.execute(
                sa.text(
                    "INSERT INTO plan_entitlements "
                    "(plan_id, feature_key, enabled, limit_value, created_at, updated_at) "
                    "VALUES (:plan_id, 'live', :enabled, :limit, :now, :now)"
                ),
                {"plan_id": plan.id, "enabled": enabled, "limit": limit, "now": now},
            )
        else:
            bind.execute(
                sa.text(
                    "UPDATE plan_entitlements SET enabled = :enabled, limit_value = :limit, updated_at = :now "
                    "WHERE id = :id"
                ),
                {"enabled": enabled, "limit": limit, "now": now, "id": entitlement.id},
            )
        bind.execute(
            sa.text("UPDATE plans SET description = :description, updated_at = :now WHERE id = :id"),
            {"description": description, "now": now, "id": plan.id},
        )


def upgrade() -> None:
    _update_plans(PLAN_LIVE_LIMITS)


def downgrade() -> None:
    _update_plans(PREVIOUS_PLAN_VALUES)
