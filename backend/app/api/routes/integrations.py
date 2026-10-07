from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.integrations import OpenAIIntegrationRead, OpenAIIntegrationWrite
from app.services.organization_integrations import (
    OPENAI_PROVIDER,
    delete_openai_integration,
    get_integration,
    save_openai_integration,
    test_saved_openai_integration,
)
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/integrations", tags=["integrations"])


def _read(record) -> OpenAIIntegrationRead:
    if record is None:
        return OpenAIIntegrationRead(
            connected=False,
            status="disconnected",
        )
    return OpenAIIntegrationRead(
        connected=record.status == "connected",
        status=record.status,
        model=record.model,
        connected_at=record.connected_at,
        last_tested_at=record.last_tested_at,
        last_error=record.last_error,
    )


@router.get("/openai", response_model=OpenAIIntegrationRead)
def get_openai_integration_route(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")
    return _read(get_integration(db, tenant, OPENAI_PROVIDER))


@router.put("/openai", response_model=OpenAIIntegrationRead)
def save_openai_integration_route(
    payload: OpenAIIntegrationWrite,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return _read(
        save_openai_integration(
            db,
            tenant,
            api_key=payload.api_key,
            model=payload.model,
        )
    )


@router.post("/openai/test", response_model=OpenAIIntegrationRead)
def test_openai_integration_route(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return _read(test_saved_openai_integration(db, tenant))


@router.delete("/openai", status_code=status.HTTP_204_NO_CONTENT)
def delete_openai_integration_route(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    delete_openai_integration(db, tenant)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
