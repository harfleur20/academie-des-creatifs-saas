"""The student's transcript: on screen and as a PDF (app/services/transcripts.py)."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.transcripts import TranscriptRead, TranscriptSummaryRead
from app.services.school_branding import branding_snapshot
from app.services.tenancy import TenantContext
from app.services.transcript_pdf import build_transcript_pdf
from app.services.transcripts import build_transcript, my_transcripts, readable_enrollment

router = APIRouter(prefix="/transcripts", tags=["transcripts"])


@router.get("/mine", response_model=list[TranscriptSummaryRead])
def list_my_transcripts(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return my_transcripts(db, tenant)


@router.get("/{enrollment_id}", response_model=TranscriptRead)
def read_transcript(
    enrollment_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return build_transcript(db, tenant, readable_enrollment(db, tenant, enrollment_id))


@router.get("/{enrollment_id}/pdf")
def download_transcript(
    enrollment_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    transcript = build_transcript(db, tenant, readable_enrollment(db, tenant, enrollment_id))
    snapshot = branding_snapshot(db, tenant.organization)
    filename, content = build_transcript_pdf(
        transcript,
        primary_color=snapshot.get("primary_color"),
        secondary_color=snapshot.get("secondary_color"),
        signature_url=snapshot.get("signature_url"),
        stamp_url=snapshot.get("stamp_url"),
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
