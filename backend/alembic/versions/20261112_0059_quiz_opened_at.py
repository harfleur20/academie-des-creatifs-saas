"""When a quiz first opened to students, so it counts against them for the badge only 7 days later.

Quizzes already open take their scheduled date, else their last update.

Revision ID: 20261112_0059
Revises: 20261112_0058
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261112_0059"
down_revision = "20261112_0058"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("quizzes") as batch_op:
        batch_op.add_column(sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE quizzes SET opened_at = COALESCE(scheduled_at, updated_at, created_at) "
        "WHERE status IN ('active', 'closed')"
    )


def downgrade() -> None:
    with op.batch_alter_table("quizzes") as batch_op:
        batch_op.drop_column("opened_at")
