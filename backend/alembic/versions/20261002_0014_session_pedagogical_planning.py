"""session pedagogical planning

Revision ID: 20261002_0014
Revises: 20261002_0013
Create Date: 2026-10-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_0014"
down_revision: str | None = "20261002_0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_course_days",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teacher_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default="90",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="planned",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_session_course_days_organization_id",
        "session_course_days",
        ["organization_id"],
    )
    op.create_index(
        "ix_session_course_days_session_id",
        "session_course_days",
        ["session_id"],
    )
    op.create_index(
        "ix_session_course_days_teacher_id",
        "session_course_days",
        ["teacher_id"],
    )
    op.create_index(
        "ix_session_course_days_scheduled_at",
        "session_course_days",
        ["scheduled_at"],
    )
    op.create_index(
        "ix_session_course_days_org_session",
        "session_course_days",
        ["organization_id", "session_id"],
    )
    op.create_index(
        "ix_session_course_days_org_teacher",
        "session_course_days",
        ["organization_id", "teacher_id"],
    )
    op.create_index(
        "ix_session_course_days_org_scheduled",
        "session_course_days",
        ["organization_id", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_table("session_course_days")
