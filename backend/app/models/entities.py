from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


ORGANIZATION_ROLES = {"owner", "admin", "manager", "teacher", "student"}
ORGANIZATION_MEMBER_STATUSES = {"active", "suspended"}
ORGANIZATION_INVITATION_STATUSES = {"pending", "accepted", "cancelled", "expired"}
SUBSCRIPTION_STATUSES = {
    "trialing",
    "active",
    "past_due",
    "suspended",
    "cancelled",
}
BILLING_INTERVALS = {"monthly", "annual"}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OrganizationOwnedMixin:
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class UserRecord(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(180), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    platform_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="user",
        index=True,
    )


class OrganizationRecord(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    name_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    subdomain: Mapped[str | None] = mapped_column(String(63), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contact_email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="fr-FR")
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#1768FF",
    )
    secondary_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#21C889",
    )
    accent_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#10233F",
    )

    members: Mapped[list["OrganizationMemberRecord"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list["SubscriptionRecord"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    domains: Mapped[list["OrganizationDomainRecord"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrganizationDomainRecord(TimestampMixin, Base):
    __tablename__ = "organization_domains"
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_organization_domains_hostname"),
        Index(
            "ix_organization_domains_org_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hostname: Mapped[str] = mapped_column(String(253), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    verification_token: Mapped[str] = mapped_column(String(96), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["OrganizationRecord"] = relationship(back_populates="domains")


class OrganizationMemberRecord(TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_members_org_user",
        ),
        Index("ix_organization_members_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    organization: Mapped["OrganizationRecord"] = relationship(back_populates="members")
    user: Mapped["UserRecord"] = relationship()


class OrganizationInvitationRecord(TimestampMixin, Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        Index(
            "ix_organization_invitations_org_email_status",
            "organization_id",
            "email",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanRecord(TimestampMixin, Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    monthly_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    entitlements: Mapped[list["PlanEntitlementRecord"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class PlanEntitlementRecord(TimestampMixin, Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature_key", name="uq_plan_entitlements_plan_feature"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    limit_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    plan: Mapped["PlanRecord"] = relationship(back_populates="entitlements")


class SubscriptionRecord(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="trialing", index=True)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(180), nullable=True)

    organization: Mapped["OrganizationRecord"] = relationship(back_populates="subscriptions")
    plan: Mapped["PlanRecord"] = relationship()


class UsageCounterRecord(TimestampMixin, Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "metric_key",
            "window_key",
            name="uq_usage_counter_org_metric_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    window_key: Mapped[str] = mapped_column(String(40), nullable=False, default="lifetime")
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)



class BillingInvoiceRecord(TimestampMixin, Base):
    __tablename__ = "billing_invoices"
    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_billing_invoices_number"),
        UniqueConstraint(
            "payment_attempt_id",
            name="uq_billing_invoices_payment_attempt",
        ),
        Index(
            "ix_billing_invoices_org_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey("billing_payment_attempts.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="open",
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["PlanRecord"] = relationship()
    subscription: Mapped["SubscriptionRecord | None"] = relationship()


class BillingPaymentAttemptRecord(TimestampMixin, Base):
    __tablename__ = "billing_payment_attempts"
    __table_args__ = (
        Index(
            "ix_billing_payment_attempts_org_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billing_interval: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="monthly",
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider_reference: Mapped[str] = mapped_column(
        String(180),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(180),
        unique=True,
        nullable=True,
        index=True,
    )
    activated_subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    plan: Mapped["PlanRecord"] = relationship()
    activated_subscription: Mapped["SubscriptionRecord | None"] = relationship()


class PlatformAdminAuditRecord(TimestampMixin, Base):
    __tablename__ = "platform_admin_audit_logs"
    __table_args__ = (
        Index("ix_platform_admin_audit_org_created", "organization_id", "created_at"),
        Index("ix_platform_admin_audit_actor_created", "actor_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    actor: Mapped["UserRecord | None"] = relationship()


class OrganizationPlanOverrideRecord(TimestampMixin, Base):
    __tablename__ = "organization_plan_overrides"
    __table_args__ = (
        Index(
            "ix_organization_plan_overrides_org_status_end",
            "organization_id",
            "status",
            "ends_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    granted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["PlanRecord"] = relationship()
    granted_by: Mapped["UserRecord | None"] = relationship()


class PlatformSupportSessionRecord(TimestampMixin, Base):
    __tablename__ = "platform_support_sessions"
    __table_args__ = (
        Index(
            "ix_platform_support_sessions_actor_end",
            "actor_user_id",
            "ended_at",
        ),
        Index(
            "ix_platform_support_sessions_org_expiry",
            "organization_id",
            "expires_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    actor: Mapped["UserRecord"] = relationship()


class FormationRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "formations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_formations_organization_slug",
        ),
        Index(
            "ix_formations_organization_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    level: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    format_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ligne")
    training_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    sessions: Mapped[list["FormationSessionRecord"]] = relationship(
        back_populates="formation",
        cascade="all, delete-orphan",
    )


class FormationSessionRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "formation_sessions"
    __table_args__ = (
        Index("ix_formation_sessions_org_formation", "organization_id", "formation_id"),
        Index("ix_formation_sessions_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    formation_id: Mapped[int] = mapped_column(
        ForeignKey("formations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=False)
    campus_label: Mapped[str | None] = mapped_column(String(180), nullable=True)
    seat_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")

    formation: Mapped["FormationRecord"] = relationship(back_populates="sessions")
    teachers: Mapped[list["SessionTeacherRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[list["EnrollmentRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    courses: Mapped[list["CourseRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class SessionTeacherRecord(OrganizationOwnedMixin, Base):
    __tablename__ = "session_teachers"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "teacher_id",
            name="uq_session_teachers_session_teacher",
        ),
        Index("ix_session_teachers_org_session", "organization_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("formation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="intervenant")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped["FormationSessionRecord"] = relationship(back_populates="teachers")
    teacher: Mapped["UserRecord"] = relationship()


class EnrollmentRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "student_id",
            name="uq_enrollments_session_student",
        ),
        Index("ix_enrollments_org_session", "organization_id", "session_id"),
        Index("ix_enrollments_org_student", "organization_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("formation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")

    session: Mapped["FormationSessionRecord"] = relationship(back_populates="enrollments")
    student: Mapped["UserRecord"] = relationship()


class CourseRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_org_session", "organization_id", "session_id"),
        Index("ix_courses_org_status", "organization_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("formation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")

    session: Mapped["FormationSessionRecord"] = relationship(back_populates="courses")
    teacher: Mapped["UserRecord | None"] = relationship()
    chapters: Mapped[list["ChapterRecord"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="ChapterRecord.order_index",
    )


class ChapterRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        Index("ix_chapters_org_course", "organization_id", "course_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    course: Mapped["CourseRecord"] = relationship(back_populates="chapters")
    lessons: Mapped[list["LessonRecord"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="LessonRecord.order_index",
    )


class LessonRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (
        Index("ix_lessons_org_chapter", "organization_id", "chapter_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lesson_type: Mapped[str] = mapped_column(String(24), nullable=False, default="text")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    chapter: Mapped["ChapterRecord"] = relationship(back_populates="lessons")
