"""The plan a school picked on the landing page, kept on its trial (docs/FORFAITS.md).

A new school tries Pro for 14 days whatever it clicked; the trial reminders and the billing
page then bring it back to the plan and billing period it had chosen.

Revision ID: 20261112_0063
Revises: 20261112_0062
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261112_0063"
down_revision = "20261112_0062"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("chosen_plan_code", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("chosen_billing_interval", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("chosen_billing_interval")
        batch_op.drop_column("chosen_plan_code")
