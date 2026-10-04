"""Add a revocable version to user access tokens.

Revision ID: 20261004_0023
Revises: 20261003_0022
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = "20261004_0023"
down_revision = "20261003_0022"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "session_version")
