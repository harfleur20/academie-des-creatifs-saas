"""tara billing integrity fields

Revision ID: 20261001_0005
Revises: 20261001_0004
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0005"
down_revision: str | None = "20261001_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "billing_payment_attempts",
        sa.Column("checkout_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "billing_payment_attempts",
        sa.Column("provider_transaction_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        "billing_payment_attempts",
        sa.Column(
            "activated_subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "billing_payment_attempts",
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_billing_payment_attempts_provider_transaction_id",
        "billing_payment_attempts",
        ["provider_transaction_id"],
        unique=True,
    )
    op.create_index(
        "ix_billing_payment_attempts_activated_subscription_id",
        "billing_payment_attempts",
        ["activated_subscription_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_payment_attempts_activated_subscription_id",
        table_name="billing_payment_attempts",
    )
    op.drop_index(
        "ix_billing_payment_attempts_provider_transaction_id",
        table_name="billing_payment_attempts",
    )
    op.drop_column("billing_payment_attempts", "failure_reason")
    op.drop_column("billing_payment_attempts", "activated_subscription_id")
    op.drop_column("billing_payment_attempts", "provider_transaction_id")
    op.drop_column("billing_payment_attempts", "checkout_url")
