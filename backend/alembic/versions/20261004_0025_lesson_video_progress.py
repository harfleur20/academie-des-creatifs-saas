"""Track watched video ranges for school lessons.

Revision ID: 20261004_0025
Revises: 20261004_0024
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261004_0025"
down_revision = "20261004_0024"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson_video_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watched_ranges", sa.JSON(), nullable=False),
        sa.Column("watched_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("watched_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_position_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("enrollment_id", "lesson_id", name="uq_lesson_video_progress_enrollment_lesson"),
    )
    op.create_index("ix_lesson_video_progress_organization_id", "lesson_video_progress", ["organization_id"])
    op.create_index("ix_lesson_video_progress_enrollment_id", "lesson_video_progress", ["enrollment_id"])
    op.create_index("ix_lesson_video_progress_lesson_id", "lesson_video_progress", ["lesson_id"])
    op.create_index("ix_lesson_video_progress_org_enrollment", "lesson_video_progress", ["organization_id", "enrollment_id"])


def downgrade() -> None:
    op.drop_table("lesson_video_progress")
