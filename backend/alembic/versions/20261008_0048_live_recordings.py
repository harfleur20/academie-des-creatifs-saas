"""Keep school live replays private and scoped to a course day.

Revision ID: 20261008_0048
Revises: 20261007_0047
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261008_0048"
down_revision = "20261007_0047"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_recordings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("formation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_day_id", sa.Integer(), sa.ForeignKey("session_course_days.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_recording_id", sa.String(180), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("content_type", sa.String(80), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("download_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "provider_recording_id", name="uq_live_recording_org_provider_id"),
    )
    op.create_index("ix_live_recordings_organization_id", "live_recordings", ["organization_id"])
    op.create_index("ix_live_recordings_org_session", "live_recordings", ["organization_id", "session_id"])


def downgrade() -> None:
    op.drop_index("ix_live_recordings_org_session", table_name="live_recordings")
    op.drop_index("ix_live_recordings_organization_id", table_name="live_recordings")
    op.drop_table("live_recordings")
