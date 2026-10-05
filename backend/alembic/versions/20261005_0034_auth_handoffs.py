"""Add one-time authentication handoffs for verified custom domains.

Revision ID: 20261005_0034
Revises: 20261005_0033
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0034"
down_revision = "20261005_0033"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_handoffs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("target_host", sa.String(length=253), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_auth_handoffs_token_hash"),
    )
    op.create_index("ix_auth_handoffs_token_hash", "auth_handoffs", ["token_hash"], unique=True)
    op.create_index("ix_auth_handoffs_user_id", "auth_handoffs", ["user_id"])
    op.create_index("ix_auth_handoffs_organization_id", "auth_handoffs", ["organization_id"])
    op.create_index("ix_auth_handoffs_target_host", "auth_handoffs", ["target_host"])
    op.create_index("ix_auth_handoffs_expires_at", "auth_handoffs", ["expires_at"])
    op.create_index("ix_auth_handoffs_target_expiry", "auth_handoffs", ["target_host", "expires_at"])


def downgrade() -> None:
    op.drop_table("auth_handoffs")
