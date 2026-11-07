from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from test_academic_suite import build_db, ctx, seed

from app.models.entities import FormationRecord
from app.schemas.formations import FormationUpdate
from app.services.formations import update_formation


def school(start_in_days: int, length_days: int, status: str = "open"):
    db = build_db()
    org, teacher, _student, _classmate, session, *_ = seed(db)
    today = datetime.now(UTC).date()
    session.start_date = today + timedelta(days=start_in_days)
    session.end_date = session.start_date + timedelta(days=length_days)
    session.status = status
    db.commit()
    return db, ctx(db, org, teacher), session


def test_a_running_session_blocks_the_archive() -> None:
    db, tenant, session = school(start_in_days=-3, length_days=30)
    with pytest.raises(HTTPException) as refused:
        update_formation(db, tenant, session.formation_id, FormationUpdate(status="archived"))
    assert refused.value.status_code == 409 and "est en cours" in refused.value.detail
    assert db.get(FormationRecord, session.formation_id).status != "archived"


@pytest.mark.parametrize(("start_in_days", "length_days", "status"), [
    (20, 30, "open"),        # still to come: the page warns, the archive goes through
    (-60, 30, "open"),       # already over
    (-3, 30, "cancelled"),   # cancelled while it ran
    (-3, 30, "completed"),
])
def test_other_sessions_let_the_formation_be_archived(start_in_days: int, length_days: int, status: str) -> None:
    db, tenant, session = school(start_in_days, length_days, status)
    assert update_formation(db, tenant, session.formation_id, FormationUpdate(status="archived")).status == "archived"
