from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.formations import FormationCreate, FormationRead
from app.services.formations import (
    FormationConflictError,
    create_formation,
    get_formation,
    list_formations,
)
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/formations", tags=["formations"])


@router.get("", response_model=list[FormationRead])
def list_formations_route(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_formations(db, tenant)


@router.get("/{formation_id}", response_model=FormationRead)
def get_formation_route(
    formation_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    formation = get_formation(db, tenant, formation_id)
    if formation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formation introuvable.",
        )
    return formation


@router.post(
    "",
    response_model=FormationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_formation_route(
    payload: FormationCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    try:
        return create_formation(db, tenant, payload)
    except FormationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
