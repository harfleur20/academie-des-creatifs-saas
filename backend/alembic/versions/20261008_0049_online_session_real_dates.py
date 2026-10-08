"""Replace sentinel online-session end dates with finite access dates.

Revision ID: 20261008_0049
Revises: 20261008_0048
"""
from collections.abc import Sequence
from datetime import date, timedelta

from alembic import op
import sqlalchemy as sa


revision = "20261008_0049"
down_revision = "20261008_0048"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


ONLINE_ACCESS_DEFAULT_DAYS = 365


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
        sa.column("start_date", sa.Date),
        sa.column("end_date", sa.Date),
    )

    rows = bind.execute(
        sa.select(sessions.c.id, sessions.c.start_date)
        .select_from(
            sessions.join(
                formations,
                sa.and_(
                    formations.c.id == sessions.c.formation_id,
                    formations.c.organization_id == sessions.c.organization_id,
                ),
            )
        )
        .where(
            formations.c.format_type == "ligne",
            sessions.c.end_date == date.max,
        )
    ).all()

    for session_id, start_date in rows:
        finite_start = start_date or date.today()
        bind.execute(
            sessions.update()
            .where(sessions.c.id == session_id)
            .values(end_date=finite_start + timedelta(days=ONLINE_ACCESS_DEFAULT_DAYS))
        )


def downgrade() -> None:
    # Do not restore a synthetic year-9999 date.
    pass
