"""formation sessions and pedagogical core

Revision ID: 20261002_0012
Revises: 20261002_0011
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0012"
down_revision: str | None = "20261002_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("formations", sa.Column("category", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("formations", sa.Column("level", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("formations", sa.Column("format_type", sa.String(length=32), nullable=False, server_default="ligne"))
    op.add_column("formations", sa.Column("training_hours", sa.Integer(), nullable=True))

    op.create_table(
        "formation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("formation_id", sa.Integer(), sa.ForeignKey("formations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("campus_label", sa.String(length=180), nullable=True),
        sa.Column("seat_capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_formation_sessions_organization_id", "formation_sessions", ["organization_id"])
    op.create_index("ix_formation_sessions_formation_id", "formation_sessions", ["formation_id"])
    op.create_index("ix_formation_sessions_org_formation", "formation_sessions", ["organization_id", "formation_id"])
    op.create_index("ix_formation_sessions_org_status", "formation_sessions", ["organization_id", "status"])

    op.create_table(
        "session_teachers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False, server_default="intervenant"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "teacher_id", name="uq_session_teachers_session_teacher"),
    )
    op.create_index("ix_session_teachers_organization_id", "session_teachers", ["organization_id"])
    op.create_index("ix_session_teachers_session_id", "session_teachers", ["session_id"])
    op.create_index("ix_session_teachers_teacher_id", "session_teachers", ["teacher_id"])
    op.create_index("ix_session_teachers_org_session", "session_teachers", ["organization_id", "session_id"])

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "student_id", name="uq_enrollments_session_student"),
    )
    op.create_index("ix_enrollments_organization_id", "enrollments", ["organization_id"])
    op.create_index("ix_enrollments_session_id", "enrollments", ["session_id"])
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"])
    op.create_index("ix_enrollments_org_session", "enrollments", ["organization_id", "session_id"])
    op.create_index("ix_enrollments_org_student", "enrollments", ["organization_id", "student_id"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_courses_organization_id", "courses", ["organization_id"])
    op.create_index("ix_courses_session_id", "courses", ["session_id"])
    op.create_index("ix_courses_teacher_id", "courses", ["teacher_id"])
    op.create_index("ix_courses_org_session", "courses", ["organization_id", "session_id"])
    op.create_index("ix_courses_org_status", "courses", ["organization_id", "status"])

    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chapters_organization_id", "chapters", ["organization_id"])
    op.create_index("ix_chapters_course_id", "chapters", ["course_id"])
    op.create_index("ix_chapters_org_course", "chapters", ["organization_id", "course_id"])

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lesson_type", sa.String(length=24), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("video_url", sa.String(length=512), nullable=True),
        sa.Column("file_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lessons_organization_id", "lessons", ["organization_id"])
    op.create_index("ix_lessons_chapter_id", "lessons", ["chapter_id"])
    op.create_index("ix_lessons_org_chapter", "lessons", ["organization_id", "chapter_id"])


def downgrade() -> None:
    op.drop_table("lessons")
    op.drop_table("chapters")
    op.drop_table("courses")
    op.drop_table("enrollments")
    op.drop_table("session_teachers")
    op.drop_table("formation_sessions")
    op.drop_column("formations", "training_hours")
    op.drop_column("formations", "format_type")
    op.drop_column("formations", "level")
    op.drop_column("formations", "category")
