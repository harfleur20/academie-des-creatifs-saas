"""Store super-admin integration badge preferences."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261115_0069"
down_revision = "20261115_0068"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_integration_preferences",
        sa.Column("provider", sa.String(length=50), primary_key=True),
        sa.Column("badge_mode", sa.String(length=20), nullable=False, server_default="connect"),
        sa.Column(
            "updated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("platform_integration_preferences")
