"""teacher profile and branded document outputs

Revision ID: 20261003_0019
Revises: 20261003_0018
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision="20261003_0019"
down_revision="20261003_0018"
branch_labels: Sequence[str] | None=None
depends_on: Sequence[str] | None=None

def upgrade():
    op.create_table(
        "organization_teacher_profiles",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("teacher_code",sa.String(48),nullable=False),
        sa.Column("status",sa.String(24),nullable=False,server_default="active"),
        sa.Column("first_assigned_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("organization_id","user_id",name="uq_teacher_profile_org_user"),
        sa.UniqueConstraint("organization_id","teacher_code",name="uq_teacher_profile_org_code"),
    )
    for n in ("organization_id","user_id","teacher_code"):
        op.create_index(f"ix_organization_teacher_profiles_{n}","organization_teacher_profiles",[n])
    op.create_index("ix_teacher_profiles_org_status","organization_teacher_profiles",["organization_id","status"])
    op.add_column("certificates",sa.Column("branding_snapshot",sa.JSON(),nullable=False,server_default="{}"))
    op.add_column("certificates",sa.Column("pdf_url",sa.String(1024),nullable=True))
    op.add_column("order_invoices",sa.Column("pdf_url",sa.String(1024),nullable=True))

def downgrade():
    op.drop_column("order_invoices","pdf_url")
    op.drop_column("certificates","pdf_url")
    op.drop_column("certificates","branding_snapshot")
    op.drop_table("organization_teacher_profiles")
