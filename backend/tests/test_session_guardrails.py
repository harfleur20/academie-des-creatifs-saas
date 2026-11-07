from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.formations import SessionCreate, SessionUpdate
from app.services.formations import create_session, update_session
from app.services.tenancy import resolve_tenant_context


def school():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    owner = UserRecord(email="owner@school.test", full_name="Owner", status="active")
    org = OrganizationRecord(name="School", slug="school", status="active", is_active=True, contact_email="o@school.test")
    db.add_all([owner, org])
    db.flush()
    db.add(OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active"))
    db.commit()
    return db, org, owner, resolve_tenant_context(db, user=owner, organization_id=org.id)


def formation(db, org, format_type):
    record = FormationRecord(
        organization_id=org.id,
        slug=f"formation-{format_type}",
        title="Formation",
        description="Description",
        short_description="Courte",
        cover_image_url="https://example.test/cover.jpg",
        public_program="Programme",
        status="published",
        format_type=format_type,
        price_cents=300_000,
        currency="XAF",
    )
    db.add(record)
    db.commit()
    return record


def session_payload(**values):
    today = datetime.now(UTC).date()
    return SessionCreate(**{
        "label": "Cohorte",
        "start_date": today + timedelta(days=10),
        "end_date": today + timedelta(days=40),
        "seat_capacity": 10,
        **values,
    })


def saved_session(db, record):
    return db.scalar(select(FormationSessionRecord).where(FormationSessionRecord.formation_id == record.id))


def enroll(db, org, session, count):
    for index in range(count):
        student = UserRecord(email=f"student{index}@school.test", full_name=f"Student {index}", status="active")
        db.add(student)
        db.flush()
        db.add(EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=student.id, status="active"))
    db.commit()


@pytest.mark.parametrize("place", [None, "   "])
def test_onsite_session_requires_a_place(place):
    db, org, _owner, tenant = school()
    record = formation(db, org, "presentiel")
    with pytest.raises(HTTPException) as exc:
        create_session(db, tenant, record.id, session_payload(campus_label=place))
    assert exc.value.status_code == 422
    assert "lieu" in exc.value.detail


@pytest.mark.parametrize("format_type", ["live", "presentiel"])
def test_guided_session_requires_at_least_one_seat(format_type):
    db, org, _owner, tenant = school()
    record = formation(db, org, format_type)
    with pytest.raises(HTTPException) as exc:
        create_session(db, tenant, record.id, session_payload(campus_label="Douala", seat_capacity=0))
    assert exc.value.status_code == 422
    assert "place" in exc.value.detail


def test_onsite_place_is_trimmed_and_cannot_be_removed():
    db, org, _owner, tenant = school()
    record = formation(db, org, "presentiel")
    create_session(db, tenant, record.id, session_payload(campus_label="  Douala  "))
    session = saved_session(db, record)
    assert session.campus_label == "Douala"
    with pytest.raises(HTTPException) as exc:
        update_session(db, tenant, record.id, session.id, SessionUpdate(campus_label=" "))
    assert exc.value.status_code == 422
    assert session.campus_label == "Douala"


def test_live_session_never_stores_a_place():
    db, org, _owner, tenant = school()
    record = formation(db, org, "live")
    create_session(db, tenant, record.id, session_payload(campus_label="Yaoundé"))
    session = saved_session(db, record)
    assert session.campus_label is None
    update_session(db, tenant, record.id, session.id, SessionUpdate(campus_label="Douala"))
    assert session.campus_label is None


