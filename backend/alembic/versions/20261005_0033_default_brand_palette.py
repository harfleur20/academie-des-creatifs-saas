"""Align the default school palette with the Académie des Créatifs.

Revision ID: 20261005_0033
Revises: 20261005_0032
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0033"
down_revision = "20261005_0032"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Change only schools that still carry the complete former default palette.
    # Any customized color keeps the school's current branding intact.
    op.get_bind().execute(
        sa.text(
            "UPDATE organizations "
            "SET primary_color = :new_primary, "
            "secondary_color = :new_secondary, "
            "accent_color = :new_accent "
            "WHERE UPPER(primary_color) = :old_primary "
            "AND UPPER(secondary_color) = :old_secondary "
            "AND UPPER(accent_color) = :old_accent"
        ),
        {
            "new_primary": "#1F2559",
            "new_secondary": "#18A7A3",
            "new_accent": "#131735",
            "old_primary": "#1768FF",
            "old_secondary": "#21C889",
            "old_accent": "#10233F",
        },
    )


def downgrade() -> None:
    # Branding changes made since this migration cannot be inferred safely.
    pass
