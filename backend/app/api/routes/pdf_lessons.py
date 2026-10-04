"""Private PDF lesson upload, reader and per-page progress."""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.services.pdf_lessons import pdf_bytes, read_pdf_progress, report_pdf_page, store_pdf_asset
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/academic", tags=["academic-pdf"])


class PdfPageEvent(BaseModel):
    page: int = Field(gt=0)
    event: str = Field(pattern="^(open|confirm)$")


class PdfProgressRead(BaseModel):
    page_count: int
    viewed_pages: list[int]
    viewed_pct: float
    last_page: int
    quiz_unlocked: bool
    is_completed: bool


@router.post("/teacher/pdf-assets", status_code=201)
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    asset = await store_pdf_asset(db, tenant, file)
    return {"source_url": asset.source_url, "page_count": asset.page_count}


@router.get("/student/lessons/{lesson_id}/pdf-file")
def read_pdf_file(lesson_id: int, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return Response(content=pdf_bytes(db, tenant, lesson_id), media_type="application/pdf", headers={"Cache-Control": "private, no-store", "Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})


@router.get("/student/lessons/{lesson_id}/pdf-progress", response_model=PdfProgressRead)
def get_progress(lesson_id: int, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return read_pdf_progress(db, tenant, lesson_id)


@router.post("/student/lessons/{lesson_id}/pdf-progress", response_model=PdfProgressRead)
def report_progress(lesson_id: int, payload: PdfPageEvent, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return report_pdf_page(db, tenant, lesson_id, payload.page, payload.event)
