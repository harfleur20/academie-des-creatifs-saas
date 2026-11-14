"""Live classes within their plan and the platform: 6 hours a month on Découverte, 4 hours at
most per class, and a ceiling on the students the live servers carry at once (docs/FORFAITS.md)."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from test_academic_suite import build_db, ctx, seed
from test_plans_and_revenue import NOW, plans

from app.core.config import settings
from app.models.entities import FormationRecord, SessionCourseDayRecord, SubscriptionRecord
from app.schemas.planning import CourseDayCreate
from app.services.live_classes import (
    ROOM_UNAVAILABLE, _live_month, heartbeat_live_class, live_room_window, start_live_class,
)
from app.services.planning import create_course_day

NINE = datetime(2025, 1, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def live_school(monkeypatch):
    """A live formation on a plan, its teacher, an enrolled student and a first class at 9:00."""
    # Teacher readiness has its own tests; this fixture's teacher predates onboarding.
    monkeypatch.setattr("app.services.live_classes.require_teacher_ready", lambda db, tenant: None)

    def make(plan_code: str):
        db = build_db()
        grid_plans = plans(db)
        org, teacher, student, _classmate, session, _enrollment, _other, _lesson, day = seed(db)
        db.get(FormationRecord, session.formation_id).format_type = "live"
        day.scheduled_at, day.duration_minutes = NINE, 120
        db.add(SubscriptionRecord(organization_id=org.id, plan_id=grid_plans[plan_code].id, status="active",
                                  billing_interval="monthly", started_at=NOW, current_period_start=NOW,
                                  current_period_end=NOW + timedelta(days=30)))
        db.commit()
        return db, org, teacher, student, session, day

    return make


def another_class(db, org, session, teacher, start: datetime, minutes: int = 120) -> SessionCourseDayRecord:
    day = SessionCourseDayRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Cours",
                                 scheduled_at=start, duration_minutes=minutes, status="planned")
    db.add(day)
    db.commit()
    return day


def in_room(db, org, day, user, start: datetime, minutes: int, *, device: str = "phone") -> None:
    """Someone in the live room for so many minutes: a heartbeat every 30 seconds."""
    tenant = ctx(db, org, user)
    for second in range(0, minutes * 60 + 1, 30):
        heartbeat_live_class(db, tenant, day.id, now=start + timedelta(seconds=second), device_id=device)


def test_decouverte_counts_live_hours_only_while_the_room_is_in_use(live_school):
    db, org, teacher, student, _session, first = live_school("decouverte")
    start_live_class(db, ctx(db, org, teacher), first.id, now=NINE)
    # Ten minutes with the teacher in the room, then nobody for an hour, then twenty minutes
    # with a student: thirty minutes used, the empty hour not counted.
    in_room(db, org, first, teacher, NINE, 10)
    in_room(db, org, first, student, NINE + timedelta(hours=1, minutes=10), 20)
    _windows, used_seconds, quota = _live_month(db, org.id, NINE + timedelta(hours=2))
    assert (used_seconds, quota * 60 - used_seconds) == (30 * 60, 330 * 60)


def test_decouverte_runs_six_hours_of_live_a_month(live_school):
    db, org, teacher, student, session, first = live_school("decouverte")
    tenant = ctx(db, org, teacher)
    start_live_class(db, tenant, first.id, now=NINE)
    # Five hours fifty used this month already.
    first.live_active_seconds, first.report_submitted_at = 350 * 60, NINE + timedelta(hours=4)
    db.commit()

    # The next class starts; once in use, it ends when the last ten minutes are used.
    second = another_class(db, org, session, teacher, NINE + timedelta(days=1), minutes=240)
    start_live_class(db, tenant, second.id, now=NINE + timedelta(days=1))
    in_room(db, org, second, student, NINE + timedelta(days=1), 9)
    window = live_room_window(db, org.id, second, NINE + timedelta(days=1, minutes=9))
    assert window.ends_by == NINE + timedelta(days=1, minutes=10)
    in_room(db, org, second, student, NINE + timedelta(days=1, minutes=9, seconds=30), 0)
    in_room(db, org, second, student, NINE + timedelta(days=1, minutes=9, seconds=60), 0)
    # The 6 hours are used: the room is over for its students.
    with pytest.raises(HTTPException) as over:
        heartbeat_live_class(db, ctx(db, org, student), second.id, now=NINE + timedelta(days=1, minutes=10, seconds=30),
                             device_id="phone")
    assert over.value.status_code == 404

    # And no class starts again this month.
    third = another_class(db, org, session, teacher, NINE + timedelta(days=2))
    with pytest.raises(HTTPException) as used:
        start_live_class(db, tenant, third.id, now=NINE + timedelta(days=2))
    assert used.value.status_code == 409
    assert "6 h de live" in used.value.detail and "Découverte" in used.value.detail

    # Next month, the hours are back.
    february = another_class(db, org, session, teacher, datetime(2025, 2, 1, 9, 0, tzinfo=UTC))
    assert start_live_class(db, tenant, february.id, now=datetime(2025, 2, 1, 9, 0, tzinfo=UTC))["started_at"]


def test_a_paid_plan_ends_a_live_class_four_hours_after_its_start(live_school):
    db, org, teacher, _student, _session, first = live_school("pro")
    started = start_live_class(db, ctx(db, org, teacher), first.id, now=NINE)
    assert started["ends_by"] == NINE + timedelta(hours=4)
    # No monthly hours on a paid plan: the forced end stays at 4 hours.
    window = live_room_window(db, org.id, first, NINE + timedelta(hours=1))
    assert window.ends_by == NINE + timedelta(hours=4)
    assert window.entries_close == NINE + timedelta(hours=2, minutes=15)


def test_a_live_class_is_planned_for_four_hours_at_most(live_school):
    db, org, teacher, _student, session, _first = live_school("business")
    tenant = ctx(db, org, teacher)
    with pytest.raises(HTTPException) as too_long:
        create_course_day(db, tenant, session.id, CourseDayCreate(
            title="Atelier", scheduled_at=datetime(2025, 1, 20, 8, 0, tzinfo=UTC), duration_minutes=300))
    assert too_long.value.status_code == 422
    assert "4 h au plus" in too_long.value.detail
    create_course_day(db, tenant, session.id, CourseDayCreate(
        title="Atelier", scheduled_at=datetime(2025, 1, 20, 8, 0, tzinfo=UTC), duration_minutes=240))

    # In person, a class lasts as long as the school wants.
    db.get(FormationRecord, session.formation_id).format_type = "presentiel"
    db.commit()
    create_course_day(db, tenant, session.id, CourseDayCreate(
        title="Journée", scheduled_at=datetime(2025, 1, 21, 8, 0, tzinfo=UTC), duration_minutes=480))


def test_a_class_waits_when_the_live_servers_are_full(live_school, monkeypatch):
    db, org, teacher, _student, _session, first = live_school("pro")
    tenant = ctx(db, org, teacher)
    # Two students enrolled: above a ceiling of one, the class cannot start, without saying why.
    monkeypatch.setattr(settings, "live_platform_max_participants", 1)
    with pytest.raises(HTTPException) as full:
        start_live_class(db, tenant, first.id, now=NINE)
    assert (full.value.status_code, full.value.detail) == (409, ROOM_UNAVAILABLE)
    assert db.get(SessionCourseDayRecord, first.id).started_at is None

    monkeypatch.setattr(settings, "live_platform_max_participants", 2)
    assert start_live_class(db, tenant, first.id, now=NINE)["started_at"]

    # Without a ceiling (0), nothing is counted.
    monkeypatch.setattr(settings, "live_platform_max_participants", 0)
