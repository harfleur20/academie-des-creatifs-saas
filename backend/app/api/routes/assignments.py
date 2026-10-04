import mimetypes
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import AssignmentRecord, AssignmentSubmissionRecord, EnrollmentRecord, ResourceRecord, SessionTeacherRecord
from app.schemas.assignments import *
from app.services.assignments import *
from app.services.assets import ALLOWED, store_assignment_asset, store_submission_asset
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
    if not tenant.has_role("teacher") or tenant.support_mode: raise HTTPException(403,"Accès professeur requis.")
    return await store_assignment_asset(file,tenant.organization_id)


@router.get("/resource-assets/{filename}")
def download_resource_asset(
    filename: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]+", filename) or Path(filename).suffix not in ALLOWED:
        raise HTTPException(404, "Fichier introuvable.")
    current_suffix = f"{settings.api_prefix}/assignments/resource-assets/{filename}"
    legacy_suffix = f"/schools/{tenant.organization_id}/assignments/{filename}"
    resources = db.scalars(select(ResourceRecord).where(
        ResourceRecord.organization_id == tenant.organization_id,
        (ResourceRecord.url.like(f"%{current_suffix}")) | (ResourceRecord.url.like(f"%{legacy_suffix}")),
    )).all()
    if not resources:
        raise HTTPException(404, "Ressource introuvable.")
    allowed = bool(tenant.organization_roles.intersection({"owner", "admin", "manager"}))
    if not allowed and tenant.has_role("teacher"):
        session_ids = {row.session_id for row in resources}
        allowed = db.scalar(select(SessionTeacherRecord.id).where(
            SessionTeacherRecord.organization_id == tenant.organization_id,
            SessionTeacherRecord.session_id.in_(session_ids),
            SessionTeacherRecord.teacher_id == tenant.user.id,
        )) is not None
    if not allowed and tenant.has_role("student"):
        published_session_ids = {row.session_id for row in resources if row.published_at and row.published_at.replace(tzinfo=row.published_at.tzinfo or UTC) <= datetime.now(UTC)}
        if published_session_ids:
            allowed = db.scalar(select(EnrollmentRecord.id).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.session_id.in_(published_session_ids),
                EnrollmentRecord.student_id == tenant.user.id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )) is not None
    if not allowed:
        raise HTTPException(403, "Accès à cette ressource refusé.")

    legacy = any(row.url.endswith(legacy_suffix) for row in resources)
    key = f"schools/{tenant.organization_id}/{'assignments' if legacy else 'resources'}/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": f'attachment; filename="{filename}"'}
    if settings.storage_provider == "r2":
        import boto3
        from botocore.exceptions import ClientError
        bucket = settings.r2_bucket_name if legacy else settings.r2_private_bucket_name
        if not bucket:
            raise HTTPException(503, "Stockage indisponible.")
        client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url, aws_access_key_id=settings.r2_access_key_id, aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
        try:
            body = client.get_object(Bucket=bucket, Key=key)["Body"]
        except ClientError as exc:
            raise HTTPException(404, "Fichier introuvable.") from exc
        return StreamingResponse(body.iter_chunks(), media_type=content_type, headers=headers)
    root = Path(__file__).resolve().parents[3] / ("uploads" if legacy else "private_uploads")
    path = root / key
    if not path.is_file():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(path, media_type=content_type, headers=headers)


@router.post("/submission-assets", response_model=dict, status_code=201)
async def upload_submission_asset(file: UploadFile = File(...), tenant: TenantContext = Depends(get_tenant_context)):
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")
    return await store_submission_asset(file, tenant.organization_id, tenant.user.id)


