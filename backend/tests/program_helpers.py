from datetime import UTC, datetime

from app.models.entities import SessionProgramVersionRecord


def frozen_program(session) -> SessionProgramVersionRecord:
    """These fixtures test the badge itself: their minimal program counts as already frozen."""
    return SessionProgramVersionRecord(
        organization_id=session.organization_id, session_id=session.id, version=1,
        frozen_at=datetime.now(UTC), requirements_json={},
    )
