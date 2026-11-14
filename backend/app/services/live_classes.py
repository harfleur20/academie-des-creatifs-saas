from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
import re
import threading

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
from app.services.support_mail import send_support_request_email
from app.services.teacher_readiness import require_teacher_ready
from app.services.tenancy import TenantContext

logger = logging.getLogger(__name__)


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
        _require_live_hours(db, tenant.organization_id, current)
        _require_live_room(db, tenant.organization_id, day, current)
        _require_platform_capacity(db, tenant.organization_id, day, current)
        day.started_at = current
        db.commit()
    window = live_room_window(db, tenant.organization_id, day, current)
    return {
        "course_day_id": day.id,
        "started_at": _aware(day.started_at),
        "closes_at": window.entries_close,
        "ends_by": window.ends_by,
    }


ROOM_OPENS_BEFORE = timedelta(minutes=15)
ROOM_CLOSES_AFTER = timedelta(minutes=15)
# Said to a teacher whose class cannot start because the live servers are full: it names no cause.
ROOM_UNAVAILABLE = "Impossible d'ouvrir la salle pour le moment. Réessayez dans quelques minutes."
CAPACITY_ALERT_EVERY = timedelta(hours=1)
_capacity_alert_lock = threading.Lock()
_last_capacity_alert: datetime | None = None


def _scheduled_close(day: SessionCourseDayRecord) -> datetime:
    return _aware(day.scheduled_at) + timedelta(minutes=day.duration_minutes) + ROOM_CLOSES_AFTER


def _cap(plan, feature_key: str) -> int | None:
    """A plan's limit that applies only when the plan names it (live hours)."""
    rule = allowance(plan, feature_key)
    return rule.limit if rule.enabled else None


@dataclass(frozen=True)
class LiveWindow:
    """When no one enters a live room any more, and when it ends for everyone (None: no forced end)."""
    entries_close: datetime
    ends_by: datetime | None


def _live_month(db: Session, organization_id: int, current: datetime) -> tuple[dict[int, LiveWindow], int, int | None]:
    """The school's live classes started this month with their windows, the seconds of live
    used, and the minutes its plan grants a month (None: no limit).

    A room takes entries until 15 minutes after the planned end. It ends for everyone
    live_class_hours after the teacher started it. Live hours count only while the room is in
    use, someone (teacher or student) in it: they pause while it stands empty
    (live_active_seconds, credited by each participant's heartbeat). Once the month's hours are
    used, an open room ends.
    """
    plan = get_effective_plan(db, organization_id)
    per_class = _cap(plan, "live_class_hours")
    monthly = _cap(plan, "live_hours")
    quota = monthly * 60 if monthly is not None else None
    month = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days = db.scalars(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.organization_id == organization_id,
        SessionCourseDayRecord.started_at.is_not(None),
        SessionCourseDayRecord.started_at >= month,
    ).order_by(SessionCourseDayRecord.started_at, SessionCourseDayRecord.id)).all()
    used_seconds = sum(day.live_active_seconds or 0 for day in days)
    seconds_left = None if quota is None else max(0, quota * 60 - used_seconds)
    windows: dict[int, LiveWindow] = {}
    for day in days:
        started = _aware(day.started_at)
        ends_by = started + timedelta(hours=per_class) if per_class is not None else None
        if seconds_left is not None and day.report_submitted_at is None:
            hours_end = current + timedelta(seconds=seconds_left)
            ends_by = hours_end if ends_by is None else min(ends_by, hours_end)
        entries_close = _scheduled_close(day) if ends_by is None else min(_scheduled_close(day), ends_by)
        windows[day.id] = LiveWindow(entries_close, ends_by)
    return windows, used_seconds, quota


# A room is in use while someone in it sends a sign of presence at least every 90 seconds
# (heartbeats come every 30 seconds): a longer silence means it stood empty.
ROOM_IDLE_AFTER = timedelta(seconds=90)


