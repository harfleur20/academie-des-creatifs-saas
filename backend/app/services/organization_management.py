from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    OrganizationInvitationRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.membership_roles import (
    FUNCTIONAL_ROLES,
    effective_member_roles,
    replace_effective_roles,
    replace_functional_roles,
    sync_primary_role,
)
from app.schemas.organizations import (
    OrganizationInvitationCreate,
    OrganizationMemberFunctionalRolesUpdate,
    OrganizationMemberUpdate,
    OrganizationUpdate,
)
from app.services.tenancy import TenantContext


INVITATION_TTL_DAYS = 7


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _active_owner_count(db: Session, organization_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(OrganizationMemberRecord.id)).where(
                OrganizationMemberRecord.organization_id == organization_id,
                OrganizationMemberRecord.role == "owner",
                OrganizationMemberRecord.status == "active",
            )
        )
        or 0
    )


def _actor_role(tenant: TenantContext) -> str:
    if tenant.user.platform_role == "super_admin":
        return "super_admin"
    return tenant.organization_role


def _can_assign_role(actor_role: str, role: str) -> bool:
    if actor_role in {"super_admin", "owner"}:
        return role in {"owner", "admin", "manager", "teacher", "student"}
    if actor_role == "admin":
        return role in {"manager", "teacher", "student"}
    if actor_role == "manager":
        return role in {"teacher", "student"}
    return False


def _can_manage_member(actor_role: str, target_role: str) -> bool:
    if actor_role == "super_admin":
        return True
    if actor_role == "owner":
        return True
    if actor_role == "admin":
        return target_role in {"manager", "teacher", "student"}
    if actor_role == "manager":
        return target_role in {"teacher", "student"}
    return False


def _reload_member(
    db: Session,
    member_id: int,
) -> OrganizationMemberRecord:
    return db.scalar(
        select(OrganizationMemberRecord)
        .options(
            selectinload(OrganizationMemberRecord.user),
            selectinload(OrganizationMemberRecord.roles),
        )
        .where(OrganizationMemberRecord.id == member_id)
    )


def update_organization_settings(
    db: Session,
    tenant: TenantContext,
    payload: OrganizationUpdate,
) -> OrganizationRecord:
    actor_role = _actor_role(tenant)
    if actor_role not in {"super_admin", "owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission insuffisante pour modifier l'école.",
        )

    values = payload.model_dump(exclude_unset=True)

    requested_name = values.get("name")
    if requested_name is not None:
        normalized_name = requested_name.strip()
        if normalized_name != tenant.organization.name:
            if actor_role not in {"super_admin", "owner"}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Seul le propriétaire de l'école peut modifier son nom.",
                )

            if (
                actor_role != "super_admin"
                and tenant.organization.name_changed_at is not None
            ):
                last_change = _aware_utc(tenant.organization.name_changed_at)
                next_change = last_change + timedelta(
                    days=settings.organization_name_change_cooldown_days
                )
                now = _utc_now()
                if now < next_change:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Le nom de l'école ne peut être modifié qu'une fois "
                            f"tous les {settings.organization_name_change_cooldown_days} jours. "
                            "Prochain changement possible à partir du "
                            f"{next_change.strftime('%d/%m/%Y à %H:%M UTC')}."
                        ),
                    )

            values["name"] = normalized_name
            tenant.organization.name_changed_at = _utc_now()

    for key, value in values.items():
        if value is not None and key == "logo_url":
            value = str(value)
        if isinstance(value, str):
            value = value.strip()
        if key in {"primary_color", "secondary_color", "accent_color"} and value:
            value = value.upper()
        setattr(tenant.organization, key, value)

    db.commit()
    db.refresh(tenant.organization)
    return tenant.organization


def add_member(
    db: Session,
    tenant: TenantContext,
    *,
    user: UserRecord,
    role: str,
) -> OrganizationMemberRecord:
    actor_role = _actor_role(tenant)
    if not _can_assign_role(actor_role, role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas attribuer ce rôle.",
        )

    existing = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == tenant.organization_id,
            OrganizationMemberRecord.user_id == user.id,
        )
    )
    if existing is not None:
        if existing.status == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet utilisateur appartient déjà à cette école.",
            )
        existing.role = role
        existing.status = "active"
        replace_effective_roles(db, existing, {role})
        db.commit()
        return _reload_member(db, existing.id)

    member = OrganizationMemberRecord(
        organization_id=tenant.organization_id,
        user_id=user.id,
        role=role,
        status="active",
    )
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {role})
    db.commit()
    return _reload_member(db, member.id)


def update_member(
    db: Session,
    tenant: TenantContext,
    member_id: int,
    payload: OrganizationMemberUpdate,
) -> OrganizationMemberRecord:
    member = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.id == member_id,
            OrganizationMemberRecord.organization_id == tenant.organization_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membre introuvable.",
        )

    actor_role = _actor_role(tenant)
    if not _can_manage_member(actor_role, member.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas modifier ce membre.",
        )

    new_role = payload.role or member.role
    new_status = payload.status or member.status

    if payload.role is not None and not _can_assign_role(actor_role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas attribuer ce rôle.",
        )

    removes_active_owner = (
        member.role == "owner"
        and member.status == "active"
        and (new_role != "owner" or new_status != "active")
    )
    if removes_active_owner and _active_owner_count(db, tenant.organization_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="L'école doit conserver au moins un propriétaire actif.",
        )

    previous_role = member.role
    member.role = new_role
    member.status = new_status
    sync_primary_role(
        db,
        member,
        previous_primary_role=previous_role,
    )
    db.commit()
    return _reload_member(db, member.id)


