"""Quiz questions with several right answers and points, as on the mother site's online quizzes.

Existing questions keep one right answer and are worth one point each.

Revision ID: 20261108_0056
Revises: 20261108_0055
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261108_0056"
down_revision = "20261108_0055"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.add_column(sa.Column("selection_mode", sa.String(16), nullable=False, server_default="single"))
        batch_op.add_column(sa.Column("correct_indices", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("points", sa.Float(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.drop_column("points")
        batch_op.drop_column("correct_indices")
        batch_op.drop_column("selection_mode")
