"""Teacher WhatsApp contact metadata.

Revision ID: 20261006_0044
Revises: 20261006_0043
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261006_0044"
down_revision = "20261006_0043"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teacher_professional_profiles", sa.Column("whatsapp_phone", sa.String(32), nullable=True))
    op.add_column("teacher_professional_profiles", sa.Column("whatsapp_country", sa.String(2), nullable=True))
    op.add_column(
        "teacher_professional_profiles",
        sa.Column("whatsapp_phone_legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "teacher_professional_profiles",
        sa.Column("whatsapp_phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teacher_professional_profiles", "whatsapp_phone_verified_at")
    op.drop_column("teacher_professional_profiles", "whatsapp_phone_legacy")
    op.drop_column("teacher_professional_profiles", "whatsapp_country")
    op.drop_column("teacher_professional_profiles", "whatsapp_phone")
