"""The school's time zone: the founder's own at creation, checked when changed, used for its sessions' days."""
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from test_academic_suite import build_db
from test_plans_and_revenue import plans

from app.models.entities import FormationRecord, FormationSessionRecord, OrganizationRecord, UserRecord
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate
from app.services.organizations import create_organization
from app.services.pedagogy_access import session_ends_at, session_starts_at


def test_a_new_school_takes_its_founders_time_zone_and_an_unknown_one_leaves_utc():
    db = build_db()
    plans(db)
    owner = UserRecord(email="fondatrice@test.dev", full_name="Fondatrice", status="active")
    db.add(owner)
    db.commit()

    douala = create_organization(db, user=owner, payload=OrganizationCreate(
        name="École Douala", slug="ecole-douala", timezone="Africa/Douala"))
    assert douala.timezone == "Africa/Douala"

    # A browser that sends nothing usable never blocks the creation: the school starts on UTC.
    assert OrganizationCreate(name="Mars", slug="mars", timezone="Mars/Base").timezone is None
    mars = create_organization(db, user=owner, payload=OrganizationCreate(name="Mars", slug="mars", timezone="Mars/Base"))
    assert mars.timezone == "UTC"


def test_the_settings_refuse_an_unknown_time_zone():
    assert OrganizationUpdate(timezone="Europe/Paris").timezone == "Europe/Paris"
    with pytest.raises(ValidationError, match="Fuseau horaire inconnu"):
        OrganizationUpdate(timezone="Mars/Base")


@pytest.mark.parametrize(("zone", "opens", "closes"), [
    # Douala is UTC+1 all year: midnight there is 23:00 UTC the day before.
    ("Africa/Douala", datetime(2026, 3, 31, 23, 0, tzinfo=UTC), datetime(2026, 4, 30, 23, 0, tzinfo=UTC)),
    ("UTC", datetime(2026, 4, 1, 0, 0, tzinfo=UTC), datetime(2026, 5, 1, 0, 0, tzinfo=UTC)),
    # Toronto in April is UTC-4: midnight there is 04:00 UTC.
    ("America/Toronto", datetime(2026, 4, 1, 4, 0, tzinfo=UTC), datetime(2026, 5, 1, 4, 0, tzinfo=UTC)),
])
def test_a_session_opens_and_closes_at_midnight_in_the_schools_own_time_zone(zone, opens, closes):
    db = build_db()
    org = OrganizationRecord(name="École", slug="ecole", timezone=zone)
    db.add(org)
    db.flush()
    formation = FormationRecord(organization_id=org.id, slug="motion", title="Motion Design", format_type="live")
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(organization_id=org.id, formation_id=formation.id, label="Avril",
                                     start_date=date(2026, 4, 1), end_date=date(2026, 4, 30), status="open")
    db.add(session)
    db.flush()

    assert session_starts_at(session) == opens
    assert session_ends_at(session) == closes
