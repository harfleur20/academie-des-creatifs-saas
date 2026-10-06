"""Track explicit starts of live course days.

Revision ID: 20261006_0041
Revises: 20261006_0040
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261006_0041"
down_revision = "20261006_0040"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_course_days", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("session_course_days", "started_at")
