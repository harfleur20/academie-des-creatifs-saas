"""Students' devices in live classes: one device at a time and attendance from room entries, as on the mother site.

Revision ID: 20261112_0057
Revises: 20261108_0056
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261112_0057"
down_revision = "20261108_0056"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_room_presences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_day_id", sa.Integer(), sa.ForeignKey("session_course_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("device_label", sa.String(160), nullable=True),
        sa.Column("first_joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("course_day_id", "user_id", "device_id", name="uq_live_room_presences_day_user_device"),
    )
    op.create_index("ix_live_room_presences_organization_id", "live_room_presences", ["organization_id"])
    op.create_index("ix_live_room_presences_course_day_id", "live_room_presences", ["course_day_id"])
    op.create_index("ix_live_room_presences_user_seen", "live_room_presences", ["user_id", "last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_live_room_presences_user_seen", table_name="live_room_presences")
    op.drop_index("ix_live_room_presences_course_day_id", table_name="live_room_presences")
    op.drop_index("ix_live_room_presences_organization_id", table_name="live_room_presences")
    op.drop_table("live_room_presences")
