"""branded documents and communication delivery metadata

Revision ID: 20261003_0019
Revises: 20261003_0018
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision="20261003_0019"
down_revision="20261003_0018"
branch_labels: Sequence[str] | None=None
depends_on: Sequence[str] | None=None

def upgrade() -> None:
    op.add_column(
        "certificates",
        sa.Column(
            "branding_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "communication_outbox",
        sa.Column(
            "attempts_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "communication_outbox",
        sa.Column("last_error", sa.Text(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("communication_outbox", "last_error")
    op.drop_column("communication_outbox", "attempts_count")
    op.drop_column("certificates", "branding_snapshot")
