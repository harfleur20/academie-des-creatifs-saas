"""Let a live formation take a reservation deposit, as on the mother site.

Revision ID: 20261107_0054
Revises: 20261107_0053
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261107_0054"
down_revision = "20261107_0053"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("formations") as batch_op:
        batch_op.add_column(sa.Column("reservation_deposit_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("reservation_deposit_percent", sa.Float(), nullable=False, server_default="37.5"))
    with op.batch_alter_table("student_orders") as batch_op:
        batch_op.add_column(sa.Column("deposit_cents", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("deposit_terms_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("student_orders") as batch_op:
        batch_op.drop_column("deposit_terms_accepted_at")
        batch_op.drop_column("deposit_cents")
    with op.batch_alter_table("formations") as batch_op:
        batch_op.drop_column("reservation_deposit_percent")
        batch_op.drop_column("reservation_deposit_enabled")
