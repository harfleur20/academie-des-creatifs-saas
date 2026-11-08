"""Let an assignment stay a draft until its teacher publishes it.

Existing assignments are already visible to students, so they stay published.

Revision ID: 20261107_0051
Revises: 20261107_0050
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261107_0051"
down_revision = "20261107_0050"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.add_column(sa.Column("publication_status", sa.String(16), nullable=False, server_default="published"))


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_column("publication_status")
