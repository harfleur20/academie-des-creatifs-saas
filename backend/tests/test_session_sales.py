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


def plan_of(db, org, user, session) -> list[tuple[int, object]]:
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="installments"))
    return [(row.amount_cents, aware(row.due_at).date()) for row in installments(db, checkout.order_id)]


def set_session(db, formation, session, *, price: int, school_max: int, starts_in: int, ends_in: int) -> None:
    today = datetime.now(UTC).date()
    formation.price_cents, formation.installment_count = price, school_max
    session.start_date, session.end_date = today + timedelta(days=starts_in), today + timedelta(days=ends_in)
    db.commit()


def test_the_price_and_the_time_left_cap_the_school_count() -> None:
    db = build_db()
    org, user, formation, session = seed(db)  # 300 000 FCFA, ends in 100 days
    formation.installment_count = 12
    db.commit()
    # 35 000 FCFA at least each: 8 payments; the 95 days left would allow 14 a week apart.
    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    assert preview.installments_allowed and preview.installment_count == 8
    assert public_formation_detail(db, org.slug, formation.slug).installment_count == 8

    plan = plan_of(db, org, user, session)
    assert [amount for amount, _due in plan] == [37_500] * 8
    dues = [due for _amount, due in plan]
    assert dues[0] == datetime.now(UTC).date()
    assert all((later - earlier).days >= 7 for earlier, later in zip(dues, dues[1:]))
    assert dues[-1] == session.end_date - timedelta(days=5)


def test_a_one_month_session_can_be_paid_in_three_times_within_the_month() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    set_session(db, formation, session, price=500_000, school_max=3, starts_in=0, ends_in=30)
    today = datetime.now(UTC).date()
    assert plan_of(db, org, user, session) == [
        (166_500, today), (166_500, today + timedelta(days=12)), (167_000, today + timedelta(days=25)),
    ]


def test_the_school_count_still_applies_below_the_cap() -> None:
    db = build_db()
    org, user, formation, session = seed(db)  # the school allows two payments
    plan = plan_of(db, org, user, session)
    assert [amount for amount, _due in plan] == [150_000, 150_000]
    assert plan[-1][1] == session.end_date - timedelta(days=5)


@pytest.mark.parametrize(("price", "count"), [(65_000, 1), (69_999, 1), (70_000, 2), (104_999, 2), (105_000, 3)])
def test_from_70000_fcfa_and_35000_fcfa_a_payment(price: int, count: int) -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    set_session(db, formation, session, price=price, school_max=6, starts_in=30, ends_in=100)
    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    assert (preview.installments_allowed, preview.installment_count) == (count > 1, count)
    if count == 1:
        with pytest.raises(HTTPException) as refused:
            create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="installments"))
        assert refused.value.status_code == 422


@pytest.mark.parametrize(("ends_in", "count"), [(11, 1), (12, 2), (18, 2), (19, 3)])
def test_payments_stay_a_week_apart_and_end_five_days_before_the_session(ends_in: int, count: int) -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    set_session(db, formation, session, price=500_000, school_max=6, starts_in=0, ends_in=ends_in)
    assert price_preview(db, org, user_id=user.id, session_id=session.id).installment_count == count


def test_an_online_formation_is_paid_a_month_apart() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    formation.format_type = "ligne"
    set_session(db, formation, session, price=120_000, school_max=6, starts_in=0, ends_in=365)
    today = datetime.now(UTC).date()
    assert plan_of(db, org, user, session) == [
        (40_000, today), (40_000, today + timedelta(days=30)), (40_000, today + timedelta(days=60)),
    ]


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


def schedule_of(db, order_id: int) -> list[tuple[int, object]]:
    return [(row.amount_cents, aware(row.due_at).date()) for row in installments(db, order_id)]


@pytest.mark.parametrize("deposit", [False, True])
@pytest.mark.parametrize("mode", ["full", "installments"])
def test_the_checkout_shows_the_payments_each_choice_creates(deposit: bool, mode: str) -> None:
    db, org, user, formation, session = deposit_school()
    formation.reservation_deposit_enabled = deposit
    formation.installment_count = 3
    db.commit()
    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    announced = preview.schedule_full if mode == "full" else preview.schedule_installments
    assert announced[0].due_date == datetime.now(UTC).date()
    assert sum(line.amount_cents for line in announced) == preview.final_price_cents
    expected_count = {(False, "full"): 1, (True, "full"): 2, (False, "installments"): 3, (True, "installments"): 3}
    assert len(announced) == expected_count[(deposit, mode)]

    checkout = create_checkout(db, org, user, CheckoutCreate(
        session_id=session.id, payment_mode=mode, accept_deposit_terms=deposit,
    ))
    assert schedule_of(db, checkout.order_id) == [(line.amount_cents, line.due_date) for line in announced]


def test_no_instalment_plan_is_announced_when_none_is_offered() -> None:
    db, org, user, formation, session = deposit_school()
    formation.allow_installments = False
    db.commit()
    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    assert preview.schedule_installments == [] and len(preview.schedule_full) == 2  # the deposit, then the balance


def test_the_formation_page_announces_the_payments_of_the_checkout() -> None:
    db, org, user, formation, session = deposit_school()
    formation.installment_count = 3
    db.commit()
    preview = price_preview(db, org, user_id=user.id, session_id=session.id)
    shown = next(item for item in public_formation_detail(db, org.slug, formation.slug).sessions if item.id == session.id)
    assert (shown.deposit_cents, shown.deposit_percent, shown.balance_cents, shown.balance_due_date) == (
        preview.deposit_cents, preview.deposit_percent, preview.balance_cents, preview.balance_due_date,
    )
    assert shown.deposit_cents == 112_500 and shown.schedule_installments == preview.schedule_installments

    formation.reservation_deposit_enabled = False
    formation.allow_installments = False
    db.commit()
    shown = next(item for item in public_formation_detail(db, org.slug, formation.slug).sessions if item.id == session.id)
    assert shown.deposit_cents is None and shown.schedule_installments == []
