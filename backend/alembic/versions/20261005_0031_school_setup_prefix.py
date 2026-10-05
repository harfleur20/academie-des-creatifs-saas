"""Track explicit confirmation of each school's matricule prefix.

Revision ID: 20261005_0031
Revises: 20261005_0030
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0031"
down_revision = "20261005_0030"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_public_sites",
        sa.Column("student_code_prefix_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch:
        batch.drop_column("student_code_prefix_confirmed_at")
