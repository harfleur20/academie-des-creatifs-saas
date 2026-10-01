from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.services.billing_payments import (
    confirm_demo_payment_attempt,
    create_demo_payment_attempt,
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
        monthly_price_cents=None,
        annual_price_cents=None,
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
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=starter.id,
            status="trialing",
            billing_interval="monthly",
            started_at=settings_demo_now(),
        )
    )
    db.commit()
    return owner, org, starter, pro


def settings_demo_now():
    from datetime import UTC, datetime
    return datetime.now(UTC)


def enable_demo(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)
    monkeypatch.setattr(settings, "demo_payment_amount_cents", 100)


def test_demo_checkout_uses_configured_plan_price(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    owner, org, _, pro = seed(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    attempt = create_demo_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )

    assert attempt.provider == "demo"
    assert attempt.status == "pending"
    assert attempt.amount_cents == pro.monthly_price_cents


def test_demo_checkout_uses_test_amount_when_price_is_not_configured(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    owner, org, starter, _ = seed(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    attempt = create_demo_payment_attempt(
        db,
        tenant,
        plan_code=starter.code,
        billing_interval="monthly",
    )

    assert attempt.amount_cents == 100


def test_demo_confirmation_activates_selected_plan(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    owner, org, _, pro = seed(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    attempt = create_demo_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="annual",
    )
    payment, subscription = confirm_demo_payment_attempt(
        db,
        tenant,
        payment_attempt_id=attempt.id,
    )

    assert payment.status == "paid"
    assert subscription.status == "active"
    assert subscription.plan_id == pro.id
    assert subscription.billing_interval == "annual"
    assert subscription.provider == "demo"


def test_demo_confirmation_is_idempotent(monkeypatch) -> None:
    enable_demo(monkeypatch)
    db = build_db()
    owner, org, _, _ = seed(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    attempt = create_demo_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )
    _, first = confirm_demo_payment_attempt(
        db,
        tenant,
        payment_attempt_id=attempt.id,
    )
    _, second = confirm_demo_payment_attempt(
        db,
        tenant,
        payment_attempt_id=attempt.id,
    )

    assert first.id == second.id


def test_demo_mode_is_refused_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)

    db = build_db()
    owner, org, _, _ = seed(db)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        create_demo_payment_attempt(
            db,
            tenant,
            plan_code="pro",
            billing_interval="monthly",
        )

    assert exc.value.status_code == 403
