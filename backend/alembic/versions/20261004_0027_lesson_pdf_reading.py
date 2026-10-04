"""Private PDF lesson assets and per-enrollment page reading.

Revision ID: 20261004_0027
Revises: 20261004_0026
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261004_0027"
down_revision = "20261004_0026"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson_pdf_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("source_sha", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "source_url", name="uq_lesson_pdf_asset_url"),
    )
    op.create_index("ix_lesson_pdf_assets_organization_id", "lesson_pdf_assets", ["organization_id"])
    op.create_table(
        "lesson_pdf_progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_sha", sa.String(64), nullable=False),
        sa.Column("viewed_pages", sa.JSON(), nullable=False),
        sa.Column("last_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active_page", sa.Integer(), nullable=True),
        sa.Column("active_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("enrollment_id", "lesson_id", name="uq_school_lesson_pdf_progress"),
    )
    op.create_index("ix_lesson_pdf_progress_organization_id", "lesson_pdf_progress", ["organization_id"])
    op.create_index("ix_lesson_pdf_progress_enrollment_id", "lesson_pdf_progress", ["enrollment_id"])
    op.create_index("ix_lesson_pdf_progress_lesson_id", "lesson_pdf_progress", ["lesson_id"])


def downgrade() -> None:
    op.drop_table("lesson_pdf_progress")
    op.drop_table("lesson_pdf_assets")
