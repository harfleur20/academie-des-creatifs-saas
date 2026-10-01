from __future__ import annotations

from datetime import datetime

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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
