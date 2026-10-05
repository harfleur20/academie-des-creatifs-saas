from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord, FormationSessionRecord


ONLINE_SESSION_LABEL = "Accès en ligne"


def ensure_online_content_session(db: Session, formation: FormationRecord) -> FormationSessionRecord | None:
    """Keep the existing session-based storage behind a sessionless online offer."""
    if formation.format_type != "ligne":
        return None
    existing = db.scalar(
        select(FormationSessionRecord).where(
            FormationSessionRecord.organization_id == formation.organization_id,
            FormationSessionRecord.formation_id == formation.id,
        ).order_by(FormationSessionRecord.id).limit(1)
    )
    if existing is not None:
        return existing
    session = FormationSessionRecord(
        organization_id=formation.organization_id,
        formation_id=formation.id,
        label=ONLINE_SESSION_LABEL,
        start_date=datetime.now(UTC).date(),
        end_date=date.max,
        seat_capacity=0,
        status="open",
    )
    db.add(session)
    db.flush()
    return session
