"""user profile fields

Revision ID: 20261002_0017
Revises: 20261002_0016
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0017"
down_revision: str | None = "20261002_0016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "phone")
