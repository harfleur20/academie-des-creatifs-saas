"""Add a reversible 20-day organization deletion window."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261119_0075"
down_revision: str | None = "20261116_0074"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_organizations_deletion_scheduled_at",
        "organizations",
        ["deletion_scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_deletion_scheduled_at", table_name="organizations")
    op.drop_column("organizations", "deletion_scheduled_at")
    op.drop_column("organizations", "deletion_requested_at")
