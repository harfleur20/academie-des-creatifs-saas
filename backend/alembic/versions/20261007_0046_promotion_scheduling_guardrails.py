"""promotion scheduling guardrails

Revision ID: 20261007_0046
Revises: 20261007_0045
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261007_0046"
down_revision = "20261007_0045"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


FORMATION_INDEX = "uq_promotions_active_exact_formation"
SESSION_INDEX = "uq_promotions_active_exact_session"


def upgrade() -> None:
    op.create_index(
        FORMATION_INDEX,
        "promotions",
        [
            "organization_id",
            "formation_id",
            "discount_type",
            "discount_value",
            "starts_at",
            "ends_at",
        ],
        unique=True,
        postgresql_where=sa.text(
            "is_active IS TRUE AND formation_id IS NOT NULL AND session_id IS NULL"
        ),
        sqlite_where=sa.text(
            "is_active = 1 AND formation_id IS NOT NULL AND session_id IS NULL"
        ),
    )
    op.create_index(
        SESSION_INDEX,
        "promotions",
        [
            "organization_id",
            "session_id",
            "discount_type",
            "discount_value",
            "starts_at",
            "ends_at",
        ],
        unique=True,
        postgresql_where=sa.text(
            "is_active IS TRUE AND session_id IS NOT NULL AND formation_id IS NULL"
        ),
        sqlite_where=sa.text(
            "is_active = 1 AND session_id IS NOT NULL AND formation_id IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(SESSION_INDEX, table_name="promotions")
    op.drop_index(FORMATION_INDEX, table_name="promotions")
