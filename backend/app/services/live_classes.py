from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import re

import jwt
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    EnrollmentRecord, FormationSessionRecord, LiveRollCallAnswerRecord, LiveRollCallRecord, LiveRoomPresenceRecord,
    OrganizationPublicSiteRecord, OrganizationRecord,
    SessionCourseDayRecord, SessionTeacherRecord, UserRecord,
)
from app.services.live_recordings import _source_url
from app.services.plan_limits import allowance, require_feature
from app.services.subscriptions import get_effective_plan
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
    return _room_branding(db, *map(int, match.groups()))


def self_hosted_room_branding(db: Session, conference: str) -> dict | None:
    """The school's identity for one room of the self-hosted Jitsi, fetched by Jitsi itself.

    Jitsi shows the returned logo in place of its own, and nothing when there is none.
    """
    if settings.live_provider != "jitsi":
        return None
    match = re.fullmatch(r"school-(\d+)-session-(\d+)-day-(\d+)", conference)
    if match is None:
        return None
    return _room_branding(db, *map(int, match.groups()))


def _room_branding(db: Session, organization_id: int, session_id: int, day_id: int) -> dict | None:
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
        require_feature(db, tenant.organization_id, "live")
        _require_live_room(db, tenant.organization_id, day, current)
        day.started_at = current
        db.commit()
    return {"course_day_id": day.id, "started_at": _aware(day.started_at)}


ROOM_OPENS_BEFORE = timedelta(minutes=15)
ROOM_CLOSES_AFTER = timedelta(minutes=15)


def _require_live_room(db: Session, organization_id: int, day: SessionCourseDayRecord, current: datetime) -> None:
    """A plan runs so many live classes at once: one more starts only when one of them is over."""
    plan = get_effective_plan(db, organization_id)
    rule = allowance(plan, "live_rooms")
    if not rule.enabled or rule.limit is None:
        return
    # Serialize the school's starts so two teachers cannot both take the last room.
    db.scalar(select(OrganizationRecord.id).where(OrganizationRecord.id == organization_id).with_for_update())
    started = db.scalars(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.organization_id == organization_id,
        SessionCourseDayRecord.id != day.id,
        SessionCourseDayRecord.started_at.is_not(None),
        SessionCourseDayRecord.started_at >= current - timedelta(days=1),
        SessionCourseDayRecord.report_submitted_at.is_(None),
        SessionCourseDayRecord.status != "cancelled",
    )).all()
    running = [
        other for other in started
        if current <= _aware(other.scheduled_at) + timedelta(minutes=other.duration_minutes) + ROOM_CLOSES_AFTER
    ]
    if len(running) < rule.limit:
        return
    db.rollback()
    at_once = "un seul cours en live à la fois" if rule.limit == 1 else f"{rule.limit} cours en live à la fois"
    raise HTTPException(
        409,
        f"Votre forfait {plan.name} permet {at_once}, et c'est déjà le cas. "
        "Attendez la fin d'un cours ou passez au forfait supérieur.",
    )
LIVE_ACTIVE_DEVICE_TTL = timedelta(seconds=90)


def _live_class_access(
    db: Session, tenant: TenantContext, course_day_id: int,
) -> tuple[SessionCourseDayRecord, FormationSessionRecord, bool, bool, bool]:
    """The open live course day and whether the caller manages it, teaches it or attends it, else 403/404."""
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
    return day, session, manager, teacher, student


