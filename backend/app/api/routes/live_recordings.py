from __future__ import annotations

import json
from pathlib import Path

import jwt
import re

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import EnrollmentRecord, FormationSessionRecord, LiveRecordingRecord, SessionCourseDayRecord, UserRecord
from app.services.live_recordings import (
    PRIVATE_ROOT,
    capture_jaas_recording,
    download_jaas_recording,
    may_manage_recordings,
    may_view_recording,
    replay_stream_token,
    verify_jaas_signature,
)
from app.services.tenancy import TenantContext, resolve_tenant_context


router = APIRouter(prefix="/live-recordings", tags=["live-recordings"])


class LiveRecordingRead(BaseModel):
    id: int
    session_id: int
    course_day_id: int
    title: str
    description: str | None
    status: str
    duration_seconds: int | None
    uploaded_at: str | None
    is_published: bool
    download_allowed: bool
    content_url: str | None


class LiveRecordingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_published: bool | None = None
    download_allowed: bool | None = None


def _read(recording: LiveRecordingRecord, tenant: TenantContext) -> LiveRecordingRead:
    content_url = None
    if recording.status == "ready" and recording.storage_key:
        token = replay_stream_token(tenant, recording)
        content_url = f"{settings.backend_public_url}{settings.api_prefix}/live-recordings/{recording.id}/stream?token={token}"
    return LiveRecordingRead(
        id=recording.id,
        session_id=recording.session_id,
        course_day_id=recording.course_day_id,
        title=recording.title,
        description=recording.description,
        status=recording.status,
        duration_seconds=recording.duration_seconds,
        uploaded_at=recording.uploaded_at.isoformat() if recording.uploaded_at else None,
        is_published=recording.is_published,
        download_allowed=recording.download_allowed,
        content_url=content_url,
    )


@router.post("/jaas/webhook", status_code=202)
async def jaas_recording_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()
    if not settings.jaas_webhook_secret:
        raise HTTPException(503, "Secret webhook JaaS requis.")
    if not verify_jaas_signature(request.headers.get("X-Jaas-Signature", ""), body):
        raise HTTPException(401, "Signature JaaS invalide.")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Payload JaaS invalide.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(400, "Payload JaaS invalide.")
    recording = capture_jaas_recording(db, payload)
    if recording and settings.live_replay_download_enabled:
        background_tasks.add_task(download_jaas_recording, recording.id)
    return {"status": "received", "recording_id": recording.id if recording else None}


@router.get("/sessions/{session_id}", response_model=list[LiveRecordingRead])
def list_live_recordings(
    session_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> list[LiveRecordingRead]:
    session = db.scalar(select(FormationSessionRecord).where(
        FormationSessionRecord.id == session_id,
        FormationSessionRecord.organization_id == tenant.organization_id,
    ))
    if session is None:
        raise HTTPException(404, "Session introuvable.")
    manager = may_manage_recordings(db, tenant, session_id)
    if not manager:
        # The enrollment check is repeated on each media request.
        authorized = tenant.has_role("student") and db.scalar(select(EnrollmentRecord.id).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session_id,
            EnrollmentRecord.student_id == tenant.user.id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )) is not None
        if not authorized:
            raise HTTPException(403, "Accès à la session refusé.")
    rows = db.scalars(select(LiveRecordingRecord).where(
        LiveRecordingRecord.organization_id == tenant.organization_id,
        LiveRecordingRecord.session_id == session_id,
        LiveRecordingRecord.status != "archived",
    ).order_by(LiveRecordingRecord.uploaded_at.desc(), LiveRecordingRecord.id.desc())).all()
    if not manager:
        rows = [row for row in rows if may_view_recording(db, tenant, row)]
    return [_read(row, tenant) for row in rows]


