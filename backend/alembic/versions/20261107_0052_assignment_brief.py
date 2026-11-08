"""Store the structured sheet of an assignment.

Revision ID: 20261107_0052
Revises: 20261107_0051
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261107_0052"
down_revision = "20261107_0051"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.add_column(sa.Column("brief_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_column("brief_json")