def _credit_room_activity(db: Session, day: SessionCourseDayRecord, current: datetime) -> None:
    """Someone is in the started live room now: the time since its last sign of use counts,
    unless the room stood empty in between."""
    if day.started_at is None:
        return
    db.refresh(day, with_for_update=True)  # participants' heartbeats arrive together
    last = _aware(day.live_active_at) if day.live_active_at is not None else None
    if last is not None and current > last and current - last <= ROOM_IDLE_AFTER:
        day.live_active_seconds = (day.live_active_seconds or 0) + int((current - last).total_seconds())
    if last is None or current > last:
        day.live_active_at = current
    db.commit()


def live_room_window(db: Session, organization_id: int, day: SessionCourseDayRecord, current: datetime) -> LiveWindow:
    """This class's window (see _live_month); before it starts, entries until 15 minutes after its end."""
    if day.started_at is not None:
        windows, _used, _quota = _live_month(db, organization_id, current)
        if day.id in windows:
            return windows[day.id]
    return LiveWindow(_scheduled_close(day), None)


def _require_live_hours(db: Session, organization_id: int, current: datetime) -> None:
    """Découverte grants so many live hours a month: once used, no new class starts this month."""
    _windows, used_seconds, quota = _live_month(db, organization_id, current)
    if quota is None or used_seconds < quota * 60:
        return
    plan = get_effective_plan(db, organization_id)
    raise HTTPException(
        409,
        f"Les {quota // 60} h de live incluses chaque mois dans votre forfait {plan.name} sont utilisées. "
        "Elles reviennent le 1er du mois prochain ; les forfaits payants n'ont pas cette limite.",
    )


def _expected_students(db: Session, day: SessionCourseDayRecord, class_sizes: dict[int, int | None]) -> int:
    """The students a live class can bring: its session's enrolled students, up to its plan's class size."""
    if day.organization_id not in class_sizes:
        rule = allowance(get_effective_plan(db, day.organization_id), "live")
        class_sizes[day.organization_id] = rule.limit if rule.enabled else 0
    enrolled = db.scalar(select(func.count(EnrollmentRecord.id)).where(
        EnrollmentRecord.organization_id == day.organization_id,
        EnrollmentRecord.session_id == day.session_id,
        EnrollmentRecord.status.in_(["active", "completed"]),
    )) or 0
    size = class_sizes[day.organization_id]
    return enrolled if size is None else min(enrolled, size)


def _require_platform_capacity(db: Session, organization_id: int, day: SessionCourseDayRecord, current: datetime) -> None:
    """All schools share the live servers: a class starts only if the students it can bring fit
    beside those of the classes running, below LIVE_PLATFORM_MAX_PARTICIPANTS."""
    ceiling = settings.live_platform_max_participants
    if ceiling <= 0:
        return
    started = db.scalars(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id != day.id,
        SessionCourseDayRecord.started_at.is_not(None),
        SessionCourseDayRecord.started_at >= current - timedelta(days=1),
        SessionCourseDayRecord.report_submitted_at.is_(None),
        SessionCourseDayRecord.status != "cancelled",
    )).all()
    class_sizes: dict[int, int | None] = {}
    booked = sum(_expected_students(db, other, class_sizes) for other in started if current <= _scheduled_close(other))
    booked += _expected_students(db, day, class_sizes)
    if booked <= ceiling:
        return
    db.rollback()
    _alert_capacity(db, organization_id, booked, ceiling, current)
    raise HTTPException(409, ROOM_UNAVAILABLE)


