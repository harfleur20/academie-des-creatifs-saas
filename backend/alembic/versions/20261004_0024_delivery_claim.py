"""Track claimed communication deliveries.

Revision ID: 20261004_0024
Revises: 20261004_0023
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = "20261004_0024"
down_revision = "20261004_0023"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("communication_outbox", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("communication_outbox", sa.Column("claim_token", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("communication_outbox", "claim_token")
    op.drop_column("communication_outbox", "claimed_at")
