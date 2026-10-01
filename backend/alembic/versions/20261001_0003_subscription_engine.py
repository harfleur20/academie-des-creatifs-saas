"""subscription engine

Revision ID: 20261001_0003
Revises: 20261001_0002
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0003"
down_revision: str | None = "20261001_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    plans = op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=True),
        sa.Column("annual_price_cents", sa.Integer(), nullable=True),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_plans_code", "plans", ["code"])

    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_key", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plan_id", "feature_key", name="uq_plan_entitlements_plan_feature"),
    )
    op.create_index("ix_plan_entitlements_plan_id", "plan_entitlements", ["plan_id"])
    op.create_index("ix_plan_entitlements_feature_key", "plan_entitlements", ["feature_key"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="trialing"),
        sa.Column("billing_interval", sa.String(length=16), nullable=False, server_default="monthly"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=180), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index("ix_subscriptions_org_status", "subscriptions", ["organization_id", "status"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("window_key", sa.String(length=40), nullable=False, server_default="lifetime"),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "metric_key", "window_key", name="uq_usage_counter_org_metric_window"),
    )
    op.create_index("ix_usage_counters_organization_id", "usage_counters", ["organization_id"])
    op.create_index("ix_usage_counters_metric_key", "usage_counters", ["metric_key"])

    op.bulk_insert(
        plans,
        [
            {
                "code": "starter",
                "name": "Starter",
                "description": "Plan de démarrage configurable.",
                "currency": "EUR",
                "monthly_price_cents": None,
                "annual_price_cents": None,
                "trial_days": 14,
                "is_public": True,
                "is_active": True,
            },
            {
                "code": "pro",
                "name": "Pro",
                "description": "Plan avancé configurable.",
                "currency": "EUR",
                "monthly_price_cents": None,
                "annual_price_cents": None,
                "trial_days": 14,
                "is_public": True,
                "is_active": True,
            },
            {
                "code": "business",
                "name": "Business",
                "description": "Plan pour les structures à besoins avancés.",
                "currency": "EUR",
                "monthly_price_cents": None,
                "annual_price_cents": None,
                "trial_days": 14,
                "is_public": True,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_table("plans")
