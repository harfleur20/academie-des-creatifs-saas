"""organization white-label branding

Revision ID: 20261002_0007
Revises: 20261001_0006
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0007"
down_revision: str | None = "20261001_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("logo_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "primary_color",
            sa.String(length=7),
            nullable=False,
            server_default="#1768FF",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "secondary_color",
            sa.String(length=7),
            nullable=False,
            server_default="#21C889",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "accent_color",
            sa.String(length=7),
            nullable=False,
            server_default="#10233F",
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "accent_color")
    op.drop_column("organizations", "secondary_color")
    op.drop_column("organizations", "primary_color")
    op.drop_column("organizations", "logo_url")
