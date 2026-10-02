"""multi-role organization memberships

Revision ID: 20261002_0013
Revises: 20261002_0012
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0013"
down_revision: str | None = "20261002_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_member_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("organization_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
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
        sa.UniqueConstraint(
            "member_id",
            "role",
            name="uq_organization_member_roles_member_role",
        ),
    )
    op.create_index(
        "ix_organization_member_roles_organization_id",
        "organization_member_roles",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_member_roles_member_id",
        "organization_member_roles",
        ["member_id"],
    )
    op.create_index(
        "ix_organization_member_roles_role",
        "organization_member_roles",
        ["role"],
    )
    op.create_index(
        "ix_organization_member_roles_org_role",
        "organization_member_roles",
        ["organization_id", "role"],
    )
    op.execute(
        """
        INSERT INTO organization_member_roles
            (organization_id, member_id, role, created_at, updated_at)
        SELECT
            organization_id, id, role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM organization_members
        """
    )


def downgrade() -> None:
    op.drop_table("organization_member_roles")
