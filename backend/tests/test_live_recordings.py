import base64
import asyncio
import hashlib
import hmac
import io
import json
import time
from datetime import UTC, date, datetime

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes import live_recordings as routes
from app.core.config import Settings, settings
from app.db.base import Base
from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.services.live_recordings import _source_url, capture_jaas_recording, replay_stream_token, verify_jaas_signature
from app.services.tenancy import resolve_tenant_context


def seed():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org = OrganizationRecord(name="École", slug="ecole")
    other_org = OrganizationRecord(name="Autre", slug="autre")
    teacher = UserRecord(email="teacher@recording.test", full_name="Prof", status="active")
    student = UserRecord(email="student@recording.test", full_name="Élève", status="active")
    outsider = UserRecord(email="outsider@recording.test", full_name="Autre élève", status="active")
    db.add_all([org, other_org, teacher, student, outsider])
    db.flush()
    formation = FormationRecord(organization_id=org.id, slug="live", title="Live", format_type="live")
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(
        organization_id=org.id, formation_id=formation.id, label="Cohorte",
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 30), status="open",
    )
    db.add(session)
    db.flush()
    day = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Cours live", scheduled_at=datetime(2026, 10, 8, 10, tzinfo=UTC),
        duration_minutes=90,
    )
    db.add_all([
        day,
        SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, role="principal"),
        EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=student.id, status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=teacher.id, role="teacher", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=student.id, role="student", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=outsider.id, role="student", status="active"),
    ])
    db.commit()
    return db, org, other_org, session, day, teacher, student, outsider


def test_signed_webhook_and_tenant_room_capture(monkeypatch) -> None:
    db, org, other_org, session, day, *_ = seed()
    monkeypatch.setattr(settings, "jaas_webhook_secret", "test-secret")
    payload = {
        "eventType": "RECORDING_UPLOADED",
        "fqn": f"app/school-{org.id}-session-{session.id}-day-{day.id}",
        "data": {"recordingId": "recording-1", "preAuthenticatedLink": "https://cdn.example.test/replay.mp4"},
    }
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(b"test-secret", timestamp.encode() + b"." + body, hashlib.sha256).digest()
    signature = f"t={timestamp},v1={base64.b64encode(digest).decode()}"
    assert verify_jaas_signature(signature, body)
    assert verify_jaas_signature(f"t={timestamp},v1=invalid,v1={base64.b64encode(digest).decode()}", body)
    assert not verify_jaas_signature(f"t={timestamp},v1=invalid", body)
    assert _source_url("https://169.254.169.254/latest/meta-data") is None
    assert _source_url("https://127.0.0.1/replay.mp4") is None

    first = capture_jaas_recording(db, payload)
    assert first is not None
    assert first.organization_id == org.id
    assert first.course_day_id == day.id
    assert capture_jaas_recording(db, payload).id == first.id

    payload["fqn"] = f"app/school-{other_org.id}-session-{session.id}-day-{day.id}"
    assert capture_jaas_recording(db, payload) is None


