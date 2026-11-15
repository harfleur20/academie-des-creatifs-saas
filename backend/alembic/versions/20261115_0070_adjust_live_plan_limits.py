"""Adjust live class duration, replay, transcription, and class-size quotas."""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20261115_0070"
down_revision = "20261115_0069"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


LIMITS = {
    "decouverte": {"live_class_hours": 2},
    "starter": {"live_class_hours": 3},
    "pro": {"live": 25, "live_class_hours": 4},
    "business": {"live_class_hours": 4, "replays": 25, "transcription": 25},
}

PREVIOUS_LIMITS = {
    "decouverte": {"live_class_hours": 4},
    "starter": {"live_class_hours": 4},
    "pro": {"live": 30, "live_class_hours": 4},
    "business": {"live_class_hours": 4, "replays": 50, "transcription": 50},
}


def _set_limits(limits: dict[str, dict[str, int]]) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    for plan_code, features in limits.items():
        plan = bind.execute(
            sa.text("SELECT id FROM plans WHERE code = :code"), {"code": plan_code}
        ).first()
        if plan is None:
            continue

        for feature_key, limit_value in features.items():
            entitlement = bind.execute(
                sa.text(
                    "SELECT id FROM plan_entitlements "
                    "WHERE plan_id = :plan_id AND feature_key = :feature_key"
                ),
                {"plan_id": plan.id, "feature_key": feature_key},
            ).first()
            if entitlement is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO plan_entitlements "
                        "(plan_id, feature_key, enabled, limit_value, created_at, updated_at) "
                        "VALUES (:plan_id, :feature_key, TRUE, :limit_value, :now, :now)"
                    ),
                    {"plan_id": plan.id, "feature_key": feature_key, "limit_value": limit_value, "now": now},
                )
            else:
                bind.execute(
                    sa.text(
                        "UPDATE plan_entitlements SET enabled = TRUE, limit_value = :limit_value, "
                        "updated_at = :now WHERE plan_id = :plan_id AND feature_key = :feature_key"
                    ),
                    {
                        "plan_id": plan.id,
                        "feature_key": feature_key,
                        "limit_value": limit_value,
                        "now": now,
                    },
                )


def upgrade() -> None:
    _set_limits(LIMITS)


def downgrade() -> None:
    _set_limits(PREVIOUS_LIMITS)