def update_member_functional_roles(
    db: Session,
    tenant: TenantContext,
    member_id: int,
    payload: OrganizationMemberFunctionalRolesUpdate,
) -> OrganizationMemberRecord:
    member = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.id == member_id,
            OrganizationMemberRecord.organization_id == tenant.organization_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membre introuvable.",
        )

    actor_role = _actor_role(tenant)
    if not _can_manage_member(actor_role, member.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas modifier les accès de ce membre.",
        )

    requested = set(payload.functional_roles)
    invalid = requested - FUNCTIONAL_ROLES
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Les accès fonctionnels autorisés sont teacher et student.",
        )

    replace_functional_roles(db, member, requested)
    db.commit()
    return _reload_member(db, member.id)


def create_invitation(
    db: Session,
    tenant: TenantContext,
    payload: OrganizationInvitationCreate,
) -> tuple[OrganizationInvitationRecord, str]:
    actor_role = _actor_role(tenant)
    if not _can_assign_role(actor_role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas inviter ce rôle.",
        )

    email = _normalize_email(str(payload.email))

    existing_user = db.scalar(
        select(UserRecord).where(func.lower(UserRecord.email) == email)
    )
    if existing_user is not None:
        existing_member = db.scalar(
            select(OrganizationMemberRecord).where(
                OrganizationMemberRecord.organization_id == tenant.organization_id,
                OrganizationMemberRecord.user_id == existing_user.id,
                OrganizationMemberRecord.status == "active",
            )
        )
        if existing_member is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet utilisateur appartient déjà à cette école.",
            )

    pending = db.scalar(
        select(OrganizationInvitationRecord).where(
            OrganizationInvitationRecord.organization_id == tenant.organization_id,
            func.lower(OrganizationInvitationRecord.email) == email,
            OrganizationInvitationRecord.status == "pending",
            OrganizationInvitationRecord.expires_at > _utc_now(),
        )
    )
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une invitation valide existe déjà pour cette adresse.",
        )

    token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitationRecord(
        organization_id=tenant.organization_id,
        email=email,
        role=payload.role,
        token_hash=_token_hash(token),
        status="pending",
        invited_by_user_id=tenant.user.id,
        expires_at=_utc_now() + timedelta(days=INVITATION_TTL_DAYS),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation, token


def list_invitations(
    db: Session,
    tenant: TenantContext,
) -> list[OrganizationInvitationRecord]:
    if _actor_role(tenant) not in {"super_admin", "owner", "admin", "manager"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission insuffisante.",
        )

    return list(
        db.scalars(
            select(OrganizationInvitationRecord)
            .where(
                OrganizationInvitationRecord.organization_id == tenant.organization_id,
            )
            .order_by(OrganizationInvitationRecord.created_at.desc())
        ).all()
    )


def cancel_invitation(
    db: Session,
    tenant: TenantContext,
    invitation_id: int,
) -> OrganizationInvitationRecord:
    invitation = db.scalar(
        select(OrganizationInvitationRecord).where(
            OrganizationInvitationRecord.id == invitation_id,
            OrganizationInvitationRecord.organization_id == tenant.organization_id,
        )
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation introuvable.",
        )

    actor_role = _actor_role(tenant)
    if not _can_assign_role(actor_role, invitation.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez pas annuler cette invitation.",
        )

    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette invitation n'est plus en attente.",
        )

    invitation.status = "cancelled"
    invitation.cancelled_at = _utc_now()
    db.commit()
    db.refresh(invitation)
    return invitation


def accept_invitation(
    db: Session,
    *,
    current_user: UserRecord,
    token: str,
) -> tuple[OrganizationRecord, OrganizationMemberRecord]:
    invitation = db.scalar(
        select(OrganizationInvitationRecord).where(
            OrganizationInvitationRecord.token_hash == _token_hash(token),
        )
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation introuvable.",
        )

    now = _utc_now()
    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette invitation n'est plus valide.",
        )

    if _aware_utc(invitation.expires_at) <= now:
        invitation.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Cette invitation a expiré.",
        )

    if _normalize_email(current_user.email) != _normalize_email(invitation.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette invitation a été envoyée à une autre adresse email.",
        )

    organization = db.get(OrganizationRecord, invitation.organization_id)
    if organization is None or not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="École introuvable.",
        )

    membership = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == invitation.organization_id,
            OrganizationMemberRecord.user_id == current_user.id,
        )
    )
    if membership is None:
        membership = OrganizationMemberRecord(
            organization_id=invitation.organization_id,
            user_id=current_user.id,
            role=invitation.role,
            status="active",
        )
        db.add(membership)
    else:
        membership.role = invitation.role
        membership.status = "active"

    replace_effective_roles(db, membership, {invitation.role})

    invitation.status = "accepted"
    invitation.accepted_by_user_id = current_user.id
    invitation.accepted_at = now

    db.commit()
    db.refresh(organization)
    return organization, _reload_member(db, membership.id)
