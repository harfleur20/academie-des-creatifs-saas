"""remember the verified school origin used for payment returns

Revision ID: 20261003_0022
Revises: 20261003_0021
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision = "20261003_0022"
down_revision = "20261003_0021"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("student_orders", sa.Column("return_origin", sa.String(512), nullable=True))
    # Earlier lifecycle runs could mark an unpaid first installment late and
    # release its reserved seat while its payment link was still usable.
    op.execute("""UPDATE order_installments SET status = 'pending'
        WHERE sequence = 1 AND status = 'late'
        AND order_id IN (SELECT id FROM student_orders WHERE status = 'late' AND paid_cents = 0)""")
    op.execute("""UPDATE student_orders SET status = 'pending', access_status = 'pending'
        WHERE status = 'late' AND paid_cents = 0""")


def downgrade() -> None:
    op.drop_column("student_orders", "return_origin")