def test_capacity_cannot_drop_below_enrolled_and_reserved_seats():
    db, org, owner, tenant = school()
    record = formation(db, org, "live")
    create_session(db, tenant, record.id, session_payload())
    session = saved_session(db, record)
    enroll(db, org, session, 2)
    db.add(StudentOrderRecord(
        organization_id=org.id,
        user_id=owner.id,
        formation_id=record.id,
        session_id=session.id,
        order_number="ORDER-1",
        status="pending",
        base_price_cents=300_000,
        final_price_cents=300_000,
        currency="XAF",
    ))
    db.commit()

    with pytest.raises(HTTPException) as exc:
        update_session(db, tenant, record.id, session.id, SessionUpdate(seat_capacity=2))
    assert exc.value.status_code == 409
    assert session.seat_capacity == 10

    update_session(db, tenant, record.id, session.id, SessionUpdate(seat_capacity=3))
    assert session.seat_capacity == 3


def test_expired_reservation_does_not_hold_a_seat():
    db, org, owner, tenant = school()
    record = formation(db, org, "live")
    create_session(db, tenant, record.id, session_payload())
    session = saved_session(db, record)
    enroll(db, org, session, 2)
    db.add(StudentOrderRecord(
        organization_id=org.id,
        user_id=owner.id,
        formation_id=record.id,
        session_id=session.id,
        order_number="ORDER-OLD",
        status="pending",
        base_price_cents=300_000,
        final_price_cents=300_000,
        currency="XAF",
        created_at=datetime.now(UTC) - timedelta(minutes=settings.commerce_reservation_minutes + 1),
    ))
    db.commit()

    update_session(db, tenant, record.id, session.id, SessionUpdate(seat_capacity=2))
    assert session.seat_capacity == 2


def test_session_dates_cannot_leave_a_planned_course_day_outside():
    db, org, owner, tenant = school()
    record = formation(db, org, "presentiel")
    create_session(db, tenant, record.id, session_payload(campus_label="Douala"))
    session = saved_session(db, record)
    day = SessionCourseDayRecord(
        organization_id=org.id,
        session_id=session.id,
        teacher_id=owner.id,
        title="Séance",
        scheduled_at=datetime.combine(session.start_date + timedelta(days=5), datetime.min.time(), tzinfo=UTC),
    )
    db.add(day)
    db.commit()
    moved_start = session.start_date + timedelta(days=10)
    original_start = session.start_date

    with pytest.raises(HTTPException) as exc:
        update_session(db, tenant, record.id, session.id, SessionUpdate(start_date=moved_start))
    assert exc.value.status_code == 409
    assert session.start_date == original_start

    day.status = "cancelled"
    db.commit()
    update_session(db, tenant, record.id, session.id, SessionUpdate(start_date=moved_start))
    assert session.start_date == moved_start


def test_incomplete_older_session_can_close_but_must_be_fixed_to_reopen():
    db, org, _owner, tenant = school()
    record = formation(db, org, "presentiel")
    today = datetime.now(UTC).date()
    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=record.id,
        label="Ancienne cohorte",
        start_date=today + timedelta(days=10),
        end_date=today + timedelta(days=40),
        seat_capacity=0,
        status="open",
    )
    db.add(session)
    db.commit()

    update_session(db, tenant, record.id, session.id, SessionUpdate(status="planned"))
    assert session.status == "planned"

    with pytest.raises(HTTPException) as exc:
        update_session(db, tenant, record.id, session.id, SessionUpdate(status="open"))
    assert exc.value.status_code == 422
    assert session.status == "planned"

    update_session(db, tenant, record.id, session.id, SessionUpdate(campus_label="Douala", seat_capacity=20))
    update_session(db, tenant, record.id, session.id, SessionUpdate(status="open"))
    assert session.status == "open"


def test_online_access_dates_stay_editable_with_unlimited_seats():
    db, org, _owner, tenant = school()
    record = formation(db, org, "ligne")
    today = datetime.now(UTC).date()
    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=record.id,
        label="Accès en ligne",
        start_date=today,
        end_date=today + timedelta(days=365),
        seat_capacity=0,
        status="open",
    )
    db.add(session)
    db.commit()

    update_session(db, tenant, record.id, session.id, SessionUpdate(end_date=today + timedelta(days=30)))
    assert session.end_date == today + timedelta(days=30)
    assert session.seat_capacity == 0
