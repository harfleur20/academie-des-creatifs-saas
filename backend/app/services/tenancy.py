from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.membership_roles import effective_member_roles


@dataclass(frozen=True)
class TenantContext:
    organization: OrganizationRecord
    user: UserRecord
    membership: OrganizationMemberRecord | None
    support_mode: bool = False

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

    @property
    def organization_roles(self) -> frozenset[str]:
        if self.user.platform_role == "super_admin":
            return frozenset({"super_admin"})
        if self.membership is None:
            return frozenset()
        roles = set(effective_member_roles(self.membership))
        # The school owner can also use the teacher workspace by default.
        # Teacher readiness (profile and enabled charter) is still enforced by
        # the workspace gate before the teacher area opens.
        if "owner" in roles:
            roles.add("teacher")
        return frozenset(roles)

    def has_role(self, role: str) -> bool:
        return role in self.organization_roles


def resolve_tenant_context(
    db: Session,
    *,
    user: UserRecord,
    organization_id: int,
    support_mode: bool = False,
) -> TenantContext:
    organization = db.get(OrganizationRecord, organization_id)
    if (
        organization is None
        or not organization.is_active
        or organization.status not in {"active", "deletion_pending"}
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation introuvable.",
        )

    if user.platform_role == "super_admin":
        return TenantContext(
            organization=organization,
            user=user,
            membership=None,
            support_mode=support_mode,
        )

    membership = db.scalar(
        select(OrganizationMemberRecord)
        .options(selectinload(OrganizationMemberRecord.roles))
        .where(
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

    if organization.status == "deletion_pending":
        roles = effective_member_roles(membership)
        if support_mode or "owner" not in roles:
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

    if not tenant.organization_roles.intersection(roles):
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
