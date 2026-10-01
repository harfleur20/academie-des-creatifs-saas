"""commercial plan overrides and support sessions

Revision ID: 20261002_0010
Revises: 20261002_0009
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0010"
down_revision: str | None = "20261002_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_plan_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("granted_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organization_plan_overrides_organization_id", "organization_plan_overrides", ["organization_id"])
    op.create_index("ix_organization_plan_overrides_plan_id", "organization_plan_overrides", ["plan_id"])
    op.create_index("ix_organization_plan_overrides_granted_by_user_id", "organization_plan_overrides", ["granted_by_user_id"])
    op.create_index("ix_organization_plan_overrides_status", "organization_plan_overrides", ["status"])
    op.create_index("ix_organization_plan_overrides_ends_at", "organization_plan_overrides", ["ends_at"])
    op.create_index("ix_organization_plan_overrides_org_status_end", "organization_plan_overrides", ["organization_id", "status", "ends_at"])

    op.create_table(
        "platform_support_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_platform_support_sessions_actor_user_id", "platform_support_sessions", ["actor_user_id"])
    op.create_index("ix_platform_support_sessions_organization_id", "platform_support_sessions", ["organization_id"])
    op.create_index("ix_platform_support_sessions_expires_at", "platform_support_sessions", ["expires_at"])
    op.create_index("ix_platform_support_sessions_actor_end", "platform_support_sessions", ["actor_user_id", "ended_at"])
    op.create_index("ix_platform_support_sessions_org_expiry", "platform_support_sessions", ["organization_id", "expires_at"])


def downgrade() -> None:
    op.drop_table("platform_support_sessions")
    op.drop_table("organization_plan_overrides")
