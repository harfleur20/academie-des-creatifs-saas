"""demo billing payments

Revision ID: 20261001_0004
Revises: 20261001_0003
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0004"
down_revision: str | None = "20261001_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_payment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("billing_interval", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_reference", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider_reference"),
    )
    op.create_index(
        "ix_billing_payment_attempts_organization_id",
        "billing_payment_attempts",
        ["organization_id"],
    )
    op.create_index(
        "ix_billing_payment_attempts_plan_id",
        "billing_payment_attempts",
        ["plan_id"],
    )
    op.create_index(
        "ix_billing_payment_attempts_provider",
        "billing_payment_attempts",
        ["provider"],
    )
    op.create_index(
        "ix_billing_payment_attempts_provider_reference",
        "billing_payment_attempts",
        ["provider_reference"],
    )
    op.create_index(
        "ix_billing_payment_attempts_status",
        "billing_payment_attempts",
        ["status"],
    )
    op.create_index(
        "ix_billing_payment_attempts_org_status",
        "billing_payment_attempts",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("billing_payment_attempts")
