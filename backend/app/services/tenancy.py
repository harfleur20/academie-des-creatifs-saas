from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)


@dataclass(frozen=True)
class TenantContext:
    organization: OrganizationRecord
    user: UserRecord
    membership: OrganizationMemberRecord | None

    @property
    def organization_id(self) -> int:
        return self.organization.id

    @property
    def organization_role(self) -> str:
        if self.user.platform_role == "super_admin":
            return "super_admin"
        if self.membership is None:
            return ""
        return self.membership.role


def resolve_tenant_context(
    db: Session,
    *,
    user: UserRecord,
    organization_id: int,
) -> TenantContext:
    organization = db.get(OrganizationRecord, organization_id)
    if organization is None or not organization.is_active or organization.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation introuvable.",
        )

    if user.platform_role == "super_admin":
        return TenantContext(organization=organization, user=user, membership=None)

    membership = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == organization_id,
            OrganizationMemberRecord.user_id == user.id,
            OrganizationMemberRecord.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation introuvable.",
        )

    return TenantContext(
        organization=organization,
        user=user,
        membership=membership,
    )


def require_organization_roles(
    tenant: TenantContext,
    *roles: str,
) -> TenantContext:
    if tenant.user.platform_role == "super_admin":
        return tenant

    if tenant.organization_role not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission insuffisante dans cette organisation.",
        )
    return tenant


T = TypeVar("T")


def scoped_select(model: type[T], tenant: TenantContext) -> Select[tuple[T]]:
    organization_column = getattr(model, "organization_id", None)
    if organization_column is None:
        raise TypeError(
            f"{model.__name__} n'est pas une ressource rattachée à une organisation."
        )
    return select(model).where(organization_column == tenant.organization_id)
