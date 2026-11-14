"""The time a live room is in use: Découverte's hours count only while someone is in it.

Revision ID: 20261114_0067
Revises: 20261114_0066
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261114_0067"
down_revision = "20261114_0066"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_course_days") as batch:
        batch.add_column(sa.Column("live_active_seconds", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("live_active_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_course_days") as batch:
        batch.drop_column("live_active_at")
        batch.drop_column("live_active_seconds")