@router.get("/submission-assets/{uploader_id}/{filename}")
def download_submission_asset(
    uploader_id: int,
    filename: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]+", filename) or Path(filename).suffix not in ALLOWED:
        raise HTTPException(404, "Fichier introuvable.")
    asset_path = f"{settings.api_prefix}/assignments/submission-assets/{uploader_id}/{filename}"
    allowed = tenant.user.id == uploader_id
    if not allowed and tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        allowed = db.scalar(select(AssignmentSubmissionRecord.id).where(
            AssignmentSubmissionRecord.organization_id == tenant.organization_id,
            AssignmentSubmissionRecord.file_url.like(f"%{asset_path}"),
        )) is not None
    if not allowed and tenant.has_role("teacher"):
        allowed = db.scalar(select(AssignmentSubmissionRecord.id).join(
            AssignmentRecord, AssignmentRecord.id == AssignmentSubmissionRecord.assignment_id,
        ).where(
            AssignmentSubmissionRecord.organization_id == tenant.organization_id,
            AssignmentSubmissionRecord.file_url.like(f"%{asset_path}"),
            AssignmentRecord.teacher_id == tenant.user.id,
        )) is not None
    if not allowed:
        raise HTTPException(403, "Accès à ce fichier refusé.")
    key = f"schools/{tenant.organization_id}/assignments/{uploader_id}/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": f'attachment; filename="{filename}"'}
    if settings.storage_provider == "r2":
        if not settings.r2_private_bucket_name:
            raise HTTPException(503, "Stockage privé indisponible.")
        import boto3
        from botocore.exceptions import ClientError
        client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url, aws_access_key_id=settings.r2_access_key_id, aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
        try:
            body = client.get_object(Bucket=settings.r2_private_bucket_name, Key=key)["Body"]
        except ClientError as exc:
            raise HTTPException(404, "Fichier introuvable.") from exc
        return StreamingResponse(body.iter_chunks(), media_type=content_type, headers=headers)
    path = Path(__file__).resolve().parents[3] / "private_uploads" / key
    if not path.is_file():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(path, media_type=content_type, headers=headers)


@router.get("/legacy-submissions/{filename}")
def download_legacy_submission(
    filename: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if not re.fullmatch(r"[a-f0-9]{32}\.[a-z0-9]+", filename) or Path(filename).suffix not in ALLOWED:
        raise HTTPException(404, "Fichier introuvable.")
    rows = db.execute(select(AssignmentSubmissionRecord, AssignmentRecord, EnrollmentRecord)
        .join(AssignmentRecord, AssignmentRecord.id == AssignmentSubmissionRecord.assignment_id)
        .join(EnrollmentRecord, EnrollmentRecord.id == AssignmentSubmissionRecord.enrollment_id)
        .where(
            AssignmentSubmissionRecord.organization_id == tenant.organization_id,
            AssignmentSubmissionRecord.file_url.like(f"%/{filename}"),
        )).all()
    allowed = any(
        enrollment.student_id == tenant.user.id
        or (tenant.has_role("teacher") and assignment.teacher_id == tenant.user.id)
        or tenant.organization_roles.intersection({"owner", "admin", "manager"})
        for _submission, assignment, enrollment in rows
    )
    if not allowed:
        raise HTTPException(403, "Accès à ce fichier refusé.")
    key = f"schools/{tenant.organization_id}/assignments/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": f'attachment; filename="{filename}"'}
    if settings.storage_provider == "r2":
        import boto3
        from botocore.exceptions import ClientError
        client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url, aws_access_key_id=settings.r2_access_key_id, aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
        body = None
        for bucket in (settings.r2_private_bucket_name, settings.r2_bucket_name):
            if not bucket:
                continue
            try:
                body = client.get_object(Bucket=bucket, Key=key)["Body"]
                break
            except ClientError:
                continue
        if body is None:
            raise HTTPException(404, "Fichier introuvable.")
        return StreamingResponse(body.iter_chunks(), media_type=content_type, headers=headers)
    root = Path(__file__).resolve().parents[3]
    path = root / "private_uploads" / key
    if not path.is_file():
        path = root / "uploads" / key
    if not path.is_file():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(path, media_type=content_type, headers=headers)
