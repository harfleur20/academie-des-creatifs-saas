from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import (
    BillingInvoiceRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.schemas.subscriptions import DemoCheckoutCreate
from app.services.billing_payments import (
    confirm_demo_payment_attempt,
    create_demo_payment_attempt,
)
from app.services.subscriptions import (
    apply_subscription_lifecycle,
    list_invoices,
    request_cancel_at_period_end,
)
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    org = OrganizationRecord(name="School", slug="school")
    starter = PlanRecord(
        code="starter",
        name="Starter",
        currency="EUR",
        monthly_price_cents=1900,
        annual_price_cents=19000,
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    pro = PlanRecord(
        code="pro",
        name="Pro",
        currency="EUR",
        monthly_price_cents=4900,
        annual_price_cents=49000,
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    db.add_all([owner, org, starter, pro])
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
    )
    db.commit()
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    return owner, org, starter, pro, tenant


def enable_demo(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)
    monkeypatch.setattr(settings, "billing_grace_period_days", 7)


def test_active_subscription_becomes_past_due_then_suspended(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    _, org, starter, _, _ = seed(db)
    now = datetime.now(UTC)
    subscription = SubscriptionRecord(
        organization_id=org.id,
        plan_id=starter.id,
        status="active",
        billing_interval="monthly",
        started_at=now - timedelta(days=31),
        current_period_start=now - timedelta(days=31),
        current_period_end=now - timedelta(days=1),
    )
    db.add(subscription)
    db.commit()
    subscription.plan = starter

    changed = apply_subscription_lifecycle(db, subscription, now=now)
    db.commit()

    assert changed is True
    assert subscription.status == "past_due"
    assert subscription.grace_period_ends_at is not None
    open_invoice = db.query(BillingInvoiceRecord).filter_by(
        subscription_id=subscription.id,
        status="open",
    ).one()
    assert open_invoice.amount_cents == 1900

    later = now + timedelta(days=8)
    changed_again = apply_subscription_lifecycle(db, subscription, now=later)
    db.commit()

    assert changed_again is True
    assert subscription.status == "suspended"
    assert subscription.suspended_at is not None


def test_cancel_at_period_end_is_respected(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    _, org, starter, _, tenant = seed(db)
    now = datetime.now(UTC)
    subscription = SubscriptionRecord(
        organization_id=org.id,
        plan_id=starter.id,
        status="active",
        billing_interval="monthly",
        started_at=now - timedelta(days=20),
        current_period_start=now - timedelta(days=20),
        current_period_end=now + timedelta(days=10),
    )
    db.add(subscription)
    db.commit()

    scheduled = request_cancel_at_period_end(db, tenant)
    assert scheduled.cancel_at_period_end is True

    subscription.plan = starter
    apply_subscription_lifecycle(
        db,
        subscription,
        now=now + timedelta(days=11),
    )
    db.commit()
    assert subscription.status == "cancelled"


def test_same_plan_payment_renews_existing_subscription(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    _, org, starter, _, tenant = seed(db)
    now = datetime.now(UTC)
    old_end = now + timedelta(days=5)
    subscription = SubscriptionRecord(
        organization_id=org.id,
        plan_id=starter.id,
        status="active",
        billing_interval="monthly",
        started_at=now - timedelta(days=25),
        current_period_start=now - timedelta(days=25),
        current_period_end=old_end,
    )
    db.add(subscription)
    db.commit()

    attempt = create_demo_payment_attempt(
        db,
        tenant,
        plan_code="starter",
        billing_interval="monthly",
    )
    _, renewed = confirm_demo_payment_attempt(
        db,
        tenant,
        payment_attempt_id=attempt.id,
    )

    assert renewed.id == subscription.id
    assert renewed.current_period_end > old_end
    invoices = list_invoices(db, org.id)
    assert len(invoices) == 1
    assert invoices[0].status == "paid"
    assert invoices[0].payment_attempt_id == attempt.id


def test_plan_change_cancels_old_and_creates_new_subscription(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    _, org, starter, pro, tenant = seed(db)
    now = datetime.now(UTC)
    old = SubscriptionRecord(
        organization_id=org.id,
        plan_id=starter.id,
        status="active",
        billing_interval="monthly",
        started_at=now - timedelta(days=5),
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=25),
    )
    db.add(old)
    db.commit()

    attempt = create_demo_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )
    _, changed = confirm_demo_payment_attempt(
        db,
        tenant,
        payment_attempt_id=attempt.id,
    )

    db.refresh(old)
    assert old.status == "cancelled"
    assert changed.id != old.id
    assert changed.plan_id == pro.id
    assert changed.status == "active"



def test_cancelled_trial_ends_as_cancelled(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    _, org, starter, _, tenant = seed(db)
    now = datetime.now(UTC)
    trial_end = now + timedelta(days=2)
    subscription = SubscriptionRecord(
        organization_id=org.id,
        plan_id=starter.id,
        status="trialing",
        billing_interval="monthly",
        started_at=now,
        trial_ends_at=trial_end,
        current_period_start=now,
        current_period_end=trial_end,
    )
    db.add(subscription)
    db.commit()

    request_cancel_at_period_end(db, tenant)
    subscription.plan = starter
    apply_subscription_lifecycle(
        db,
        subscription,
        now=trial_end + timedelta(minutes=1),
    )
    db.commit()

    assert subscription.status == "cancelled"
    assert subscription.cancelled_at is not None
    assert subscription.suspended_at is None


def test_past_due_cancellation_is_immediate_and_voids_invoice(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    _, org, starter, _, tenant = seed(db)
    now = datetime.now(UTC)
    subscription = SubscriptionRecord(
        organization_id=org.id,
        plan_id=starter.id,
        status="active",
        billing_interval="monthly",
        started_at=now - timedelta(days=31),
        current_period_start=now - timedelta(days=31),
        current_period_end=now - timedelta(days=1),
    )
    db.add(subscription)
    db.commit()
    subscription.plan = starter
    apply_subscription_lifecycle(db, subscription, now=now)
    db.commit()

    assert subscription.status == "past_due"
    invoice = db.query(BillingInvoiceRecord).filter_by(
        subscription_id=subscription.id,
        status="open",
    ).one()

    updated = request_cancel_at_period_end(db, tenant)
    db.refresh(invoice)

    assert updated.status == "cancelled"
    assert invoice.status == "void"
    assert invoice.due_at is None
