from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from test_academic_suite import build_db, ctx, seed
from test_school_commerce import build_db as build_commerce_db
from test_school_commerce import demo_payments  # noqa: F401  (autouse fixture)
from test_school_commerce import seed as seed_commerce

from app.models.entities import (
    CommunicationOutboxRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationMemberRecord,
    SchoolNotificationRecord,
    SessionProgramVersionRecord,
    UserRecord,
)
from app.schemas.formations import SessionUpdate
from app.services.formations import update_session
from app.services.public_catalog import public_formation_detail
from app.services.session_lifecycle import process_session_lifecycle


def notices(db, prefix: str, user_id: int | None = None) -> int:
    query = select(func.count(SchoolNotificationRecord.id)).where(SchoolNotificationRecord.event_key.startswith(prefix))
    if user_id is not None:
        query = query.where(SchoolNotificationRecord.user_id == user_id)
    return int(db.scalar(query) or 0)


def sale_for(start_in_days: int, *, close_at: datetime | None = None):
    db = build_commerce_db()
    org, _user, formation, session = seed_commerce(db)
    today = datetime.now(UTC).date()
    session.start_date = today + timedelta(days=start_in_days)
    session.end_date = session.start_date + timedelta(days=60)
    session.enrollment_close_at = close_at
    db.commit()
    return public_formation_detail(db, org.slug, formation.slug).sessions[0]


def test_enrollment_stays_open_five_days_after_the_start() -> None:
    assert sale_for(-5).can_purchase
    late = sale_for(-6)
    assert not late.can_purchase and "closes depuis le" in late.unavailable_reason


def test_the_school_closing_date_replaces_the_default() -> None:
    assert sale_for(-10, close_at=datetime.now(UTC) + timedelta(days=2)).can_purchase
    assert not sale_for(10, close_at=datetime.now(UTC) - timedelta(hours=1)).can_purchase


def live_school():
    db = build_db()
    org, teacher, student, _classmate, session, *_ = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    manager = UserRecord(email="direction@test.dev", full_name="Direction", status="active")
    db.add(manager)
    db.flush()
    db.add(OrganizationMemberRecord(organization_id=org.id, user_id=manager.id, role="manager", status="active"))
    db.commit()
    return db, org, teacher, student, session, manager


def test_the_hourly_job_completes_ended_sessions() -> None:
    db, _org, *_rest = live_school()
    session = db.scalar(select(FormationSessionRecord))  # ended in February 2025
    assert process_session_lifecycle(db)["completed"] == 1
    assert db.get(FormationSessionRecord, session.id).status == "completed"


def test_a_started_session_is_frozen_or_the_school_is_warned_once() -> None:
    db, org, teacher, student, session, manager = live_school()
    session.end_date = date.today() + timedelta(days=20)
    db.commit()
    assert process_session_lifecycle(db)["frozen"] == 1
    assert db.scalar(select(func.count(SessionProgramVersionRecord.id))) == 1

    db2, org2, _teacher2, _student2, session2, manager2 = live_school()
    session2.end_date = date.today() + timedelta(days=20)
    for day in session2.course_days:
        day.status = "cancelled"  # the program now misses a course day
    db2.commit()
    assert process_session_lifecycle(db2)["incomplete_warnings"] == 1
    assert process_session_lifecycle(db2)["incomplete_warnings"] == 0
    assert notices(db2, f"program.incomplete:{session2.id}", manager2.id) == 1


def test_a_change_of_dates_or_a_cancellation_is_announced() -> None:
    db, org, teacher, student, session, manager = live_school()
    session.status = "planned"
    db.commit()
    tenant = ctx(db, org, manager)
    update_session(db, tenant, session.formation_id, session.id, SessionUpdate(seat_capacity=12))
    assert notices(db, f"session.changed:{session.id}") == 0  # seats are not a change for students

    update_session(db, tenant, session.formation_id, session.id, SessionUpdate(end_date=date(2025, 2, 5)))
    assert notices(db, f"session.changed:{session.id}", student.id) == 1
    assert notices(db, f"session.changed:{session.id}", teacher.id) == 1
    assert db.scalar(select(func.count(CommunicationOutboxRecord.id)).where(
        CommunicationOutboxRecord.event_key == "student.session.updated", CommunicationOutboxRecord.recipient == student.email,
    )) == 1

    update_session(db, tenant, session.formation_id, session.id, SessionUpdate(status="cancelled"))
    cancelled = db.scalars(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.user_id == student.id, SchoolNotificationRecord.event_key.startswith(f"session.changed:{session.id}"),
    )).all()
    assert len(cancelled) == 2 and any(item.title == "Votre session est annulée" for item in cancelled)