def live_class_info(db: Session, tenant: TenantContext, course_day_id: int) -> dict:
    """What the live room shows before anyone enters: its waiting room, then its welcome card."""
    day, session, manager, teacher, _ = _live_class_access(db, tenant, course_day_id)
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
    device_id: str | None = None, device_label: str | None = None,
) -> dict:
    day, session, manager, teacher, student = _live_class_access(db, tenant, course_day_id)

    current = _aware(now or datetime.now(UTC))
    starts_at = _aware(day.scheduled_at)
    ends_at = starts_at + timedelta(minutes=day.duration_minutes)
    if current < starts_at - ROOM_OPENS_BEFORE or current > ends_at + ROOM_CLOSES_AFTER:
        raise HTTPException(403, "La salle ouvre 15 minutes avant le cours et ferme 15 minutes après.")

    if not live_provider_configured():
        raise HTTPException(503, "Le service de classes live n'est pas configuré.")
    # Check the plan before issuing a room token, including its per-class student cap.
    require_feature(db, tenant.organization_id, "live")
    if student and not (manager or teacher):
        limit = allowance(get_effective_plan(db, tenant.organization_id), "live").limit
        if limit is not None:
            # Serialize joins to this room so simultaneous requests cannot exceed the plan cap.
            db.scalar(select(SessionCourseDayRecord.id).where(
                SessionCourseDayRecord.id == day.id,
                SessionCourseDayRecord.organization_id == tenant.organization_id,
            ).with_for_update())
            active_students = db.scalar(select(func.count(func.distinct(LiveRoomPresenceRecord.user_id))).where(
                LiveRoomPresenceRecord.organization_id == tenant.organization_id,
                LiveRoomPresenceRecord.course_day_id == day.id,
                LiveRoomPresenceRecord.user_id != tenant.user.id,
                LiveRoomPresenceRecord.left_at.is_(None),
                LiveRoomPresenceRecord.last_seen_at >= current - LIVE_ACTIVE_DEVICE_TTL,
            )) or 0
            if active_students >= limit:
                db.rollback()
                raise HTTPException(
                    409,
                    f"Cette classe a atteint la limite de {limit} étudiants en live prévue par votre forfait.",
                )
        _hold_live_device(db, tenant, day, device_id, device_label, current)

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


# As on the mother site, a student keeps one device in live classes at a time: another
# device that sent a heartbeat less than 90 seconds ago, without leaving, holds the place.
DEVICE_TAKEN = (
    "Votre compte étudiant est déjà connecté à un live sur un autre appareil. "
    "Quittez cette salle ou réessayez dans environ 90 secondes."
)


def _device_id(value: str | None, user_id: int) -> str:
    safe = "".join(char for char in (value or "").strip() if char.isalnum() or char in "-_.")
    return safe[:128] or f"user-{user_id}"


# Each heartbeat credits the time since the previous one, at most a minute: a dropped
# connection or a closed tab is not counted as time in the room.
HEARTBEAT_CREDIT_MAX = timedelta(seconds=60)


def _credit_time_in_room(presence: LiveRoomPresenceRecord, current: datetime) -> None:
    if presence.left_at is None:
        gap = (current - _aware(presence.last_seen_at)).total_seconds()
        presence.seconds_in_room = (presence.seconds_in_room or 0) + int(max(0.0, min(gap, HEARTBEAT_CREDIT_MAX.total_seconds())))


def _hold_live_device(
    db: Session, tenant: TenantContext, day: SessionCourseDayRecord,
    device_id: str | None, device_label: str | None, current: datetime,
) -> None:
    device = _device_id(device_id, tenant.user.id)
    # Serializes two devices joining at the same time for one account (PostgreSQL).
    db.scalar(select(UserRecord.id).where(UserRecord.id == tenant.user.id).with_for_update())
    taken = db.scalar(select(LiveRoomPresenceRecord.id).where(
        LiveRoomPresenceRecord.user_id == tenant.user.id,
        LiveRoomPresenceRecord.device_id != device,
        LiveRoomPresenceRecord.left_at.is_(None),
        LiveRoomPresenceRecord.last_seen_at >= current - LIVE_ACTIVE_DEVICE_TTL,
    ).limit(1))
    if taken is not None:
        db.rollback()
        raise HTTPException(409, DEVICE_TAKEN)
    presence = db.scalar(select(LiveRoomPresenceRecord).where(
        LiveRoomPresenceRecord.course_day_id == day.id,
        LiveRoomPresenceRecord.user_id == tenant.user.id,
        LiveRoomPresenceRecord.device_id == device,
    ))
    label = (device_label or "").strip()[:160] or None
    if presence is None:
        db.add(LiveRoomPresenceRecord(
            organization_id=tenant.organization_id, course_day_id=day.id, user_id=tenant.user.id,
            device_id=device, device_label=label, first_joined_at=current, last_seen_at=current,
            seconds_in_room=0,
        ))
    else:
        _credit_time_in_room(presence, current)
        presence.last_seen_at = current
        presence.left_at = None
        presence.device_label = label or presence.device_label
    db.commit()


