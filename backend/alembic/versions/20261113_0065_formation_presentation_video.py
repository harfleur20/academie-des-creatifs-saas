"""Add an optional public presentation video to formations."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261113_0065"
down_revision = "20261113_0064"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "formations",
        sa.Column("presentation_video_url", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("formations", "presentation_video_url")