def _alert_capacity(db: Session, organization_id: int, booked: int, ceiling: int, current: datetime) -> None:
    """Tells the platform, at most once an hour, that live classes waited for room: time for a relay."""
    global _last_capacity_alert
    logger.warning("Live capacity reached: %s students for a ceiling of %s (school %s).", booked, ceiling, organization_id)
    recipient = settings.support_email
    if not recipient:
        return
    with _capacity_alert_lock:
        if _last_capacity_alert is not None and current - _last_capacity_alert < CAPACITY_ALERT_EVERY:
            return
        _last_capacity_alert = current
    organization = db.get(OrganizationRecord, organization_id)
    school = organization.name if organization else f"#{organization_id}"

    def send() -> None:
        try:
            send_support_request_email(
                recipient=recipient, reference="LIVE-CAPACITE", requester_name="Plateforme",
                requester_email=recipient, organization_name=school, organization_id=organization_id,
                category="technical", priority="urgent", subject="Capacité live atteinte",
                message=(
                    f"Un cours en live de {school} n'a pas pu démarrer : {booked} étudiants prévus en même temps "
                    f"pour un plafond de {ceiling} (LIVE_PLATFORM_MAX_PARTICIPANTS).\n\n"
                    "Ajoutez un relais vidéo (infra/live/README.md), puis relevez le plafond dans Coolify."
                ),
                page_url=None,
            )
        except Exception:  # an alert must never break a request
            logger.exception("Unable to send the live capacity alert.")

    threading.Thread(target=send, daemon=True).start()


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
    current = datetime.now(UTC)
    windows, used_seconds, quota = _live_month(db, tenant.organization_id, current)
    window = windows.get(day.id, LiveWindow(_scheduled_close(day), None))
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
        "closes_at": window.entries_close,
        "ends_by": window.ends_by,
        "started_at": _aware(day.started_at) if day.started_at else None,
        "moderator": bool(manager or teacher),
        "responsible_teacher": bool(teacher and day.teacher_id == tenant.user.id),
        "live_minutes_left": max(0, quota * 60 - used_seconds) // 60 if quota is not None and (manager or teacher) else None,
    }


def join_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
    device_id: str | None = None, device_label: str | None = None,
) -> dict:
    day, session, manager, teacher, student = _live_class_access(db, tenant, course_day_id)

    current = _aware(now or datetime.now(UTC))
    starts_at = _aware(day.scheduled_at)
    ends_at = starts_at + timedelta(minutes=day.duration_minutes)
    window = live_room_window(db, tenant.organization_id, day, current)
    if window.ends_by is not None and current >= window.ends_by:
        raise HTTPException(403, "Ce cours en live est terminé : sa salle est fermée.")
    if current < starts_at - ROOM_OPENS_BEFORE or current > window.entries_close:
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
    _credit_room_activity(db, day, current)

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
        "ends_by": window.ends_by,
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
    window = live_room_window(db, tenant.organization_id, day, current)
    # Past its forced end (live_class_hours, or the month's live hours spent), the room is over.
    if window.ends_by is not None and current >= window.ends_by:
        raise HTTPException(404, "Ce cours en live est terminé : sa salle est fermée.")
    student_only = bool(student and not (manager or teacher))
    if student_only:
        _hold_live_device(db, tenant, day, device_id, device_label, current)
    _credit_room_activity(db, day, current)
    return {"roll_call": _roll_call_view(db, tenant, day, current, student_only=student_only), "ends_by": window.ends_by}


def leave_live_class(
    db: Session, tenant: TenantContext, course_day_id: int, *, now: datetime | None = None,
    device_id: str | None = None,
) -> None:
    """Frees the device at once, even once the class is closed; the room's time in use counts until now."""
    current = _aware(now or datetime.now(UTC))
    presence = db.scalar(select(LiveRoomPresenceRecord).where(
        LiveRoomPresenceRecord.organization_id == tenant.organization_id,
        LiveRoomPresenceRecord.course_day_id == course_day_id,
        LiveRoomPresenceRecord.user_id == tenant.user.id,
        LiveRoomPresenceRecord.device_id == _device_id(device_id, tenant.user.id),
    ))
    if presence is not None and presence.left_at is None:
        _credit_time_in_room(presence, current)
        presence.last_seen_at = current
        presence.left_at = current
        db.commit()
    day = db.scalar(select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.id == course_day_id,
        SessionCourseDayRecord.organization_id == tenant.organization_id,
    ))
    if day is not None and day.report_submitted_at is None:
        _credit_room_activity(db, day, current)


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
