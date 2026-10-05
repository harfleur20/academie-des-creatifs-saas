"""Add school-scoped conversations and messages.

Revision ID: 20261005_0037
Revises: 20261005_0036
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0037"
down_revision = "20261005_0036"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "school_message_threads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_school_message_threads_organization_id", "school_message_threads", ["organization_id"])
    op.create_table(
        "school_message_participants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("school_message_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_snapshot", sa.String(32), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("thread_id", "user_id", name="uq_school_message_participant"),
    )
    for column in ("organization_id", "thread_id", "user_id"):
        op.create_index(f"ix_school_message_participants_{column}", "school_message_participants", [column])
    op.create_table(
        "school_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("school_message_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("organization_id", "thread_id", "sender_user_id"):
        op.create_index(f"ix_school_messages_{column}", "school_messages", [column])


def downgrade() -> None:
    for column in ("sender_user_id", "thread_id", "organization_id"):
        op.drop_index(f"ix_school_messages_{column}", table_name="school_messages")
    op.drop_table("school_messages")
    for column in ("user_id", "thread_id", "organization_id"):
        op.drop_index(f"ix_school_message_participants_{column}", table_name="school_message_participants")
    op.drop_table("school_message_participants")
    op.drop_index("ix_school_message_threads_organization_id", table_name="school_message_threads")
    op.drop_table("school_message_threads")
