from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import re

import jwt
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import EnrollmentRecord, FormationSessionRecord, OrganizationPublicSiteRecord, OrganizationRecord, SessionCourseDayRecord, SessionTeacherRecord
from app.services.live_recordings import _source_url
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
    if settings.live_provider == "jitsi":
        return bool(settings.jitsi_domain and settings.jitsi_app_id and settings.jitsi_app_secret)
    return bool(settings.jaas_enabled and settings.jaas_app_id and settings.jaas_kid and _private_key())


def _jaas_room(room: str, user: dict, *, moderator: bool, current: datetime) -> dict:
    private_key = _private_key()
    payload = {
        "aud": "jitsi", "iss": "chat", "sub": settings.jaas_app_id, "room": room,
        "nbf": int((current - timedelta(seconds=30)).timestamp()),
        "exp": int((current + timedelta(minutes=10)).timestamp()),
        "context": {
            "features": {"recording": moderator and settings.jaas_recording_enabled, "livestreaming": False, "transcription": False},
            "user": {**user, "moderator": "true" if moderator else "false"},
        },
    }
    try:
        token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": settings.jaas_kid, "typ": "JWT"})
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "La configuration de la classe live est invalide.") from exc
    return {
        "domain": settings.jaas_domain,
        "room_name": f"{settings.jaas_app_id}/{room}",
        "external_api_url": f"https://{settings.jaas_domain}/{settings.jaas_app_id}/external_api.js",
        "token": token,
    }


def _self_hosted_room(room: str, user: dict, *, moderator: bool, current: datetime) -> dict:
    """A token for the school's own Jitsi (infra/live): shared secret, moderator only for staff.

    Its Prosody runs mod_token_affiliation, which makes the token's moderators owners and every
    other participant a plain member; Jicofo must not promote anyone else (ENABLE_AUTO_OWNER=0).
    """
    payload = {
        "aud": settings.jitsi_app_id, "iss": settings.jitsi_app_id, "sub": settings.jitsi_xmpp_domain,
        "room": room,
        "nbf": int((current - timedelta(seconds=30)).timestamp()),
        "exp": int((current + timedelta(minutes=10)).timestamp()),
        "context": {
            "features": {"recording": False, "livestreaming": False, "transcription": False},
            "user": {**user, "moderator": moderator, "affiliation": "owner" if moderator else "member"},
        },
    }
    token = jwt.encode(payload, settings.jitsi_app_secret, algorithm="HS256", headers={"typ": "JWT"})
    return {
        "domain": settings.jitsi_domain,
        "room_name": room,
        "external_api_url": f"https://{settings.jitsi_domain}/external_api.js",
        "token": token,
    }


def _school_live_identity(db: Session, organization_id: int) -> tuple[str, str | None, str]:
    organization = db.get(OrganizationRecord, organization_id)
    site = db.scalar(select(OrganizationPublicSiteRecord).where(
        OrganizationPublicSiteRecord.organization_id == organization_id,
    ))
    return (
        (site.site_name or organization.name) if site else organization.name,
        organization.logo_url,
        organization.primary_color,
    )


def jaas_room_branding(db: Session, conference: str) -> dict | None:
    """Return the owning school's public identity for one verified JaaS room."""
    if not settings.jaas_app_id:
        return None
    match = re.fullmatch(
        rf"{re.escape(settings.jaas_app_id)}/school-(\d+)-session-(\d+)-day-(\d+)",
        conference,
    )
    if match is None:
        return None
    organization_id, session_id, day_id = map(int, match.groups())
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == day_id,
        SessionCourseDayRecord.session_id == session_id,
        SessionCourseDayRecord.organization_id == organization_id,
    ))
    session = db.scalar(select(FormationSessionRecord).options(selectinload(FormationSessionRecord.formation)).where(
        FormationSessionRecord.id == session_id,
        FormationSessionRecord.organization_id == organization_id,
    ))
    if day is None or session is None or session.formation.format_type != "live":
        return None
    _, logo_url, primary_color = _school_live_identity(db, organization_id)
    branding = {"backgroundColor": primary_color}
    public_logo_url = _source_url(logo_url)
    if public_logo_url:
        branding["logoImageUrl"] = public_logo_url
    return branding


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
    return {"course_day_id": day.id, "started_at": _aware(day.started_at)}


ROOM_OPENS_BEFORE = timedelta(minutes=15)
ROOM_CLOSES_AFTER = timedelta(minutes=15)


def _live_class_access(
    db: Session, tenant: TenantContext, course_day_id: int,
) -> tuple[SessionCourseDayRecord, FormationSessionRecord, bool, bool]:
    """The open live course day and whether the caller manages it or teaches it, else 403/404."""
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
    if session.status == "cancelled" or day.status == "cancelled":
        raise HTTPException(404, "Cette classe live est annulée.")
    if day.report_submitted_at is not None:
        raise HTTPException(404, "Ce cours est terminé : sa salle est fermée.")

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
    return day, session, manager, teacher


def live_class_info(db: Session, tenant: TenantContext, course_day_id: int) -> dict:
    """What the live room shows before anyone enters: its waiting room, then its welcome card."""
    day, session, manager, teacher = _live_class_access(db, tenant, course_day_id)
    starts_at = _aware(day.scheduled_at)
    ends_at = starts_at + timedelta(minutes=day.duration_minutes)
    school_name, school_logo_url, school_primary_color = _school_live_identity(db, tenant.organization_id)
    return {
        "course_day_id": day.id,
        "title": day.title,
        "formation_title": session.formation.title,
        "session_label": session.label,
        "formation_image_url": session.formation.cover_image_url,
        "school_name": school_name,
        "school_logo_url": school_logo_url,
        "school_primary_color": school_primary_color,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "opens_at": starts_at - ROOM_OPENS_BEFORE,
        "closes_at": ends_at + ROOM_CLOSES_AFTER,
        "started_at": _aware(day.started_at) if day.started_at else None,
        "moderator": bool(manager or teacher),
        "responsible_teacher": bool(teacher and day.teacher_id == tenant.user.id),
    }


def join_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
) -> dict:
    day, session, manager, teacher = _live_class_access(db, tenant, course_day_id)

    current = _aware(now or datetime.now(UTC))
    starts_at = _aware(day.scheduled_at)
    ends_at = starts_at + timedelta(minutes=day.duration_minutes)
    if current < starts_at - ROOM_OPENS_BEFORE or current > ends_at + ROOM_CLOSES_AFTER:
        raise HTTPException(403, "La salle ouvre 15 minutes avant le cours et ferme 15 minutes après.")

    if not live_provider_configured():
        raise HTTPException(503, "Le service de classes live n'est pas configuré.")

    moderator = bool(manager or teacher)
    room = f"school-{tenant.organization_id}-session-{session.id}-day-{day.id}"
    user = {
        "id": f"school-{tenant.organization_id}-user-{tenant.user.id}",
        "name": tenant.user.full_name,
        "email": tenant.user.email,
    }
    provider_room = (_self_hosted_room if settings.live_provider == "jitsi" else _jaas_room)(
        room, user, moderator=moderator, current=current,
    )
    school_name, school_logo_url, _ = _school_live_identity(db, tenant.organization_id)
    return {
        "course_day_id": day.id,
        "title": day.title,
        "school_name": school_name,
        "school_logo_url": school_logo_url,
        "starts_at": starts_at,
        "ends_at": ends_at,
        **provider_room,
        "moderator": moderator,
        "started_at": _aware(day.started_at) if day.started_at else None,
    }
