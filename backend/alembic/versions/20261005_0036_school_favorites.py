"""Store favorite formations separately for each school.

Revision ID: 20261005_0036
Revises: 20261005_0035
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0036"
down_revision = "20261005_0035"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "school_favorites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("formation_id", sa.Integer(), sa.ForeignKey("formations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", "formation_id", name="uq_school_favorite_user_formation"),
    )
    op.create_index("ix_school_favorites_organization_id", "school_favorites", ["organization_id"])
    op.create_index("ix_school_favorites_user_id", "school_favorites", ["user_id"])
    op.create_index("ix_school_favorites_formation_id", "school_favorites", ["formation_id"])


def downgrade() -> None:
    op.drop_index("ix_school_favorites_formation_id", table_name="school_favorites")
    op.drop_index("ix_school_favorites_user_id", table_name="school_favorites")
    op.drop_index("ix_school_favorites_organization_id", table_name="school_favorites")
    op.drop_table("school_favorites")
