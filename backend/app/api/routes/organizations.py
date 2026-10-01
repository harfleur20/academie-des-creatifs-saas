from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_tenant_context
from app.db.session import get_db
from app.models.entities import OrganizationMemberRecord, UserRecord
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationMemberCreate,
    OrganizationMemberRead,
    OrganizationRead,
)
from app.services.organizations import (
    OrganizationConflictError,
    create_organization,
    list_user_organizations,
)
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
def list_organizations_route(
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
):
    return list_user_organizations(db, current_user)


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_route(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
):
    try:
        return create_organization(db, user=current_user, payload=payload)
    except OrganizationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/current", response_model=OrganizationRead)
def get_current_organization(
    tenant: TenantContext = Depends(get_tenant_context),
):
    return tenant.organization


@router.get("/current/members", response_model=list[OrganizationMemberRead])
def list_current_members(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return list(
        db.scalars(
            select(OrganizationMemberRecord)
            .where(
                OrganizationMemberRecord.organization_id == tenant.organization_id,
                OrganizationMemberRecord.status == "active",
            )
            .order_by(OrganizationMemberRecord.id)
        ).all()
    )


@router.post(
    "/current/members",
    response_model=OrganizationMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_current_member(
    payload: OrganizationMemberCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin")

    existing = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == tenant.organization_id,
            OrganizationMemberRecord.user_id == payload.user_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet utilisateur appartient déjà à cette organisation.",
        )

    user = db.get(UserRecord, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    member = OrganizationMemberRecord(
        organization_id=tenant.organization_id,
        user_id=user.id,
        role=payload.role,
        status="active",
    )
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible d'ajouter ce membre.",
        ) from exc
    db.refresh(member)
    return member