def heartbeat_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
    device_id: str | None = None, device_label: str | None = None,
) -> dict:
    """Keeps a student's device in the room and tells the room about the roll call.

    A closed class or another device ends the student's room (404, 409).
    """
    day, _session, manager, teacher, student = _live_class_access(db, tenant, course_day_id)
    current = _aware(now or datetime.now(UTC))
    student_only = bool(student and not (manager or teacher))
    if student_only:
        _hold_live_device(db, tenant, day, device_id, device_label, current)
    return {"roll_call": _roll_call_view(db, tenant, day, current, student_only=student_only)}


def leave_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
    device_id: str | None = None,
) -> None:
    """Frees the device at once, even once the class is closed."""
    presence = db.scalar(select(LiveRoomPresenceRecord).where(
        LiveRoomPresenceRecord.organization_id == tenant.organization_id,
        LiveRoomPresenceRecord.course_day_id == course_day_id,
        LiveRoomPresenceRecord.user_id == tenant.user.id,
        LiveRoomPresenceRecord.device_id == _device_id(device_id, tenant.user.id),
    ))
    if presence is not None and presence.left_at is None:
        current = _aware(now or datetime.now(UTC))
        _credit_time_in_room(presence, current)
        presence.last_seen_at = current
        presence.left_at = current
        db.commit()


# The teacher's roll call: students have two minutes to answer "Je suis là".
ROLL_CALL_WINDOW = timedelta(minutes=2)
ROLL_CALL_GRACE = timedelta(seconds=15)  # an answer sent just before the end still arrives


def _latest_roll_call(db: Session, organization_id: int, day_id: int) -> LiveRollCallRecord | None:
    return db.scalar(select(LiveRollCallRecord).where(
        LiveRollCallRecord.organization_id == organization_id,
        LiveRollCallRecord.course_day_id == day_id,
    ).order_by(LiveRollCallRecord.started_at.desc(), LiveRollCallRecord.id.desc()).limit(1))


def _roll_call_view(
    db: Session, tenant: TenantContext, day: SessionCourseDayRecord, current: datetime, *, student_only: bool,
) -> dict | None:
    call = _latest_roll_call(db, tenant.organization_id, day.id)
    if call is None:
        return None
    is_open = current <= _aware(call.closes_at)
    if student_only and not is_open:
        return None
    answered = db.scalar(select(LiveRollCallAnswerRecord.id).where(
        LiveRollCallAnswerRecord.roll_call_id == call.id,
        LiveRollCallAnswerRecord.user_id == tenant.user.id,
    )) is not None
    answers = None if student_only else int(db.scalar(select(func.count(LiveRollCallAnswerRecord.id)).where(
        LiveRollCallAnswerRecord.roll_call_id == call.id,
    )) or 0)
    return {
        "id": call.id,
        "started_at": _aware(call.started_at),
        "closes_at": _aware(call.closes_at),
        "open": is_open,
        "answered": answered,
        "answers_count": answers,
    }


def start_roll_call(db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None) -> dict:
    day, _session, _manager, teacher, _student = _live_class_access(db, tenant, course_day_id)
    if not (teacher and day.teacher_id == tenant.user.id):
        raise HTTPException(403, "Seul le professeur responsable peut faire l'appel.")
    if day.started_at is None:
        raise HTTPException(409, "Démarrez le cours avant de faire l'appel.")
    current = _aware(now or datetime.now(UTC))
    latest = _latest_roll_call(db, tenant.organization_id, day.id)
    if latest is None or current > _aware(latest.closes_at):
        db.add(LiveRollCallRecord(
            organization_id=tenant.organization_id, course_day_id=day.id, started_by_user_id=tenant.user.id,
            started_at=current, closes_at=current + ROLL_CALL_WINDOW,
        ))
        db.commit()
    return _roll_call_view(db, tenant, day, current, student_only=False)


