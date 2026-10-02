from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.assignments import *
from app.services.assignments import *
from app.services.assets import store_assignment_asset
from app.services.tenancy import TenantContext

router=APIRouter(prefix="/assignments",tags=["assignments"])

@router.get("/teacher/sessions/{session_id}",response_model=list[AssignmentRead])
def teacher_list(session_id:int,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_teacher_assignments(db,tenant,session_id)
@router.post("/teacher/sessions/{session_id}",response_model=AssignmentRead,status_code=201)
def teacher_create(session_id:int,payload:AssignmentCreate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return create_assignment(db,tenant,session_id,payload)
@router.get("/teacher/{assignment_id}/submissions",response_model=list[SubmissionRead])
def teacher_submissions(assignment_id:int,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_submissions(db,tenant,assignment_id)
@router.patch("/teacher/{assignment_id}/submissions/{submission_id}",response_model=SubmissionRead)
def teacher_review(assignment_id:int,submission_id:int,payload:ReviewSubmission,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return review_submission(db,tenant,assignment_id,submission_id,payload)
@router.get("/student",response_model=list[StudentAssignmentRead])
def student_list(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_student_assignments(db,tenant)
@router.post("/student/{assignment_id}/submit",response_model=StudentAssignmentRead)
def student_submit(assignment_id:int,payload:AssignmentSubmit,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return submit_assignment(db,tenant,assignment_id,payload)
@router.get("/{assignment_id}/enrollments/{enrollment_id}/comments",response_model=list[CommentRead])
def comments(assignment_id:int,enrollment_id:int,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_comments(db,tenant,assignment_id,enrollment_id)
@router.post("/{assignment_id}/enrollments/{enrollment_id}/comments",response_model=CommentRead,status_code=201)
def comment(assignment_id:int,enrollment_id:int,payload:CommentCreate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return add_comment(db,tenant,assignment_id,enrollment_id,payload)
@router.post("/assets",response_model=dict,status_code=201)
async def upload_asset(file:UploadFile=File(...),tenant:TenantContext=Depends(get_tenant_context)):
    if not tenant.organization_roles.intersection({"teacher","student"}): raise HTTPException(403,"Accès pédagogique requis.")
    return await store_assignment_asset(file,tenant.organization_id)
