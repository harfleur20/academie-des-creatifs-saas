"""Link course lessons to existing session activities and opening dates.

Revision ID: 20261004_0026
Revises: 20261004_0025
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261004_0026"
down_revision = "20261004_0025"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("quiz_id", sa.Integer(), nullable=True))
    op.add_column("lessons", sa.Column("assignment_id", sa.Integer(), nullable=True))
    op.add_column("lessons", sa.Column("resource_id", sa.Integer(), nullable=True))
    op.add_column("lessons", sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("lessons") as batch:
        batch.create_foreign_key("fk_lessons_quiz_id", "quizzes", ["quiz_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_lessons_assignment_id", "assignments", ["assignment_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_lessons_resource_id", "resources", ["resource_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_lessons_quiz_id", "lessons", ["quiz_id"])
    op.create_index("ix_lessons_assignment_id", "lessons", ["assignment_id"])
    op.create_index("ix_lessons_resource_id", "lessons", ["resource_id"])


def downgrade() -> None:
    op.drop_index("ix_lessons_resource_id", table_name="lessons")
    op.drop_index("ix_lessons_assignment_id", table_name="lessons")
    op.drop_index("ix_lessons_quiz_id", table_name="lessons")
    with op.batch_alter_table("lessons") as batch:
        batch.drop_constraint("fk_lessons_resource_id", type_="foreignkey")
        batch.drop_constraint("fk_lessons_assignment_id", type_="foreignkey")
        batch.drop_constraint("fk_lessons_quiz_id", type_="foreignkey")
    op.drop_column("lessons", "available_at")
    op.drop_column("lessons", "resource_id")
    op.drop_column("lessons", "assignment_id")
    op.drop_column("lessons", "quiz_id")
