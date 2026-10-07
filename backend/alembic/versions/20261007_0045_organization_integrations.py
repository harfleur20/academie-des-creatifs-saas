"""Organization-scoped external integrations.

Revision ID: 20261007_0045
Revises: 20261006_0044
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261007_0045"
down_revision = "20261006_0044"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_integrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="connected"),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False, server_default="gpt-6-luna"),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("organization_id", "provider", name="uq_org_integrations_org_provider"),
    )
    op.create_index(
        "ix_org_integrations_organization_id",
        "organization_integrations",
        ["organization_id"],
    )
    op.create_index(
        "ix_org_integrations_org_status",
        "organization_integrations",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_org_integrations_org_status", table_name="organization_integrations")
    op.drop_index("ix_org_integrations_organization_id", table_name="organization_integrations")
    op.drop_table("organization_integrations")
