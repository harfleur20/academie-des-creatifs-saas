from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.workspace import StudentWorkspaceRead, TeacherWorkspaceRead
from app.services.tenancy import TenantContext
from app.services.workspace import get_student_workspace, get_teacher_workspace


router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/teacher", response_model=TeacherWorkspaceRead)
def teacher_workspace(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return get_teacher_workspace(db, tenant)


@router.get("/student", response_model=StudentWorkspaceRead)
def student_workspace(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return get_student_workspace(db, tenant)
