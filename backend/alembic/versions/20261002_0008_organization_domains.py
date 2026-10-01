"""organization domains and subdomains

Revision ID: 20261002_0008
Revises: 20261002_0007
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0008"
down_revision: str | None = "20261002_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("subdomain", sa.String(length=63), nullable=True),
    )
    op.create_index(
        "ix_organizations_subdomain",
        "organizations",
        ["subdomain"],
        unique=True,
    )

    op.create_table(
        "organization_domains",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("verification_token", sa.String(length=96), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hostname", name="uq_organization_domains_hostname"),
    )
    op.create_index(
        "ix_organization_domains_organization_id",
        "organization_domains",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_domains_hostname",
        "organization_domains",
        ["hostname"],
        unique=True,
    )
    op.create_index(
        "ix_organization_domains_status",
        "organization_domains",
        ["status"],
    )
    op.create_index(
        "ix_organization_domains_org_status",
        "organization_domains",
        ["organization_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("organization_domains")
    op.drop_index("ix_organizations_subdomain", table_name="organizations")
    op.drop_column("organizations", "subdomain")
