from datetime import UTC, datetime
import hashlib
import hmac
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import (
    BillingPaymentAttemptRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanRecord,
    UserRecord,
)
from app.services import billing_payments
from app.services.billing_payments import (
    create_tara_payment_attempt,
    reconcile_tara_attempt,
)
from app.services.tara_money import TaraPaymentSession, TaraPaymentVerification
from app.services.tara_webhook import verify_webhook_authentication
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session, *, currency: str = "XAF"):
    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    org = OrganizationRecord(name="School", slug="school")
    pro = PlanRecord(
        code="pro",
        name="Pro",
        currency=currency,
        monthly_price_cents=25000,
        annual_price_cents=250000,
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    db.add_all([owner, org, pro])
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
    return owner, org, pro, tenant


def enable_tara(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "production")
    monkeypatch.setattr(settings, "tara_api_key", "test-key")
    monkeypatch.setattr(settings, "tara_business_id", "business-1")
    monkeypatch.setattr(settings, "tara_webhook_secret", "secret-1")


def test_tara_checkout_requires_xaf(monkeypatch) -> None:
    enable_tara(monkeypatch)
    db = build_db()
    _, _, _, tenant = seed(db, currency="EUR")

    with pytest.raises(HTTPException) as exc:
        create_tara_payment_attempt(
            db,
            tenant,
            plan_code="pro",
            billing_interval="monthly",
        )

    assert exc.value.status_code == 422


def test_tara_checkout_creates_local_attempt_and_checkout(monkeypatch) -> None:
    enable_tara(monkeypatch)
    db = build_db()
    _, org, _, tenant = seed(db)

    monkeypatch.setattr(
        billing_payments,
        "create_payment_link",
        lambda **kwargs: TaraPaymentSession(
            provider_reference=kwargs["product_id"],
            checkout_url="https://tara.example/checkout",
        ),
    )

    attempt, checkout_url = create_tara_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )

    assert attempt.organization_id == org.id
    assert attempt.provider == "taramoney"
    assert attempt.status == "pending"
    assert attempt.amount_cents == 25000
    assert attempt.provider_reference.startswith(f"SAAS-{org.id}-")
    assert checkout_url == "https://tara.example/checkout"
    assert attempt.checkout_url == checkout_url


def test_tara_paid_verification_activates_subscription(monkeypatch) -> None:
    enable_tara(monkeypatch)
    db = build_db()
    _, _, _, tenant = seed(db)

    monkeypatch.setattr(
        billing_payments,
        "create_payment_link",
        lambda **kwargs: TaraPaymentSession(
            provider_reference=kwargs["product_id"],
            checkout_url="https://tara.example/checkout",
        ),
    )
    attempt, _ = create_tara_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="annual",
    )

    monkeypatch.setattr(
        billing_payments,
        "verify_payment",
        lambda product_id: TaraPaymentVerification(
            status="paid",
            product_id=product_id,
            business_id="business-1",
            amount=250000,
            paid_at=datetime.now(UTC),
            transaction_id="TX-001",
        ),
    )

    payment, subscription, result = reconcile_tara_attempt(
        db,
        provider_reference=attempt.provider_reference,
        organization_id=tenant.organization_id,
    )

    assert result == "paid"
    assert payment.status == "paid"
    assert payment.provider_transaction_id == "TX-001"
    assert payment.activated_subscription_id == subscription.id
    assert subscription.provider == "taramoney"
    assert subscription.billing_interval == "annual"


def test_tara_amount_mismatch_never_activates(monkeypatch) -> None:
    enable_tara(monkeypatch)
    db = build_db()
    _, _, _, tenant = seed(db)

    monkeypatch.setattr(
        billing_payments,
        "create_payment_link",
        lambda **kwargs: TaraPaymentSession(
            provider_reference=kwargs["product_id"],
            checkout_url="https://tara.example/checkout",
        ),
    )
    attempt, _ = create_tara_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )

    monkeypatch.setattr(
        billing_payments,
        "verify_payment",
        lambda product_id: TaraPaymentVerification(
            status="paid",
            product_id=product_id,
            amount=1000,
            paid_at=datetime.now(UTC),
            transaction_id="TX-BAD",
        ),
    )

    with pytest.raises(HTTPException) as exc:
        reconcile_tara_attempt(
            db,
            provider_reference=attempt.provider_reference,
            organization_id=tenant.organization_id,
        )

    assert exc.value.status_code == 409
    db.rollback()
    stored = db.get(BillingPaymentAttemptRecord, attempt.id)
    assert stored.status == "pending"
    assert stored.activated_subscription_id is None


def test_same_tara_transaction_cannot_activate_two_attempts(monkeypatch) -> None:
    enable_tara(monkeypatch)
    db = build_db()
    _, _, _, tenant = seed(db)

    monkeypatch.setattr(
        billing_payments,
        "create_payment_link",
        lambda **kwargs: TaraPaymentSession(
            provider_reference=kwargs["product_id"],
            checkout_url="https://tara.example/checkout",
        ),
    )
    first, _ = create_tara_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )
    second, _ = create_tara_payment_attempt(
        db,
        tenant,
        plan_code="pro",
        billing_interval="monthly",
    )

    monkeypatch.setattr(
        billing_payments,
        "verify_payment",
        lambda product_id: TaraPaymentVerification(
            status="paid",
            product_id=product_id,
            amount=25000,
            paid_at=datetime.now(UTC),
            transaction_id="TX-SAME",
        ),
    )

    reconcile_tara_attempt(
        db,
        provider_reference=first.provider_reference,
        organization_id=tenant.organization_id,
    )

    with pytest.raises(HTTPException) as exc:
        reconcile_tara_attempt(
            db,
            provider_reference=second.provider_reference,
            organization_id=tenant.organization_id,
        )

    assert exc.value.status_code == 409


def test_tara_webhook_hmac_is_checked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tara_webhook_secret", "top-secret")
    monkeypatch.setattr(settings, "tara_webhook_secret_header", "")

    body = json.dumps({"productId": "SAAS-1-abc"}).encode()
    signature = hmac.new(
        b"top-secret",
        body,
        hashlib.sha256,
    ).hexdigest()

    headers = {"x-taramoney-signature": signature}
    assert verify_webhook_authentication(body, headers) is True
    assert verify_webhook_authentication(body, {"x-taramoney-signature": "0" * 64}) is False