def answer_roll_call(
    db: Session, tenant: TenantContext, course_day_id: int, roll_call_id: int, *, now: datetime | None = None,
) -> None:
    day, _session, _manager, _teacher, student = _live_class_access(db, tenant, course_day_id)
    if not student:
        raise HTTPException(403, "Seuls les étudiants répondent à l'appel.")
    call = db.scalar(select(LiveRollCallRecord).where(
        LiveRollCallRecord.id == roll_call_id,
        LiveRollCallRecord.organization_id == tenant.organization_id,
        LiveRollCallRecord.course_day_id == day.id,
    ))
    if call is None:
        raise HTTPException(404, "Appel introuvable.")
    current = _aware(now or datetime.now(UTC))
    if current > _aware(call.closes_at) + ROLL_CALL_GRACE:
        raise HTTPException(409, "L'appel est terminé.")
    if db.scalar(select(LiveRollCallAnswerRecord.id).where(
        LiveRollCallAnswerRecord.roll_call_id == call.id,
        LiveRollCallAnswerRecord.user_id == tenant.user.id,
    )) is None:
        db.add(LiveRollCallAnswerRecord(
            organization_id=tenant.organization_id, roll_call_id=call.id, user_id=tenant.user.id, answered_at=current,
        ))
        db.commit()


@dataclass(frozen=True)
class LiveEvidence:
    """What shows that a student followed one live class."""
    entered_at: datetime | None
    seconds_in_room: int
    roll_calls_answered: int


def live_attendance_evidence(db: Session, organization_id: int, day_id: int) -> tuple[dict[int, LiveEvidence], int]:
    """Each student's evidence for one course day, by user id, and the number of roll calls held."""
    presences: dict[int, tuple[datetime | None, int]] = {}
    for user_id, entered_at, seconds in db.execute(select(
        LiveRoomPresenceRecord.user_id,
        func.min(LiveRoomPresenceRecord.first_joined_at),
        func.sum(LiveRoomPresenceRecord.seconds_in_room),
    ).where(
        LiveRoomPresenceRecord.organization_id == organization_id,
        LiveRoomPresenceRecord.course_day_id == day_id,
    ).group_by(LiveRoomPresenceRecord.user_id)).all():
        presences[user_id] = (_aware(entered_at) if entered_at else None, int(seconds or 0))
    call_ids = list(db.scalars(select(LiveRollCallRecord.id).where(
        LiveRollCallRecord.organization_id == organization_id,
        LiveRollCallRecord.course_day_id == day_id,
    )).all())
    answered: dict[int, int] = {}
    if call_ids:
        for user_id, count in db.execute(select(
            LiveRollCallAnswerRecord.user_id, func.count(LiveRollCallAnswerRecord.id),
        ).where(LiveRollCallAnswerRecord.roll_call_id.in_(call_ids)).group_by(LiveRollCallAnswerRecord.user_id)).all():
            answered[user_id] = int(count)
    evidence = {}
    for user_id in set(presences) | set(answered):
        entered_at, seconds = presences.get(user_id, (None, 0))
        evidence[user_id] = LiveEvidence(entered_at=entered_at, seconds_in_room=seconds, roll_calls_answered=answered.get(user_id, 0))
    return evidence, len(call_ids)


# A student is present when they spent at least half of the course in the room, and late
# when they came in more than 15 minutes after it started (as on the mother site).
LIVE_PRESENT_MIN_SHARE = 0.5
LIVE_LATE_AFTER = timedelta(minutes=15)


def live_course_window(day: SessionCourseDayRecord, current: datetime) -> tuple[datetime, datetime]:
    """When the course actually ran: from its start to its closing, at most until the room closes."""
    start = _aware(day.started_at or day.scheduled_at)
    room_closes = _aware(day.scheduled_at) + timedelta(minutes=day.duration_minutes) + ROOM_CLOSES_AFTER
    end = min(_aware(current), room_closes)
    return start, max(end, start + timedelta(minutes=1))


def prefill_live_status(
    evidence: LiveEvidence | None, roll_calls: int, start: datetime, end: datetime,
) -> str:
    """The attendance a live class suggests; the teacher can still correct it for 24 h."""
    if evidence is None or evidence.entered_at is None:
        return "absent"
    if roll_calls and evidence.roll_calls_answered == 0:
        return "absent"  # the screen was open, nobody answered the roll call
    if evidence.seconds_in_room < (end - start).total_seconds() * LIVE_PRESENT_MIN_SHARE:
        return "absent"
    return "late" if evidence.entered_at > start + LIVE_LATE_AFTER else "present"
