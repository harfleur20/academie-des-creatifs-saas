"""Add per-organization Direction appearance preferences."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261115_0071"
down_revision = "20261115_0070"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "direction_accent_color",
            sa.String(length=7),
            nullable=False,
            server_default="#18A7A3",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "direction_sidebar_collapsed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "direction_sidebar_collapsed")
    op.drop_column("organizations", "direction_accent_color")
