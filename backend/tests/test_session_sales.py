from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_school_commerce import build_db, demo_payments, seed  # noqa: F401  (demo_payments is an autouse fixture)

from app.models.entities import EnrollmentRecord, FormationSessionRecord, OrderInstallmentRecord, StudentOrderRecord
from app.schemas.commerce import CheckoutCreate
from app.services.public_catalog import public_formation_detail
from app.services.school_commerce import confirm_demo_checkout, create_checkout, price_preview, process_installment_lifecycle
from app.services.session_payment_plans import reservation_deposit_amount, split_amounts


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


def deposit_school():
    db = build_db()
    org, user, formation, session = seed(db)  # live, 300 000 FCFA, starts in 30 days
    formation.reservation_deposit_enabled = True
    formation.reservation_deposit_percent = 37.5
    db.commit()
    return db, org, user, formation, session


def test_a_live_seat_is_reserved_with_a_deposit_then_the_balance_ten_days_before() -> None:
    db, org, user, _formation, session = deposit_school()
    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    assert (preview.deposit_cents, preview.balance_cents) == (112_500, 187_500)
    assert preview.balance_due_date == session.start_date - timedelta(days=10)

    with pytest.raises(HTTPException) as refused:
        create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    assert refused.value.status_code == 422 and "acompte non remboursable" in refused.value.detail

    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, accept_deposit_terms=True))
    order = db.get(StudentOrderRecord, checkout.order_id)
    assert checkout.deposit_cents == 112_500 and order.deposit_terms_accepted_at is not None
    deposit, balance = installments(db, checkout.order_id)
    assert (deposit.amount_cents, balance.amount_cents) == (112_500, 187_500)
    assert aware(balance.due_at) == datetime.combine(session.start_date - timedelta(days=10), datetime.min.time(), UTC)
    assert aware(balance.grace_until) == aware(balance.due_at)

    paid = confirm_demo_checkout(db, org, user, checkout.order_id)
    assert paid.status == "partially_paid" and paid.access_status == "active"
    seats_before = public_formation_detail(db, org.slug, _formation.slug).sessions[0].seats_remaining

    # Ten days before the start, an unpaid balance suspends access but keeps the seat.
    balance.due_at = balance.grace_until = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert process_installment_lifecycle(db, organization_id=org.id) == 1
    assert db.get(StudentOrderRecord, checkout.order_id).access_status == "suspended_payment"
    assert enrollment_status(db, org, session, user) == "suspended_payment"
    assert public_formation_detail(db, org.slug, _formation.slug).sessions[0].seats_remaining == seats_before

    settled = confirm_demo_checkout(db, org, user, checkout.order_id)
    assert settled.status == "paid" and settled.access_status == "active"
    assert enrollment_status(db, org, session, user) == "active"


def test_a_deposit_can_open_an_instalment_plan() -> None:
    db, org, user, formation, session = deposit_school()
    formation.installment_count = 3
    db.commit()
    checkout = create_checkout(db, org, user, CheckoutCreate(
        session_id=session.id, payment_mode="installments", accept_deposit_terms=True,
    ))
    rows = installments(db, checkout.order_id)
    assert [row.amount_cents for row in rows] == [112_500, 93_500, 94_000]
    assert aware(rows[1].grace_until) == aware(rows[1].due_at)
    assert aware(rows[-1].due_at).date() <= session.end_date - timedelta(days=5)


@pytest.mark.parametrize("change", ["starts_in_ten_days", "presentiel", "disabled"])
def test_no_deposit_outside_its_conditions(change: str) -> None:
    db, org, user, formation, session = deposit_school()
    if change == "starts_in_ten_days":
        session.start_date = (datetime.now(UTC) + timedelta(days=10)).date()
    elif change == "presentiel":
        formation.format_type = "presentiel"
        session.campus_label = "Douala"
    else:
        formation.reservation_deposit_enabled = False
    db.commit()
    assert price_preview(db, org, user_id=user.id, session_id=session.id).deposit_cents is None
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    assert checkout.deposit_cents is None and len(installments(db, checkout.order_id)) == 1


def test_deposit_amounts_follow_the_mother_site() -> None:
    assert reservation_deposit_amount(300_000, 37.5, "XAF") == 112_500
    assert reservation_deposit_amount(250_000, 37.5, "XAF") == 94_000  # 93 750 rounded to 500 FCFA
    assert reservation_deposit_amount(1_000, 99, "XAF") == 500  # never the whole price
    assert reservation_deposit_amount(10_000, 37.5, "EUR") == 3_750


def enrollment_status(db, org, session, user) -> str:
    return db.scalar(select(EnrollmentRecord.status).where(
        EnrollmentRecord.organization_id == org.id,
        EnrollmentRecord.session_id == session.id,
        EnrollmentRecord.student_id == user.id,
    ))


def test_fcfa_instalments_are_rounded_to_500_and_add_up() -> None:
    assert split_amounts(250_000, 3, "XAF") == [83_000, 83_000, 84_000]
    assert split_amounts(1_000, 3, "XAF") == [334, 333, 333]  # too small to round: an exact split
    assert split_amounts(1_000, 3, "EUR") == [333, 333, 334]
