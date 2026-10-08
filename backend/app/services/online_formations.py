from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord, FormationSessionRecord


ONLINE_SESSION_LABEL = "Accès en ligne"
ONLINE_ACCESS_DEFAULT_DAYS = 365


def _default_online_end_date(start_date: date) -> date:
    """Return a real, finite default access date for an online formation."""
    return start_date + timedelta(days=ONLINE_ACCESS_DEFAULT_DAYS)


def ensure_online_content_session(db: Session, formation: FormationRecord) -> FormationSessionRecord | None:
    """Keep the existing session-based storage behind a sessionless online offer.

    The internal session still needs real dates because these dates are shown in
    the student space and can be edited by the school. Older rows used
    ``date.max`` as a sentinel; normalize them to a one-year access window.
    """
    if formation.format_type != "ligne":
        return None
    existing = db.scalar(
        select(FormationSessionRecord).where(
            FormationSessionRecord.organization_id == formation.organization_id,
            FormationSessionRecord.formation_id == formation.id,
        ).order_by(FormationSessionRecord.id).limit(1)
    )
    if existing is not None:
        if existing.end_date == date.max:
            existing.end_date = _default_online_end_date(existing.start_date)
            db.flush()
        return existing

    start_date = datetime.now(UTC).date()
    session = FormationSessionRecord(
        organization_id=formation.organization_id,
        formation_id=formation.id,
        label=ONLINE_SESSION_LABEL,
        start_date=start_date,
        end_date=_default_online_end_date(start_date),
        seat_capacity=0,
        status="open",
    )
    db.add(session)
    db.flush()
    return session
