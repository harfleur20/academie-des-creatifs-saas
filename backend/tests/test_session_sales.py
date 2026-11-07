from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_school_commerce import build_db, demo_payments, seed  # noqa: F401  (demo_payments is an autouse fixture)

from app.models.entities import FormationSessionRecord, OrderInstallmentRecord
from app.schemas.commerce import CheckoutCreate
from app.services.public_catalog import public_formation_detail
from app.services.school_commerce import create_checkout, price_preview
from app.services.session_payment_plans import split_amounts


def installments(db, order_id: int) -> list[OrderInstallmentRecord]:
    return list(db.scalars(select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.order_id == order_id,
    ).order_by(OrderInstallmentRecord.sequence)).all())


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


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


def test_the_session_length_caps_the_school_instalment_count() -> None:
    db = build_db()
    org, user, formation, session = seed(db)  # a 70-day session: three payments at most
    formation.installment_count = 6
    db.commit()

    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    assert preview.installments_allowed and preview.installment_count == 3
    detail = public_formation_detail(db, org.slug, formation.slug)
    assert detail.allow_installments and detail.installment_count == 3

    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="installments"))
    rows = installments(db, checkout.order_id)
    assert checkout.installment_count == 3
    assert [row.amount_cents for row in rows] == [100_000, 100_000, 100_000]
    dues = [aware(row.due_at) for row in rows]
    assert abs(dues[0] - datetime.now(UTC)) < timedelta(minutes=1)
    assert all(later - earlier >= timedelta(days=7) for earlier, later in zip(dues, dues[1:]))
    assert dues[-1].date() <= session.end_date - timedelta(days=5)


def test_the_school_count_still_applies_below_the_cap() -> None:
    db = build_db()
    org, user, formation, session = seed(db)  # the school allows two payments
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="installments"))
    rows = installments(db, checkout.order_id)
    assert [row.amount_cents for row in rows] == [150_000, 150_000]
    assert aware(rows[-1].due_at).date() <= session.end_date - timedelta(days=5)


def test_a_session_shorter_than_a_month_takes_a_single_payment() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    session.end_date = session.start_date + timedelta(days=20)
    db.commit()

    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    assert not preview.installments_allowed and preview.installment_count == 1
    assert public_formation_detail(db, org.slug, formation.slug).allow_installments is False
    with pytest.raises(HTTPException) as refused:
        create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="installments"))
    assert refused.value.status_code == 422


def test_fcfa_instalments_are_rounded_to_500_and_add_up() -> None:
    assert split_amounts(250_000, 3, "XAF") == [83_000, 83_000, 84_000]
    assert split_amounts(1_000, 3, "XAF") == [334, 333, 333]  # too small to round: an exact split
    assert split_amounts(1_000, 3, "EUR") == [333, 333, 334]