def test_replay_publication_and_stream_are_scoped_to_enrollment(tmp_path, monkeypatch) -> None:
    db, org, other_org, session, day, teacher, student, outsider = seed()
    payload = {
        "eventType": "RECORDING_UPLOADED",
        "fqn": f"app/school-{org.id}-session-{session.id}-day-{day.id}",
        "data": {"recordingId": "recording-2", "downloadUrl": "https://cdn.example.test/replay.mp4"},
    }
    recording = capture_jaas_recording(db, payload)
    assert recording is not None
    teacher_tenant = resolve_tenant_context(db, user=teacher, organization_id=org.id)
    student_tenant = resolve_tenant_context(db, user=student, organization_id=org.id)
    outsider_tenant = resolve_tenant_context(db, user=outsider, organization_id=org.id)
    db.add(OrganizationMemberRecord(
        organization_id=other_org.id, user_id=student.id, role="student", status="active",
    ))
    db.commit()
    other_school_tenant = resolve_tenant_context(db, user=student, organization_id=other_org.id)

    with pytest.raises(HTTPException) as error:
        routes.update_live_recording(recording.id, routes.LiveRecordingUpdate(is_published=True), db, teacher_tenant)
    assert error.value.status_code == 409
    assert routes.list_live_recordings(session.id, db, student_tenant) == []
    with pytest.raises(HTTPException) as error:
        routes.list_live_recordings(session.id, db, outsider_tenant)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        routes.list_live_recordings(session.id, db, other_school_tenant)
    assert error.value.status_code == 404

    recording.status = "ready"
    recording.storage_key = f"schools/{org.id}/replays/{recording.id}.mp4"
    day.report_submitted_at = datetime.now(UTC)
    db.commit()
    published = routes.update_live_recording(
        recording.id, routes.LiveRecordingUpdate(is_published=True), db, teacher_tenant,
    )
    assert published.is_published
    assert len(routes.list_live_recordings(session.id, db, student_tenant)) == 1

    monkeypatch.setattr(routes, "PRIVATE_ROOT", tmp_path)
    replay_path = tmp_path / recording.storage_key
    replay_path.parent.mkdir(parents=True)
    replay_path.write_bytes(b"\x00\x00\x00\x18ftypisom")
    token = replay_stream_token(student_tenant, recording)
    response = routes.stream_live_recording(recording.id, token=token, download=False, db=db)
    assert isinstance(response, FileResponse)
    with pytest.raises(HTTPException) as error:
        routes.stream_live_recording(recording.id, token=replay_stream_token(other_school_tenant, recording), download=False, db=db)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        routes.stream_live_recording(recording.id, token=token, download=True, db=db)
    assert error.value.status_code == 403

    calls = []
    class FakeS3:
        def get_object(self, **kwargs):
            calls.append(kwargs)
            return {"Body": io.BytesIO(b"video-bytes"), "ContentLength": 11, "ContentRange": "bytes 0-10/11"}

    monkeypatch.setattr(settings, "storage_provider", "r2")
    monkeypatch.setattr(settings, "r2_private_bucket_name", "private-test")
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: FakeS3())
    ranged = routes.stream_live_recording(recording.id, token=token, download=False, range_header="bytes=0-10", db=db)
    assert isinstance(ranged, StreamingResponse)
    assert ranged.status_code == 206
    assert ranged.headers["content-range"] == "bytes 0-10/11"
    assert calls[0]["Range"] == "bytes=0-10"
    async def read_body():
        return b"".join([chunk async for chunk in ranged.body_iterator])
    assert asyncio.run(read_body()) == b"video-bytes"

    student.session_version += 1
    db.commit()
    with pytest.raises(HTTPException) as error:
        routes.stream_live_recording(recording.id, token=token, download=False, db=db)
    assert error.value.status_code == 404


def test_teacher_can_retry_and_archive_failed_replay(monkeypatch) -> None:
    db, org, _, session, day, teacher, student, _ = seed()
    recording = capture_jaas_recording(db, {
        "eventType": "RECORDING_UPLOADED",
        "fqn": f"app/school-{org.id}-session-{session.id}-day-{day.id}",
        "data": {"recordingId": "recording-3", "downloadUrl": "https://cdn.example.test/replay.mp4"},
    })
    assert recording is not None
    recording.status = "failed"
    db.commit()
    teacher_tenant = resolve_tenant_context(db, user=teacher, organization_id=org.id)
    student_tenant = resolve_tenant_context(db, user=student, organization_id=org.id)
    tasks = BackgroundTasks()
    monkeypatch.setattr(settings, "live_replay_download_enabled", True)

    with pytest.raises(HTTPException) as error:
        routes.retry_live_recording(recording.id, tasks, db, student_tenant)
    assert error.value.status_code == 403
    assert routes.retry_live_recording(recording.id, tasks, db, teacher_tenant)["status"] == "processing"
    assert len(tasks.tasks) == 1
    with pytest.raises(HTTPException) as error:
        routes.update_live_recording(recording.id, routes.LiveRecordingUpdate(download_allowed=True), db, teacher_tenant)
    assert error.value.status_code == 409

    routes.archive_live_recording(recording.id, db, teacher_tenant)
    assert db.get(type(recording), recording.id).status == "archived"
    assert routes.list_live_recordings(session.id, db, teacher_tenant) == []


def test_production_recording_requires_private_bucket() -> None:
    config = Settings(
        environment="production",
        jwt_secret_key="test-only-unique-secret-with-over-32-characters",
        jaas_enabled=True,
        jaas_app_id="test-app",
        jaas_kid="test-kid",
        jaas_private_key="test-key",
        jaas_recording_enabled=True,
        jaas_webhook_secret="test-only-webhook-secret",
        storage_provider="local",
    )
    with pytest.raises(RuntimeError, match="bucket R2 privé"):
        config.validate_production_security()
    config.storage_provider = "r2"
    config.r2_endpoint_url = "https://r2.example.test"
    config.r2_bucket_name = "public"
    config.r2_private_bucket_name = "private"
    config.r2_access_key_id = "test-id"
    config.r2_secret_access_key = "test-secret"
    config.r2_public_base_url = "https://cdn.example.test"
    config.validate_production_security()
