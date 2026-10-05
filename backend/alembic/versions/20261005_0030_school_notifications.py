"""Store school-scoped in-app notifications.

Revision ID: 20261005_0030
Revises: 20261005_0029
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0030"
down_revision = "20261005_0029"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "school_notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_key", sa.String(160), nullable=False),
        sa.Column("audience", sa.String(16), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("tone", sa.String(16), nullable=False),
        sa.Column("action_label", sa.String(80), nullable=True),
        sa.Column("action_path", sa.String(512), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", "event_key", name="uq_school_notifications_event"),
    )
    op.create_index("ix_school_notifications_organization_id", "school_notifications", ["organization_id"])
    op.create_index("ix_school_notifications_user_id", "school_notifications", ["user_id"])
    op.create_index("ix_school_notifications_recipient", "school_notifications", ["organization_id", "user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_school_notifications_recipient", table_name="school_notifications")
    op.drop_index("ix_school_notifications_user_id", table_name="school_notifications")
    op.drop_index("ix_school_notifications_organization_id", table_name="school_notifications")
    op.drop_table("school_notifications")
