from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.entities import TimestampMixin


class OrganizationSlugAliasRecord(TimestampMixin, Base):
    __tablename__ = "organization_slug_aliases"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organization_slug_aliases_slug"),
        Index(
            "ix_organization_slug_aliases_org",
            "organization_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
