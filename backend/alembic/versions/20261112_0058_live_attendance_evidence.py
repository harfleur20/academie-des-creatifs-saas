"""Evidence that a student followed a live class: time in the room and roll calls.

Revision ID: 20261112_0058
Revises: 20261112_0057
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261112_0058"
down_revision = "20261112_0057"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("live_room_presences") as batch_op:
        batch_op.add_column(sa.Column("seconds_in_room", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "live_roll_calls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_day_id", sa.Integer(), sa.ForeignKey("session_course_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_live_roll_calls_organization_id", "live_roll_calls", ["organization_id"])
    op.create_index("ix_live_roll_calls_course_day_id", "live_roll_calls", ["course_day_id"])
    op.create_table(
        "live_roll_call_answers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("roll_call_id", sa.Integer(), sa.ForeignKey("live_roll_calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("roll_call_id", "user_id", name="uq_live_roll_call_answers_call_user"),
    )
    op.create_index("ix_live_roll_call_answers_organization_id", "live_roll_call_answers", ["organization_id"])
    op.create_index("ix_live_roll_call_answers_roll_call_id", "live_roll_call_answers", ["roll_call_id"])


def downgrade() -> None:
    op.drop_index("ix_live_roll_call_answers_roll_call_id", table_name="live_roll_call_answers")
    op.drop_index("ix_live_roll_call_answers_organization_id", table_name="live_roll_call_answers")
    op.drop_table("live_roll_call_answers")
    op.drop_index("ix_live_roll_calls_course_day_id", table_name="live_roll_calls")
    op.drop_index("ix_live_roll_calls_organization_id", table_name="live_roll_calls")
    op.drop_table("live_roll_calls")
    with op.batch_alter_table("live_room_presences") as batch_op:
        batch_op.drop_column("seconds_in_room")
