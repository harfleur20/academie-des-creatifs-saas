"""Add school branding options for student login and registration.

Revision ID: 20261115_0068
Revises: 20261114_0067
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261115_0068"
down_revision = "20261114_0067"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch:
        batch.add_column(sa.Column("auth_background_image_url", sa.String(length=1024), nullable=True))
        batch.add_column(sa.Column("auth_show_school_name", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch:
        batch.drop_column("auth_show_school_name")
        batch.drop_column("auth_background_image_url")