@router.patch("/{recording_id}", response_model=LiveRecordingRead)
def update_live_recording(
    recording_id: int,
    payload: LiveRecordingUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> LiveRecordingRead:
    recording = db.scalar(select(LiveRecordingRecord).where(
        LiveRecordingRecord.id == recording_id,
        LiveRecordingRecord.organization_id == tenant.organization_id,
        LiveRecordingRecord.status != "archived",
    ))
    if recording is None:
        raise HTTPException(404, "Replay introuvable.")
    if not may_manage_recordings(db, tenant, recording.session_id):
        raise HTTPException(403, "Gestion des replays refusée.")
    if payload.is_published is True:
        day = db.get(SessionCourseDayRecord, recording.course_day_id)
        if recording.status != "ready" or not recording.storage_key or day is None or day.report_submitted_at is None:
            raise HTTPException(409, "Le replay sera publiable après la fin de séance et son stockage privé.")
    if payload.title is not None:
        title = payload.title.strip()
        if len(title) < 2:
            raise HTTPException(422, "Le titre doit contenir au moins deux caractères.")
        recording.title = title
    if payload.description is not None:
        recording.description = payload.description.strip() or None
    if payload.is_published is not None:
        recording.is_published = payload.is_published
    if payload.download_allowed is not None:
        if payload.download_allowed and recording.status != "ready":
            raise HTTPException(409, "Le téléchargement attend la fin du traitement.")
        recording.download_allowed = payload.download_allowed
    db.commit()
    db.refresh(recording)
    return _read(recording, tenant)


@router.post("/{recording_id}/retry", status_code=202)
def retry_live_recording(
    recording_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> dict:
    recording = db.scalar(select(LiveRecordingRecord).where(
        LiveRecordingRecord.id == recording_id,
        LiveRecordingRecord.organization_id == tenant.organization_id,
    ))
    if recording is None:
        raise HTTPException(404, "Replay introuvable.")
    if not may_manage_recordings(db, tenant, recording.session_id):
        raise HTTPException(403, "Gestion des replays refusée.")
    if recording.status != "failed" or not recording.source_url or not settings.live_replay_download_enabled:
        raise HTTPException(409, "Ce replay ne peut pas être relancé.")
    recording.status = "processing"
    db.commit()
    background_tasks.add_task(download_jaas_recording, recording.id)
    return {"status": "processing"}


@router.delete("/{recording_id}", status_code=204)
def archive_live_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> None:
    recording = db.scalar(select(LiveRecordingRecord).where(
        LiveRecordingRecord.id == recording_id,
        LiveRecordingRecord.organization_id == tenant.organization_id,
        LiveRecordingRecord.status != "archived",
    ))
    if recording is None:
        raise HTTPException(404, "Replay introuvable.")
    if not may_manage_recordings(db, tenant, recording.session_id):
        raise HTTPException(403, "Gestion des replays refusée.")
    recording.status = "archived"
    recording.is_published = False
    db.commit()


@router.get("/{recording_id}/stream")
def stream_live_recording(
    recording_id: int,
    token: str = Query(...),
    download: bool = False,
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
):
    try:
        claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(403, "Lien de replay expiré ou invalide.") from exc
    if claims.get("purpose") != "replay" or claims.get("rid") != recording_id:
        raise HTTPException(403, "Lien de replay invalide.")
    recording = db.get(LiveRecordingRecord, recording_id)
    user = db.get(UserRecord, claims.get("uid"))
    if recording is None or user is None or user.status != "active" or user.session_version != claims.get("ver"):
        raise HTTPException(404, "Replay introuvable.")
    if recording.organization_id != claims.get("oid") or recording.status != "ready" or not recording.storage_key:
        raise HTTPException(404, "Replay introuvable.")
    tenant = resolve_tenant_context(db, user=user, organization_id=recording.organization_id)
    if not may_view_recording(db, tenant, recording):
        raise HTTPException(403, "Accès au replay refusé.")
    if download and not (may_manage_recordings(db, tenant, recording.session_id) or recording.download_allowed):
        raise HTTPException(403, "Téléchargement non autorisé.")
    disposition = "attachment" if download else "inline"
    filename = f"replay-{recording.id}{Path(recording.storage_key).suffix}"
    if settings.storage_provider == "r2":
        if not settings.r2_private_bucket_name:
            raise HTTPException(503, "Stockage privé indisponible.")
        if isinstance(range_header, str) and not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", range_header):
            raise HTTPException(416, "Plage de lecture invalide.")
        import boto3
        client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url,
                              aws_access_key_id=settings.r2_access_key_id,
                              aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
        params = {"Bucket": settings.r2_private_bucket_name, "Key": recording.storage_key}
        if isinstance(range_header, str):
            params["Range"] = range_header
        try:
            stored = client.get_object(**params)
        except Exception as exc:
            raise HTTPException(502, "Fichier de replay indisponible.") from exc
        body = stored["Body"]

        def chunks():
            try:
                while chunk := body.read(1024 * 1024):
                    yield chunk
            finally:
                body.close()

        headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Content-Length": str(stored["ContentLength"]),
        }
        if stored.get("ContentRange"):
            headers["Content-Range"] = stored["ContentRange"]
        return StreamingResponse(
            chunks(), status_code=206 if isinstance(range_header, str) else 200,
            media_type=recording.content_type or "video/mp4", headers=headers,
        )
    path = PRIVATE_ROOT / recording.storage_key
    if not path.is_file():
        raise HTTPException(404, "Fichier de replay introuvable.")
    return FileResponse(path, media_type=recording.content_type or "video/mp4",
                        filename=filename, content_disposition_type=disposition)
