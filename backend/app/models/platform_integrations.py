from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformIntegrationPreferenceRecord(Base):
    __tablename__ = "platform_integration_preferences"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    badge_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="connect")
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
