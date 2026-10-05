"""Add an optional announcement banner to each school public site.

Revision ID: 20261005_0035
Revises: 20261005_0034
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0035"
down_revision = "20261005_0034"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_public_sites",
        sa.Column("announcement_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organization_public_sites",
        sa.Column("announcement_text", sa.String(600), nullable=False, server_default=""),
    )
    op.add_column(
        "organization_public_sites",
        sa.Column("announcement_background_color", sa.String(7), nullable=False, server_default="#FFF4E7"),
    )
    op.add_column(
        "organization_public_sites",
        sa.Column("announcement_text_color", sa.String(7), nullable=False, server_default="#7C4200"),
    )


def downgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch:
        batch.drop_column("announcement_text_color")
        batch.drop_column("announcement_background_color")
        batch.drop_column("announcement_text")
        batch.drop_column("announcement_enabled")
