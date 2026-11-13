"""The public site's titles and subtitles get their own size, next to the text's.

One slider used to scale every text of a school's site; a school now sets the titles,
the subtitles and the text apart (85 % to 125 % each). font_size_scale stays the text's.

Revision ID: 20261113_0064
Revises: 20261112_0063
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261113_0064"
down_revision = "20261112_0063"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch_op:
        batch_op.add_column(sa.Column("heading_size_scale", sa.Integer(), nullable=False, server_default="100"))
        batch_op.add_column(sa.Column("subtitle_size_scale", sa.Integer(), nullable=False, server_default="100"))


def downgrade() -> None:
    with op.batch_alter_table("organization_public_sites") as batch_op:
        batch_op.drop_column("subtitle_size_scale")
        batch_op.drop_column("heading_size_scale")
