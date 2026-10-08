"""Tenant-scoped JaaS replay capture and private delivery."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import logging
import os
import re
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
import jwt
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import (
    EnrollmentRecord,
    FormationSessionRecord,
    LiveRecordingRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
)
from app.services.tenancy import TenantContext


ROOM_PATTERN = re.compile(r"^school-(\d+)-session-(\d+)-day-(\d+)$")
MAX_REPLAY_BYTES = 2 * 1024 * 1024 * 1024
PRIVATE_ROOT = Path(__file__).resolve().parents[2] / "private_uploads"
logger = logging.getLogger(__name__)


def verify_jaas_signature(header: str, body: bytes) -> bool:
    if not settings.jaas_webhook_secret:
        return False
    parts = [part.strip().split("=", 1) for part in header.split(",") if "=" in part]
    timestamp = next((value for key, value in parts if key == "t"), None)
    signatures = [value for key, value in parts if key == "v1"]
    if not timestamp or not signatures:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    digest = hmac.new(
        settings.jaas_webhook_secret.encode(),
        timestamp.encode() + b"." + body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def _source_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if parsed.hostname == "localhost" or parsed.hostname.endswith((".local", ".localhost", ".internal")):
        return None
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            return None
    except ValueError:
        pass
    return value.strip()


def _copy_source_to_file(source_url: str, target, redirects_left: int = 5) -> tuple[int, bytes]:
    with httpx.stream("GET", source_url, follow_redirects=False, timeout=httpx.Timeout(120, connect=10)) as response:
        if response.is_redirect:
            destination = _source_url(urljoin(source_url, response.headers.get("location", "")))
            if redirects_left <= 0 or destination is None:
                raise ValueError("Redirection de replay non autorisée")
            return _copy_source_to_file(destination, target, redirects_left - 1)
        response.raise_for_status()
        size = 0
        first_chunk = b""
        for chunk in response.iter_bytes(1024 * 1024):
            if not chunk:
                continue
            if not first_chunk:
                first_chunk = chunk[:16]
            size += len(chunk)
            if size > MAX_REPLAY_BYTES:
                raise ValueError("Replay trop volumineux")
            target.write(chunk)
        return size, first_chunk


def capture_jaas_recording(db: Session, payload: dict) -> LiveRecordingRecord | None:
    if payload.get("eventType", payload.get("event_type", payload.get("type"))) != "RECORDING_UPLOADED":
        return None
    if settings.jaas_app_id and payload.get("appId") and payload["appId"] != settings.jaas_app_id:
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    fqn = payload.get("fqn") or payload.get("meetingFqn") or data.get("conference") or data.get("roomAddress")
    if not isinstance(fqn, str):
        return None
    room = fqn.strip("/").rsplit("/", 1)[-1]
    room = room.split("@conference", 1)[0]
    matched = ROOM_PATTERN.fullmatch(room)
    if not matched:
        return None
    organization_id, session_id, day_id = map(int, matched.groups())
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == day_id,
        SessionCourseDayRecord.session_id == session_id,
        SessionCourseDayRecord.organization_id == organization_id,
    ))
    session = db.scalar(select(FormationSessionRecord).where(
        FormationSessionRecord.id == session_id,
        FormationSessionRecord.organization_id == organization_id,
    ))
    if day is None or session is None or session.formation.format_type != "live":
        return None
    source = next((url for key in ("preAuthenticatedLink", "preAuthenticatedLinkV2", "downloadUrl", "url", "fileUrl")
                   if (url := _source_url(data.get(key)))), None)
    if source is None:
        return None
    explicit_id = next((str(data[key]).strip() for key in ("recordingSessionId", "recordingId", "recording_id", "fileId", "file_id", "id")
                        if data.get(key)), "")
    provider_id = explicit_id[:180] or hashlib.sha256(f"{fqn}|{source}".encode()).hexdigest()
    recording = db.scalar(select(LiveRecordingRecord).where(
        LiveRecordingRecord.organization_id == organization_id,
        LiveRecordingRecord.provider_recording_id == provider_id,
    ))
    if recording is None:
        recording = LiveRecordingRecord(
            organization_id=organization_id,
            session_id=session_id,
            course_day_id=day_id,
            provider_recording_id=provider_id,
            title=f"Replay · {day.title}",
            status="processing",
        )
    if recording.status != "ready" or not recording.storage_key:
        recording.source_url = source
    if recording.uploaded_at is None:
        try:
            recording.uploaded_at = datetime.fromtimestamp(float(payload["timestamp"]) / 1000, UTC)
        except (KeyError, TypeError, ValueError, OverflowError):
            recording.uploaded_at = datetime.now(UTC)
    duration = next((data[key] for key in ("durationSec", "durationSeconds", "duration_seconds")
                     if data.get(key) is not None), None)
    if duration is not None:
        try:
            recording.duration_seconds = max(0, int(duration))
        except (TypeError, ValueError):
            pass
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording


def download_jaas_recording(recording_id: int) -> None:
    if not settings.live_replay_download_enabled:
        return
    with SessionLocal() as db:
        recording = db.get(LiveRecordingRecord, recording_id)
        if recording is None or not recording.source_url or recording.status == "archived":
            return
        if recording.status == "ready" and recording.storage_key:
            return
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="replay-", delete=False) as temp:
                temp_path = Path(temp.name)
                source_url = _source_url(recording.source_url)
                if source_url is None:
                    raise ValueError("Source de replay non autorisée")
                size, first_chunk = _copy_source_to_file(source_url, temp)
            if first_chunk.startswith(b"\x1a\x45\xdf\xa3"):
                extension, content_type = "webm", "video/webm"
            elif first_chunk[4:8] == b"ftyp":
                extension, content_type = "mp4", "video/mp4"
            else:
                raise ValueError("Format de replay non reconnu")
            key = f"schools/{recording.organization_id}/replays/{recording.id}.{extension}"
            if settings.storage_provider == "r2":
                if not settings.r2_configured or not settings.r2_private_bucket_name or settings.r2_private_bucket_name == settings.r2_bucket_name:
                    raise RuntimeError("Bucket R2 privé requis pour les replays")
                import boto3
                client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url,
                                      aws_access_key_id=settings.r2_access_key_id,
                                      aws_secret_access_key=settings.r2_secret_access_key, region_name="auto")
                client.upload_file(str(temp_path), settings.r2_private_bucket_name, key,
                                   ExtraArgs={"ContentType": content_type})
            elif settings.environment != "production":
                destination = PRIVATE_ROOT / key
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temp_path, destination)
                temp_path = None
            else:
                raise RuntimeError("Stockage privé indisponible pour les replays")
            db.execute(update(LiveRecordingRecord).where(
                LiveRecordingRecord.id == recording_id,
                LiveRecordingRecord.status != "archived",
            ).values(
                storage_key=key,
                content_type=content_type,
                file_size_bytes=size,
                status="ready",
                source_url=None,
            ))
            db.commit()
        except Exception:
            logger.exception("Impossible de copier le replay %s vers le stockage privé", recording_id)
            db.rollback()
            recording = db.get(LiveRecordingRecord, recording_id)
            if recording and recording.status != "archived":
                recording.status = "failed"
                recording.is_published = False
                db.commit()
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)


def may_manage_recordings(db: Session, tenant: TenantContext, session_id: int) -> bool:
    if tenant.support_mode:
        return False
    if tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        return True
    return tenant.has_role("teacher") and db.scalar(select(SessionTeacherRecord.id).where(
        SessionTeacherRecord.organization_id == tenant.organization_id,
        SessionTeacherRecord.session_id == session_id,
        SessionTeacherRecord.teacher_id == tenant.user.id,
    )) is not None


def may_view_recording(db: Session, tenant: TenantContext, recording: LiveRecordingRecord) -> bool:
    if recording.organization_id != tenant.organization_id:
        return False
    if may_manage_recordings(db, tenant, recording.session_id):
        return True
    return recording.status == "ready" and recording.is_published and tenant.has_role("student") and db.scalar(
        select(EnrollmentRecord.id).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == recording.session_id,
            EnrollmentRecord.student_id == tenant.user.id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )
    ) is not None


def replay_stream_token(tenant: TenantContext, recording: LiveRecordingRecord) -> str:
    return jwt.encode({
        "purpose": "replay", "uid": tenant.user.id, "oid": tenant.organization_id,
        "rid": recording.id, "ver": tenant.user.session_version,
        "exp": datetime.now(UTC) + timedelta(hours=4),
    }, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
