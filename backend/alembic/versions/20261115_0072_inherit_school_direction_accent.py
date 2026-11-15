"""Let the Direction accent inherit the school's secondary brand color."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261115_0072"
down_revision = "20261115_0071"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.alter_column(
            "direction_accent_color",
            existing_type=sa.String(length=7),
            nullable=True,
            server_default=None,
        )

    op.execute(
        sa.text(
            "UPDATE organizations "
            "SET direction_accent_color = NULL "
            "WHERE UPPER(direction_accent_color) = '#18A7A3'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE organizations "
            "SET direction_accent_color = '#18A7A3' "
            "WHERE direction_accent_color IS NULL"
        )
    )

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.alter_column(
            "direction_accent_color",
            existing_type=sa.String(length=7),
            nullable=False,
            server_default="#18A7A3",
        )
