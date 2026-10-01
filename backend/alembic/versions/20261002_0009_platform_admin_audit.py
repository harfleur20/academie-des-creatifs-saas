"""platform admin audit logs

Revision ID: 20261002_0009
Revises: 20261002_0008
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0009"
down_revision: str | None = "20261002_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_admin_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_platform_admin_audit_actor_user_id",
        "platform_admin_audit_logs",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_platform_admin_audit_organization_id",
        "platform_admin_audit_logs",
        ["organization_id"],
    )
    op.create_index(
        "ix_platform_admin_audit_action",
        "platform_admin_audit_logs",
        ["action"],
    )
    op.create_index(
        "ix_platform_admin_audit_org_created",
        "platform_admin_audit_logs",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_platform_admin_audit_actor_created",
        "platform_admin_audit_logs",
        ["actor_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("platform_admin_audit_logs")
