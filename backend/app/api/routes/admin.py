from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_super_admin
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.admin import AdminDashboardRead, AdminOrganizationRead
from app.services.admin import get_admin_dashboard, list_admin_organizations


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardRead)
def admin_dashboard(
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return get_admin_dashboard(db)


@router.get("/organizations", response_model=list[AdminOrganizationRead])
def admin_organizations(
    db: Session = Depends(get_db),
    _: UserRecord = Depends(get_super_admin),
):
    return list_admin_organizations(db)
