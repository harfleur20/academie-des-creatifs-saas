"""Backfill internal content sessions for online formations without a cohort.

Revision ID: 20261005_0029
Revises: 20261004_0028
"""
from collections.abc import Sequence
from datetime import date

from alembic import op
import sqlalchemy as sa


revision = "20261005_0029"
down_revision = "20261004_0028"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    formations = sa.table(
        "formations",
        sa.column("id", sa.Integer),
        sa.column("organization_id", sa.Integer),
        sa.column("format_type", sa.String),
    )
    sessions = sa.table(
        "formation_sessions",
        sa.column("id", sa.Integer),
        sa.column("organization_id", sa.Integer),
        sa.column("formation_id", sa.Integer),
        sa.column("label", sa.String),
        sa.column("start_date", sa.Date),
        sa.column("end_date", sa.Date),
        sa.column("seat_capacity", sa.Integer),
        sa.column("status", sa.String),
    )
    rows = bind.execute(
        sa.select(formations.c.id, formations.c.organization_id).where(
            formations.c.format_type == "ligne",
            ~sa.exists(sa.select(sessions.c.id).where(
                sessions.c.formation_id == formations.c.id,
                sessions.c.organization_id == formations.c.organization_id,
            )),
        )
    ).all()
    for formation_id, organization_id in rows:
        bind.execute(sessions.insert().values(
            organization_id=organization_id,
            formation_id=formation_id,
            label="Accès en ligne",
            start_date=date.today(),
            end_date=date.max,
            seat_capacity=0,
            status="open",
        ))


def downgrade() -> None:
    # These rows may already own courses, enrollments, and orders.
    pass
