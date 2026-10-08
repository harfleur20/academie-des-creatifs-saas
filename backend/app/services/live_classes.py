from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import EnrollmentRecord, FormationSessionRecord, SessionCourseDayRecord, SessionTeacherRecord
from app.services.teacher_readiness import require_teacher_ready
from app.services.tenancy import TenantContext


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _private_key() -> str:
    if settings.jaas_private_key:
        return settings.jaas_private_key
    if not settings.jaas_private_key_file:
        return ""
    path = Path(settings.jaas_private_key_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def live_provider_configured() -> bool:
    return bool(settings.jaas_enabled and settings.jaas_app_id and settings.jaas_kid and _private_key())


def start_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
) -> dict:
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == course_day_id,
        SessionCourseDayRecord.organization_id == tenant.organization_id,
    ))
    if day is None:
        raise HTTPException(404, "Séance introuvable.")
    session = db.scalar(select(FormationSessionRecord).options(selectinload(FormationSessionRecord.formation)).where(
        FormationSessionRecord.id == day.session_id,
        FormationSessionRecord.organization_id == tenant.organization_id,
    ))
    if session is None or session.formation.format_type != "live":
        raise HTTPException(404, "Classe live introuvable.")
    assigned = tenant.has_role("teacher") and db.scalar(select(SessionTeacherRecord.id).where(
        SessionTeacherRecord.organization_id == tenant.organization_id,
        SessionTeacherRecord.session_id == session.id,
        SessionTeacherRecord.teacher_id == tenant.user.id,
    )) is not None
    if not assigned or day.teacher_id != tenant.user.id or tenant.support_mode:
        raise HTTPException(403, "Seul le professeur responsable peut démarrer cette classe live.")
    require_teacher_ready(db, tenant)
    if session.status == "cancelled" or day.status == "cancelled" or day.report_submitted_at is not None:
        raise HTTPException(409, "Cette classe live est clôturée ou annulée.")
    current = _aware(now or datetime.now(UTC))
    if current < _aware(day.scheduled_at):
        raise HTTPException(409, "Le cours ne peut démarrer qu'à l'heure prévue.")
    if day.started_at is None:
        day.started_at = current
        db.commit()
    return {"course_day_id": day.id, "started_at": day.started_at}


def join_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
) -> dict:
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == course_day_id,
        SessionCourseDayRecord.organization_id == tenant.organization_id,
    ))
    if day is None:
        raise HTTPException(404, "Séance introuvable.")
    session = db.scalar(select(FormationSessionRecord).options(selectinload(FormationSessionRecord.formation)).where(
        FormationSessionRecord.id == day.session_id,
        FormationSessionRecord.organization_id == tenant.organization_id,
    ))
    if session is None or session.formation.format_type != "live" or session.status == "cancelled" or day.status == "cancelled" or day.report_submitted_at is not None:
        raise HTTPException(404, "Classe live introuvable.")

    manager = bool(tenant.organization_roles.intersection({"owner", "admin", "manager", "super_admin"}))
    teacher = tenant.has_role("teacher") and db.scalar(select(SessionTeacherRecord.id).where(
        SessionTeacherRecord.organization_id == tenant.organization_id,
        SessionTeacherRecord.session_id == session.id,
        SessionTeacherRecord.teacher_id == tenant.user.id,
    )) is not None
    student = tenant.has_role("student") and db.scalar(select(EnrollmentRecord.id).where(
        EnrollmentRecord.organization_id == tenant.organization_id,
        EnrollmentRecord.session_id == session.id,
        EnrollmentRecord.student_id == tenant.user.id,
        EnrollmentRecord.status.in_(["active", "completed"]),
    )) is not None
    if not (manager or teacher or student):
        raise HTTPException(403, "Vous n'êtes pas inscrit ou affecté à cette classe live.")
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support ne peut pas rejoindre une classe live.")
    if teacher:
        require_teacher_ready(db, tenant)

    current = _aware(now or datetime.now(UTC))
    starts_at = _aware(day.scheduled_at)
    ends_at = starts_at + timedelta(minutes=day.duration_minutes)
    if current < starts_at - timedelta(minutes=15) or current > ends_at + timedelta(minutes=15):
        raise HTTPException(403, "La salle ouvre 15 minutes avant le cours et ferme 15 minutes après.")

    private_key = _private_key()
    if not (settings.jaas_enabled and settings.jaas_app_id and settings.jaas_kid and private_key):
        raise HTTPException(503, "Le service de classes live n'est pas configuré.")

    moderator = bool(manager or teacher)
    room = f"school-{tenant.organization_id}-session-{session.id}-day-{day.id}"
    payload = {
        "aud": "jitsi", "iss": "chat", "sub": settings.jaas_app_id, "room": room,
        "nbf": int((current - timedelta(seconds=30)).timestamp()),
        "exp": int((current + timedelta(minutes=10)).timestamp()),
        "context": {
            "features": {"recording": moderator and settings.jaas_recording_enabled, "livestreaming": False, "transcription": False},
            "user": {
                "id": f"school-{tenant.organization_id}-user-{tenant.user.id}",
                "name": tenant.user.full_name,
                "email": tenant.user.email,
                "moderator": "true" if moderator else "false",
            },
        },
    }
    try:
        token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": settings.jaas_kid, "typ": "JWT"})
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "La configuration de la classe live est invalide.") from exc
    return {
        "course_day_id": day.id,
        "title": day.title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "domain": settings.jaas_domain,
        "room_name": f"{settings.jaas_app_id}/{room}",
        "external_api_url": f"https://{settings.jaas_domain}/{settings.jaas_app_id}/external_api.js",
        "token": token,
        "moderator": moderator,
        "started_at": day.started_at,
    }
