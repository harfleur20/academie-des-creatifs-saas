"""Separate sidebar collapse permission from current collapsed state."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261116_0073"
down_revision = "20261115_0072"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "direction_sidebar_collapse_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.alter_column(
            "direction_sidebar_collapsed",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
    # Existing schools keep an expanded sidebar, with the collapse control enabled.
    op.execute(
        sa.text(
            "UPDATE organizations "
            "SET direction_sidebar_collapse_enabled = TRUE, "
            "direction_sidebar_collapsed = FALSE"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("direction_sidebar_collapse_enabled")
