from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import OrganizationOwnedMixin, TimestampMixin


class OrganizationIntegrationRecord(OrganizationOwnedMixin, TimestampMixin, Base):
    __tablename__ = "organization_integrations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            name="uq_org_integrations_org_provider",
        ),
        Index(
            "ix_org_integrations_org_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="connected")
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="gpt-6-luna")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
