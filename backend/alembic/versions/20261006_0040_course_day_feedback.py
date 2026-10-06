"""Store school-scoped student feedback on completed course days.

Revision ID: 20261006_0040
Revises: 20261006_0039
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261006_0040"
down_revision = "20261006_0039"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_day_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_day_id", sa.Integer(), sa.ForeignKey("session_course_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("delivery_status", sa.String(16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_day_id", "enrollment_id", name="uq_course_day_feedback_enrollment"),
    )
    op.create_index("ix_course_day_feedback_organization_id", "course_day_feedback", ["organization_id"])
    op.create_index("ix_course_day_feedback_org_day", "course_day_feedback", ["organization_id", "course_day_id"])


def downgrade() -> None:
    op.drop_index("ix_course_day_feedback_org_day", table_name="course_day_feedback")
    op.drop_index("ix_course_day_feedback_organization_id", table_name="course_day_feedback")
    op.drop_table("course_day_feedback")
