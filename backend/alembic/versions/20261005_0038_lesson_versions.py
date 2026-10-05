"""Keep a school-scoped, immutable history of lesson edits.

Revision ID: 20261005_0038
Revises: 20261005_0037
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261005_0038"
down_revision = "20261005_0037"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lessons", sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "lesson_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("edited_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lesson_id", "version_number", name="uq_lesson_versions_lesson_number"),
    )
    op.create_index("ix_lesson_versions_org_lesson", "lesson_versions", ["organization_id", "lesson_id"])
    op.create_index("ix_lesson_versions_organization_id", "lesson_versions", ["organization_id"])

    connection = op.get_bind()
    lesson_rows = connection.execute(sa.text("""
        SELECT id, organization_id, title, order_index, lesson_type, publication_status,
               content, video_url, file_url, quiz_id, assignment_id, resource_id, available_at
        FROM lessons
    """)).mappings()
    versions = sa.table(
        "lesson_versions",
        sa.column("organization_id", sa.Integer()), sa.column("lesson_id", sa.Integer()),
        sa.column("version_number", sa.Integer()), sa.column("snapshot", sa.JSON()),
        sa.column("reason", sa.String()),
    )
    for lesson in lesson_rows:
        snapshot = {key: lesson[key] for key in (
            "title", "order_index", "lesson_type", "publication_status", "content",
            "video_url", "file_url", "quiz_id", "assignment_id", "resource_id",
        )}
        available_at = lesson["available_at"]
        snapshot["available_at"] = available_at.isoformat() if hasattr(available_at, "isoformat") else available_at
        connection.execute(versions.insert().values(
            organization_id=lesson["organization_id"], lesson_id=lesson["id"],
            version_number=1, snapshot=snapshot, reason="initial",
        ))


def downgrade() -> None:
    op.drop_index("ix_lesson_versions_organization_id", table_name="lesson_versions")
    op.drop_index("ix_lesson_versions_org_lesson", table_name="lesson_versions")
    op.drop_table("lesson_versions")
    op.drop_column("lessons", "version_number")
