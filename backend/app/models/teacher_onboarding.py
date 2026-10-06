from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import OrganizationOwnedMixin, TimestampMixin


class TeacherProfessionalProfileRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "teacher_professional_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_teacher_professional_profiles_org_user",
        ),
        Index(
            "ix_teacher_professional_profiles_org_complete",
            "organization_id",
            "profile_completed_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    professional_title: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activity_domains: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    portfolio_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    portfolio_file_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    portfolio_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_file_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cv_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    behance_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    profile_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrganizationCharterRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "organization_charters"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "audience",
            name="uq_organization_charters_org_audience",
        ),
        Index(
            "ix_organization_charters_org_enabled",
            "organization_id",
            "is_enabled",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class OrganizationCharterAcceptanceRecord(OrganizationOwnedMixin, Base):
    __tablename__ = "organization_charter_acceptances"
    __table_args__ = (
        UniqueConstraint(
            "charter_id",
            "user_id",
            "version",
            name="uq_charter_acceptance_user_version",
        ),
        Index(
            "ix_charter_acceptances_org_user",
            "organization_id",
            "user_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    charter_id: Mapped[int] = mapped_column(
        ForeignKey("organization_charters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
