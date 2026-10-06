"""Add structured detail to course day completion reports.

Revision ID: 20261006_0042
Revises: 20261006_0041
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261006_0042"
down_revision = "20261006_0041"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_course_days", sa.Column("report_difficulties", sa.Text(), nullable=True))
    op.add_column("session_course_days", sa.Column("report_homework", sa.Text(), nullable=True))
    op.add_column("session_course_days", sa.Column("report_attendance_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("session_course_days", "report_attendance_notes")
    op.drop_column("session_course_days", "report_homework")
    op.drop_column("session_course_days", "report_difficulties")
