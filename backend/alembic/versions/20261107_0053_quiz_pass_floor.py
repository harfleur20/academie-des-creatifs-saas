"""Pass every quiz at 80 % at least, as on the mother site.

PDF validation quizzes were passed at 70 %. A student who scored between 70 and
80 % keeps the completed lesson, but now sees the quiz as not passed and can try
again; until 80 %, it no longer counts for an online certificate.

Revision ID: 20261107_0053
Revises: 20261107_0052
"""
from collections.abc import Sequence

from alembic import op


revision = "20261107_0053"
down_revision = "20261107_0052"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE quizzes SET pass_pct = 80 WHERE pass_pct < 80")


def downgrade() -> None:
    # Only the PDF threshold is known; other values below 80 cannot be restored.
    op.execute(
        "UPDATE quizzes SET pass_pct = 70 WHERE id IN "
        "(SELECT quiz_id FROM lessons WHERE lesson_type = 'pdf' AND quiz_id IS NOT NULL)"
    )
