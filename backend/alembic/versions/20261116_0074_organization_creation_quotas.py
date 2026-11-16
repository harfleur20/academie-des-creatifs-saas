"""Add account school quotas to the subscription plans."""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20261116_0074"
down_revision = "20261116_0073"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


PLAN_LIMITS = {
    "decouverte": 1,
    "starter": 1,
    "pro": 2,
    "business": 5,
}


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for code, limit in PLAN_LIMITS.items():
        plan = bind.execute(
            sa.text("SELECT id FROM plans WHERE code = :code"), {"code": code}
        ).first()
        if plan is None:
            continue
        bind.execute(
            sa.text(
                "DELETE FROM plan_entitlements "
                "WHERE plan_id = :plan_id AND feature_key = 'organizations'"
            ),
            {"plan_id": plan.id},
        )
        bind.execute(
            sa.text(
                "INSERT INTO plan_entitlements "
                "(plan_id, feature_key, enabled, limit_value, created_at, updated_at) "
                "VALUES (:plan_id, 'organizations', TRUE, :limit_value, :now, :now)"
            ),
            {"plan_id": plan.id, "limit_value": limit, "now": now},
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM plan_entitlements WHERE feature_key = 'organizations'"))
