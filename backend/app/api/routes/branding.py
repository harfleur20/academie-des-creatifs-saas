from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.services.school_branding import branding_snapshot
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/branding", tags=["branding"])


@router.get("/current")
def get_current_school_branding(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Return the display identity shared by public, teacher and student spaces.

    This intentionally exposes only visual identity fields. Legal, billing and
    communication configuration remains restricted to management endpoints.
    """
    snapshot = branding_snapshot(db, tenant.organization)
    return {
        "organization_id": snapshot["organization_id"],
        "school_name": snapshot["school_name"],
        "logo_url": snapshot["logo_url"],
        "primary_color": snapshot["primary_color"],
        "secondary_color": snapshot["secondary_color"],
        "accent_color": snapshot["accent_color"],
    }
