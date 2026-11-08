"""Link a teacher grade to the course day it evaluates.

Revision ID: 20261107_0050
Revises: 20261008_0049
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261107_0050"
down_revision = "20261008_0049"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("grades", sa.Column("course_day_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("grades") as batch:
        batch.create_foreign_key(
            "fk_grades_course_day_id", "session_course_days", ["course_day_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_grades_course_day_id", "grades", ["course_day_id"])


def downgrade() -> None:
    op.drop_index("ix_grades_course_day_id", table_name="grades")
    with op.batch_alter_table("grades") as batch:
        batch.drop_constraint("fk_grades_course_day_id", type_="foreignkey")
    op.drop_column("grades", "course_day_id")
