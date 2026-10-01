"""school management and invitations

Revision ID: 20261001_0002
Revises: 20261001_0001
Create Date: 2026-10-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_0002"
down_revision: str | None = "20261001_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("contact_email", sa.String(length=180), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="UTC"),
    )
    op.add_column(
        "organizations",
        sa.Column("locale", sa.String(length=16), nullable=False, server_default="fr-FR"),
    )

    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=180), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "invited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "accepted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_organization_invitations_organization_id",
        "organization_invitations",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_invitations_email",
        "organization_invitations",
        ["email"],
    )
    op.create_index(
        "ix_organization_invitations_token_hash",
        "organization_invitations",
        ["token_hash"],
    )
    op.create_index(
        "ix_organization_invitations_status",
        "organization_invitations",
        ["status"],
    )
    op.create_index(
        "ix_organization_invitations_expires_at",
        "organization_invitations",
        ["expires_at"],
    )
    op.create_index(
        "ix_organization_invitations_org_email_status",
        "organization_invitations",
        ["organization_id", "email", "status"],
    )


def downgrade() -> None:
    op.drop_table("organization_invitations")
    op.drop_column("organizations", "locale")
    op.drop_column("organizations", "timezone")
    op.drop_column("organizations", "contact_email")
