"""complete pedagogical suite

Revision ID: 20261002_0016
Revises: 20261002_0015
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision="20261002_0016"
down_revision="20261002_0015"
branch_labels: Sequence[str] | None=None
depends_on: Sequence[str] | None=None

def upgrade() -> None:
    op.create_table("resources",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE"),nullable=False), sa.Column("course_day_id",sa.Integer(),sa.ForeignKey("session_course_days.id",ondelete="SET NULL")),
        sa.Column("teacher_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")), sa.Column("title",sa.String(255),nullable=False), sa.Column("resource_type",sa.String(24),nullable=False,server_default="link"),
        sa.Column("url",sa.String(1024),nullable=False), sa.Column("published_at",sa.DateTime(timezone=True)), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","session_id","course_day_id","teacher_id"): op.create_index(f"ix_resources_{n}","resources",[n])
    op.create_index("ix_resources_org_session","resources",["organization_id","session_id"]); op.create_index("ix_resources_org_teacher","resources",["organization_id","teacher_id"])

    op.create_table("quizzes",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE"),nullable=False), sa.Column("course_day_id",sa.Integer(),sa.ForeignKey("session_course_days.id",ondelete="SET NULL")),
        sa.Column("teacher_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")), sa.Column("title",sa.String(255),nullable=False), sa.Column("assessment_type",sa.String(16),nullable=False,server_default="quiz"),
        sa.Column("duration_minutes",sa.Integer()), sa.Column("scheduled_at",sa.DateTime(timezone=True)), sa.Column("status",sa.String(16),nullable=False,server_default="draft"), sa.Column("pass_pct",sa.Float(),nullable=False,server_default="80"),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","session_id","course_day_id","teacher_id","status"): op.create_index(f"ix_quizzes_{n}","quizzes",[n])
    op.create_index("ix_quizzes_org_session","quizzes",["organization_id","session_id"]); op.create_index("ix_quizzes_org_teacher","quizzes",["organization_id","teacher_id"]); op.create_index("ix_quizzes_org_status","quizzes",["organization_id","status"])

    op.create_table("quiz_questions",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("quiz_id",sa.Integer(),sa.ForeignKey("quizzes.id",ondelete="CASCADE"),nullable=False), sa.Column("order_index",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("text",sa.Text(),nullable=False), sa.Column("options",sa.JSON(),nullable=False), sa.Column("correct_index",sa.Integer(),nullable=False,server_default="0"))
    op.create_index("ix_quiz_questions_organization_id","quiz_questions",["organization_id"]); op.create_index("ix_quiz_questions_quiz_id","quiz_questions",["quiz_id"]); op.create_index("ix_quiz_questions_org_quiz","quiz_questions",["organization_id","quiz_id"])

    op.create_table("quiz_attempts",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("quiz_id",sa.Integer(),sa.ForeignKey("quizzes.id",ondelete="CASCADE"),nullable=False), sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("attempt_number",sa.Integer(),nullable=False), sa.Column("answers",sa.JSON(),nullable=False), sa.Column("score_pct",sa.Float(),nullable=False,server_default="0"), sa.Column("submitted_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("quiz_id","enrollment_id","attempt_number",name="uq_quiz_attempt"))
    for n in ("organization_id","quiz_id","enrollment_id"): op.create_index(f"ix_quiz_attempts_{n}","quiz_attempts",[n])
    op.create_index("ix_quiz_attempts_org_quiz","quiz_attempts",["organization_id","quiz_id"]); op.create_index("ix_quiz_attempts_org_enrollment","quiz_attempts",["organization_id","enrollment_id"])

    op.create_table("lesson_progress",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False), sa.Column("lesson_id",sa.Integer(),sa.ForeignKey("lessons.id",ondelete="CASCADE"),nullable=False),
        sa.Column("completed_at",sa.DateTime(timezone=True),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("enrollment_id","lesson_id",name="uq_lesson_progress_enrollment_lesson"))
    for n in ("organization_id","enrollment_id","lesson_id"): op.create_index(f"ix_lesson_progress_{n}","lesson_progress",[n])
    op.create_index("ix_lesson_progress_org_enrollment","lesson_progress",["organization_id","enrollment_id"])

    op.create_table("attendance",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("course_day_id",sa.Integer(),sa.ForeignKey("session_course_days.id",ondelete="CASCADE"),nullable=False), sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("status",sa.String(16),nullable=False,server_default="present"), sa.Column("marked_by_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")), sa.Column("marked_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("course_day_id","enrollment_id",name="uq_attendance_course_day_enrollment"))
    for n in ("organization_id","course_day_id","enrollment_id","marked_by_user_id"): op.create_index(f"ix_attendance_{n}","attendance",[n])
    op.create_index("ix_attendance_org_course_day","attendance",["organization_id","course_day_id"]); op.create_index("ix_attendance_org_enrollment","attendance",["organization_id","enrollment_id"])

    op.create_table("grades",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE"),nullable=False), sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False),
        sa.Column("teacher_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")), sa.Column("source_type",sa.String(24),nullable=False,server_default="manual"), sa.Column("source_id",sa.Integer()),
        sa.Column("label",sa.String(255),nullable=False), sa.Column("score",sa.Float(),nullable=False), sa.Column("max_score",sa.Float(),nullable=False,server_default="20"), sa.Column("note",sa.Text(),nullable=False,server_default=""),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","session_id","enrollment_id","teacher_id"): op.create_index(f"ix_grades_{n}","grades",[n])
    op.create_index("ix_grades_org_session","grades",["organization_id","session_id"]); op.create_index("ix_grades_org_enrollment","grades",["organization_id","enrollment_id"]); op.create_index("ix_grades_source","grades",["organization_id","source_type","source_id"])

    op.create_table("class_discussion_posts",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE"),nullable=False), sa.Column("author_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("author_role",sa.String(16),nullable=False), sa.Column("body",sa.Text(),nullable=False,server_default=""), sa.Column("image_url",sa.String(1024)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","session_id","author_user_id"): op.create_index(f"ix_class_discussion_posts_{n}","class_discussion_posts",[n])
    op.create_index("ix_class_posts_org_session","class_discussion_posts",["organization_id","session_id"])

    op.create_table("class_discussion_replies",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("post_id",sa.Integer(),sa.ForeignKey("class_discussion_posts.id",ondelete="CASCADE"),nullable=False), sa.Column("author_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("author_role",sa.String(16),nullable=False), sa.Column("body",sa.Text(),nullable=False,server_default=""), sa.Column("image_url",sa.String(1024)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","post_id","author_user_id"): op.create_index(f"ix_class_discussion_replies_{n}","class_discussion_replies",[n])
    op.create_index("ix_class_replies_org_post","class_discussion_replies",["organization_id","post_id"])

    op.create_table("certificates",
        sa.Column("id",sa.Integer(),primary_key=True), sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("enrollment_id",sa.Integer(),sa.ForeignKey("enrollments.id",ondelete="CASCADE"),nullable=False), sa.Column("certificate_number",sa.String(80),nullable=False),
        sa.Column("student_name",sa.String(180),nullable=False), sa.Column("formation_title",sa.String(255),nullable=False), sa.Column("issued_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("status",sa.String(16),nullable=False,server_default="valid"), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("enrollment_id",name="uq_certificates_enrollment"), sa.UniqueConstraint("certificate_number",name="uq_certificates_number"))
    for n in ("organization_id","enrollment_id","certificate_number"): op.create_index(f"ix_certificates_{n}","certificates",[n],unique=(n in {"enrollment_id","certificate_number"}))
    op.create_index("ix_certificates_org_status","certificates",["organization_id","status"])

def downgrade() -> None:
    for table in ("certificates","class_discussion_replies","class_discussion_posts","grades","attendance","lesson_progress","quiz_attempts","quiz_questions","quizzes","resources"):
        op.drop_table(table)
