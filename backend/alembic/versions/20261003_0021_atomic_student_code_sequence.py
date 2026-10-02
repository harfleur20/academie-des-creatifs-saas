"""atomic school student code sequence

Revision ID: 20261003_0021
Revises: 20261003_0020
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = "20261003_0021"
down_revision = "20261003_0020"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_public_sites",
        sa.Column(
            "student_code_sequence_year",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "organization_public_sites",
        sa.Column(
            "student_code_sequence",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("organization_public_sites", "student_code_sequence")
    op.drop_column("organization_public_sites", "student_code_sequence_year")
