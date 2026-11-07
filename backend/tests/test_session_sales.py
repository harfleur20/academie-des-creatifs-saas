from datetime import UTC, datetime, timedelta

from test_school_commerce import build_db, demo_payments, seed  # noqa: F401  (demo_payments is an autouse fixture)

from app.models.entities import FormationSessionRecord
from app.services.public_catalog import public_formation_detail


def add_session(db, org, formation, label: str, start_in_days: int, length_days: int) -> FormationSessionRecord:
    now = datetime.now(UTC)
    session = FormationSessionRecord(
        organization_id=org.id, formation_id=formation.id, label=label,
        start_date=(now + timedelta(days=start_in_days)).date(),
        end_date=(now + timedelta(days=start_in_days + length_days)).date(),
        seat_capacity=20, status="open",
    )
    db.add(session)
    db.commit()
    return session


def test_sessions_still_to_start_come_before_running_ones() -> None:
    db = build_db()
    org, _user, formation, upcoming = seed(db)  # starts in 30 days
    running = add_session(db, org, formation, "Déjà commencée", start_in_days=-3, length_days=60)
    sooner = add_session(db, org, formation, "Bientôt", start_in_days=12, length_days=40)

    detail = public_formation_detail(db, org.slug, formation.slug)
    assert all(item.can_purchase for item in detail.sessions)
    assert [item.id for item in detail.sessions] == [sooner.id, upcoming.id, running.id]
    assert detail.next_session.id == sooner.id


def test_a_running_session_is_still_shown_when_nothing_else_is_open() -> None:
    db = build_db()
    org, _user, formation, upcoming = seed(db)
    upcoming.status = "completed"
    db.commit()
    running = add_session(db, org, formation, "Déjà commencée", start_in_days=-3, length_days=60)

    detail = public_formation_detail(db, org.slug, formation.slug)
    assert detail.next_session.id == running.id and detail.can_purchase
