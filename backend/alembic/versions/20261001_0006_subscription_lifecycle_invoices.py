"""subscription lifecycle and invoices

Revision ID: 20261001_0006
Revises: 20261001_0005
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0006"
down_revision: str | None = "20261001_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "payment_attempt_id",
            sa.Integer(),
            sa.ForeignKey("billing_payment_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("billing_interval", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("invoice_number", name="uq_billing_invoices_number"),
        sa.UniqueConstraint("payment_attempt_id", name="uq_billing_invoices_payment_attempt"),
    )
    op.create_index("ix_billing_invoices_organization_id", "billing_invoices", ["organization_id"])
    op.create_index("ix_billing_invoices_subscription_id", "billing_invoices", ["subscription_id"])
    op.create_index("ix_billing_invoices_plan_id", "billing_invoices", ["plan_id"])
    op.create_index("ix_billing_invoices_payment_attempt_id", "billing_invoices", ["payment_attempt_id"], unique=True)
    op.create_index("ix_billing_invoices_invoice_number", "billing_invoices", ["invoice_number"], unique=True)
    op.create_index("ix_billing_invoices_status", "billing_invoices", ["status"])
    op.create_index("ix_billing_invoices_org_status", "billing_invoices", ["organization_id", "status"])


def downgrade() -> None:
    op.drop_table("billing_invoices")
    op.drop_column("subscriptions", "suspended_at")
    op.drop_column("subscriptions", "grace_period_ends_at")
