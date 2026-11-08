"""Freeze guided programs and keep the badges students reached, as on the mother site.

Revision ID: 20261108_0055
Revises: 20261107_0054
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261108_0055"
down_revision = "20261107_0054"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_program_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "version", name="uq_session_program_version"),
    )
    op.create_index("ix_session_program_versions_organization_id", "session_program_versions", ["organization_id"])
    op.create_index("ix_session_program_versions_session_id", "session_program_versions", ["session_id"])
    op.create_table(
        "badge_awards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_version_id", sa.Integer(), sa.ForeignKey("session_program_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("level", sa.String(24), nullable=False),
        sa.Column("score_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("enrollment_id", "level", name="uq_badge_award_enrollment_level"),
    )
    op.create_index("ix_badge_awards_organization_id", "badge_awards", ["organization_id"])
    op.create_index("ix_badge_awards_enrollment_id", "badge_awards", ["enrollment_id"])


def downgrade() -> None:
    op.drop_index("ix_badge_awards_enrollment_id", table_name="badge_awards")
    op.drop_index("ix_badge_awards_organization_id", table_name="badge_awards")
    op.drop_table("badge_awards")
    op.drop_index("ix_session_program_versions_session_id", table_name="session_program_versions")
    op.drop_index("ix_session_program_versions_organization_id", table_name="session_program_versions")
    op.drop_table("session_program_versions")
