"""Teacher professional onboarding and school charters.

Revision ID: 20261006_0043
Revises: 20261006_0042
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision = "20261006_0043"
down_revision = "20261006_0042"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teacher_professional_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("professional_title", sa.String(180), nullable=False, server_default=""),
        sa.Column("experience_years", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activity_domains", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("skills", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("portfolio_url", sa.String(1024), nullable=True),
        sa.Column("portfolio_file_key", sa.String(1024), nullable=True),
        sa.Column("portfolio_file_name", sa.String(255), nullable=True),
        sa.Column("cv_file_key", sa.String(1024), nullable=True),
        sa.Column("cv_file_name", sa.String(255), nullable=True),
        sa.Column("linkedin_url", sa.String(1024), nullable=True),
        sa.Column("behance_url", sa.String(1024), nullable=True),
        sa.Column("github_url", sa.String(1024), nullable=True),
        sa.Column("website_url", sa.String(1024), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("country", sa.String(120), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_teacher_professional_profiles_org_user"),
    )
    op.create_index("ix_teacher_professional_profiles_organization_id", "teacher_professional_profiles", ["organization_id"])
    op.create_index("ix_teacher_professional_profiles_user_id", "teacher_professional_profiles", ["user_id"])
    op.create_index("ix_teacher_professional_profiles_org_complete", "teacher_professional_profiles", ["organization_id", "profile_completed_at"])

    op.create_table(
        "organization_charters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("audience", sa.String(16), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "audience", name="uq_organization_charters_org_audience"),
    )
    op.create_index("ix_organization_charters_organization_id", "organization_charters", ["organization_id"])
    op.create_index("ix_organization_charters_org_enabled", "organization_charters", ["organization_id", "is_enabled"])

    op.create_table(
        "organization_charter_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("charter_id", sa.Integer(), sa.ForeignKey("organization_charters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("audience", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("charter_id", "user_id", "version", name="uq_charter_acceptance_user_version"),
    )
    op.create_index("ix_organization_charter_acceptances_organization_id", "organization_charter_acceptances", ["organization_id"])
    op.create_index("ix_organization_charter_acceptances_charter_id", "organization_charter_acceptances", ["charter_id"])
    op.create_index("ix_organization_charter_acceptances_user_id", "organization_charter_acceptances", ["user_id"])
    op.create_index("ix_charter_acceptances_org_user", "organization_charter_acceptances", ["organization_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_charter_acceptances_org_user", table_name="organization_charter_acceptances")
    op.drop_index("ix_organization_charter_acceptances_user_id", table_name="organization_charter_acceptances")
    op.drop_index("ix_organization_charter_acceptances_charter_id", table_name="organization_charter_acceptances")
    op.drop_index("ix_organization_charter_acceptances_organization_id", table_name="organization_charter_acceptances")
    op.drop_table("organization_charter_acceptances")

    op.drop_index("ix_organization_charters_org_enabled", table_name="organization_charters")
    op.drop_index("ix_organization_charters_organization_id", table_name="organization_charters")
    op.drop_table("organization_charters")

    op.drop_index("ix_teacher_professional_profiles_org_complete", table_name="teacher_professional_profiles")
    op.drop_index("ix_teacher_professional_profiles_user_id", table_name="teacher_professional_profiles")
    op.drop_index("ix_teacher_professional_profiles_organization_id", table_name="teacher_professional_profiles")
    op.drop_table("teacher_professional_profiles")
