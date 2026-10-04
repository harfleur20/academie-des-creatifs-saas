"""School-scoped equivalents of the mother site's course availability rules."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models.entities import FormationRecord, FormationSessionRecord, SessionCourseDayRecord


PARIS = ZoneInfo("Europe/Paris")


def dashboard_type(formation: FormationRecord) -> str:
    return "classic" if formation.format_type == "ligne" else "guided"


def current_utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def session_starts_at(session: FormationSessionRecord) -> datetime:
    return datetime.combine(session.start_date, time.min, tzinfo=PARIS).astimezone(UTC)


def learning_is_open(
    formation: FormationRecord,
    session: FormationSessionRecord,
    *,
    now: datetime | None = None,
) -> bool:
    if session.status == "cancelled":
        return False
    if dashboard_type(formation) == "classic":
        return True
    return current_utc(now) >= session_starts_at(session)


def require_learning_open(
    formation: FormationRecord,
    session: FormationSessionRecord,
) -> None:
    if not learning_is_open(formation, session):
        raise HTTPException(409, "Cette session n'a pas encore commencé ou a été annulée.")


def guided_activity_available(
    formation: FormationRecord,
    session: FormationSessionRecord,
    *,
    scheduled_at: datetime | None = None,
    day: SessionCourseDayRecord | None = None,
    published_at: datetime | None = None,
    now: datetime | None = None,
) -> bool:
    if session.status == "cancelled":
        return False
    if day is not None and day.status in {"cancelled", "not_held", "missed"}:
        return False
    if not learning_is_open(formation, session, now=now):
        if published_at is None or current_utc(published_at) >= session_starts_at(session):
            return False
        # A resource explicitly published before the session is preparatory.
        return current_utc(now) >= current_utc(published_at)
    opening = session_starts_at(session)
    if scheduled_at is not None:
        opening = max(opening, current_utc(scheduled_at))
    if day is not None:
        opening = max(opening, current_utc(day.scheduled_at))
    if published_at is not None:
        opening = max(opening, current_utc(published_at))
    return current_utc(now) >= opening
