"""Add independent lesson publication state while preserving existing visibility.

Revision ID: 20261004_0028
Revises: 20261004_0027
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261004_0028"
down_revision = "20261004_0027"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.add_column(sa.Column("publication_status", sa.String(24), nullable=False, server_default="published"))


def downgrade() -> None:
    with op.batch_alter_table("lessons") as batch_op:
        batch_op.drop_column("publication_status")
