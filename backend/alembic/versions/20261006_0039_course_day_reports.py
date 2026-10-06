"""Store completion reports for scheduled school course days.

Revision ID: 20261006_0039
Revises: 20261005_0038
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261006_0039"
down_revision = "20261005_0038"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_course_days", sa.Column("delivery_status", sa.String(24), nullable=True))
    op.add_column("session_course_days", sa.Column("report_summary", sa.Text(), nullable=True))
    op.add_column("session_course_days", sa.Column("report_submitted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("session_course_days", "report_submitted_at")
    op.drop_column("session_course_days", "report_summary")
    op.drop_column("session_course_days", "delivery_status")
