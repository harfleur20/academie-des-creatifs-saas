"""Add a controlled text size setting for school public sites.

Revision ID: 20261005_0032
Revises: 20261005_0031
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0032"
down_revision = "20261005_0031"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_public_sites",
        sa.Column("font_size_scale", sa.Integer(), nullable=False, server_default="100"),
    )


def downgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch:
        batch.drop_column("font_size_scale")
