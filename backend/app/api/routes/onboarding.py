from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.onboarding import OnboardingStatusRead
from app.services.onboarding import get_onboarding_status
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusRead)
def onboarding_status(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return get_onboarding_status(db, tenant)
