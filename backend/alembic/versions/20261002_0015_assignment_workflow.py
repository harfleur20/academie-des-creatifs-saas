"""assignment submission and review workflow

Revision ID: 20261002_0015
Revises: 20261002_0014
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision="20261002_0015"; down_revision="20261002_0014"
branch_labels: Sequence[str] | None=None; depends_on: Sequence[str] | None=None

def upgrade():
    op.create_table("assignments",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE"),nullable=False),
      sa.Column("course_day_id",sa.Integer(),sa.ForeignKey("session_course_days.id",ondelete="SET NULL"),nullable=True),
      sa.Column("teacher_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL"),nullable=True),
      sa.Column("title",sa.String(255),nullable=False),
      sa.Column("instructions",sa.Text(),nullable=False,server_default=""),
      sa.Column("due_date",sa.DateTime(timezone=True),nullable=False),
      sa.Column("is_final_project",sa.Boolean(),nullable=False,server_default=sa.false()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n,c in [("organization_id",["organization_id"]),("session_id",["session_id"]),("course_day_id",["course_day_id"]),("teacher_id",["teacher_id"])]:
        op.create_index(f"ix_assignments_{n}","assignments",c)
    op.create_index("ix_assignments_org_session","assignments",["organization_id","session_id"])
    op.create_index("ix_assignments_org_teacher","assignments",["organization_id","teacher_id"])
    op.create_index("ix_assignments_org_due","assignments",["organization_id","due_date"])

    op.create_table("assignment_submissions",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("assignment_id",sa.Integer(),sa.ForeignKey("assignments.id",ondelete="CASCADE"),nullable=False),
      sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False),
      sa.Column("file_url",sa.String(1024),nullable=False),
      sa.Column("submitted_at",sa.DateTime(timezone=True),nullable=False),
      sa.Column("is_reviewed",sa.Boolean(),nullable=False,server_default=sa.false()),
      sa.Column("review_score",sa.Float(),nullable=True),
      sa.Column("review_max_score",sa.Float(),nullable=False,server_default="20"),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("assignment_id","enrollment_id",name="uq_assignment_submission"))
    for n in ("organization_id","assignment_id","enrollment_id"): op.create_index(f"ix_assignment_submissions_{n}","assignment_submissions",[n])
    op.create_index("ix_assignment_submissions_org_assignment","assignment_submissions",["organization_id","assignment_id"])

    op.create_table("assignment_comments",
      sa.Column("id",sa.Integer(),primary_key=True),
      sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("assignment_id",sa.Integer(),sa.ForeignKey("assignments.id",ondelete="CASCADE"),nullable=False),
      sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False),
      sa.Column("author_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
      sa.Column("author_role",sa.String(16),nullable=False),
      sa.Column("body",sa.Text(),nullable=False,server_default=""),
      sa.Column("attachment_url",sa.String(1024),nullable=True),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","assignment_id","enrollment_id","author_user_id"): op.create_index(f"ix_assignment_comments_{n}","assignment_comments",[n])
    op.create_index("ix_assignment_comments_org_assignment","assignment_comments",["organization_id","assignment_id"])
    op.create_index("ix_assignment_comments_org_enrollment","assignment_comments",["organization_id","enrollment_id"])

def downgrade():
    op.drop_table("assignment_comments"); op.drop_table("assignment_submissions"); op.drop_table("assignments")
