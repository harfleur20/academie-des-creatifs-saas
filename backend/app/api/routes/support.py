from __future__ import annotations

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.dependencies import get_tenant_context
from app.core.config import settings
from app.schemas.support import SupportRequestCreate, SupportRequestRead
from app.services.support_mail import send_support_request_email
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/support", tags=["support"])


def _support_reference() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"SUP-{stamp}-{secrets.token_hex(3).upper()}"


@router.post("/requests", response_model=SupportRequestRead, status_code=status.HTTP_202_ACCEPTED)
def create_support_request(
    payload: SupportRequestCreate,
    background_tasks: BackgroundTasks,
    tenant: TenantContext = Depends(get_tenant_context),
) -> SupportRequestRead:
    recipient = settings.support_email or settings.smtp_from
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le support par e-mail n’est pas encore configuré.",
        )

    reference = _support_reference()
    background_tasks.add_task(
        send_support_request_email,
        recipient=recipient,
        reference=reference,
        requester_name=tenant.user.full_name,
        requester_email=tenant.user.email,
        organization_name=tenant.organization.name,
        organization_id=tenant.organization.id,
        category=payload.category,
        priority=payload.priority,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        page_url=payload.page_url,
    )
    return SupportRequestRead(
        reference=reference,
        message="Votre demande a bien été transmise au support.",
    )
