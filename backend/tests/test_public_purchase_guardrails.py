from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrderInstallmentRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.commerce import CheckoutCreate
from app.services.membership_roles import load_effective_member_roles
from app.services.purchase_policy import review_blocked_staff_payment
from app.services.school_branding import get_or_create_identity_records
from app.services.school_commerce import (
    confirm_demo_checkout,
    create_checkout,
    create_installment_payment_link,
)


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed_sale(db: Session):
    org = OrganizationRecord(
        name="Guardrail School",
        slug="guardrail-school",
        subdomain="guardrail-school",
        status="active",
        is_active=True,
        contact_email="contact@guardrail.test",
    )
    user = UserRecord(
        email="buyer@guardrail.test",
        full_name="Buyer Guardrail",
        status="active",
        platform_role="user",
    )
    db.add_all([org, user])
    db.flush()

    site, legal, *_ = get_or_create_identity_records(db, org)
    site.student_code_prefix = "GR"
    site.student_code_prefix_confirmed_at = datetime.now(UTC)
    site.legal_notice = "Mentions légales Guardrail School"
    site.sales_terms = "Conditions de vente Guardrail School"
    site.privacy_policy = "Politique de confidentialité Guardrail School"
    site.refund_policy = "Politique de remboursement Guardrail School"
    site.is_published = True
    legal.legal_name = "Guardrail School SARL"
    legal.legal_address = "1 rue des Tests"
    legal.invoice_email = "invoice@guardrail.test"

    formation = FormationRecord(
        organization_id=org.id,
        slug="formation-test",
        title="Formation test",
        description="Description complète",
        short_description="Formation de test",
        cover_image_url="https://example.test/formation.jpg",
        public_program="Programme public",
        status="published",
        format_type="live",
        price_cents=300_000,
        currency="XAF",
        allow_installments=True,
        installment_count=2,
    )
    db.add(formation)
    db.flush()
    now = datetime.now(UTC)
    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=formation.id,
        label="Session test",
        start_date=(now + timedelta(days=30)).date(),
        end_date=(now + timedelta(days=100)).date(),
        seat_capacity=20,
        status="open",
        enrollment_open_at=now - timedelta(days=30),
        enrollment_close_at=now + timedelta(days=29),
    )
    db.add(session)
    db.commit()
    return org, user, formation, session


@pytest.fixture(autouse=True)
def demo_payments(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)


def test_checkout_requires_authenticated_account() -> None:
    client = TestClient(app)
    response = client.post(
        f"{settings.api_prefix}/commerce/public/guardrail-school/checkout",
        json={"session_id": 1, "payment_mode": "full"},
    )
    assert response.status_code == 401


def test_checkout_does_not_create_student_access_before_payment() -> None:
    db = build_db()
    org, user, _formation, session = seed_sale(db)

    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="full"),
    )
    assert checkout.status == "pending"
    assert db.scalar(select(OrganizationMemberRecord.id).where(
        OrganizationMemberRecord.organization_id == org.id,
        OrganizationMemberRecord.user_id == user.id,
    )) is None
    assert db.scalar(select(OrganizationStudentProfileRecord.id).where(
        OrganizationStudentProfileRecord.organization_id == org.id,
        OrganizationStudentProfileRecord.user_id == user.id,
    )) is None
    assert db.scalar(select(EnrollmentRecord.id).where(
        EnrollmentRecord.organization_id == org.id,
        EnrollmentRecord.student_id == user.id,
        EnrollmentRecord.session_id == session.id,
    )) is None


def test_another_user_cannot_confirm_or_pay_someone_elses_order() -> None:
    db = build_db()
    org, user, _formation, session = seed_sale(db)
    other = UserRecord(
        email="other@guardrail.test",
        full_name="Other User",
        status="active",
        platform_role="user",
    )
    db.add(other)
    db.commit()

    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="installments"),
    )
    first = db.scalar(select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.order_id == checkout.order_id,
        OrderInstallmentRecord.sequence == 1,
    ))

    with pytest.raises(HTTPException) as confirm_error:
        confirm_demo_checkout(db, org, other, checkout.order_id, checkout.provider_reference)
    assert confirm_error.value.status_code == 404

    with pytest.raises(HTTPException) as pay_error:
        create_installment_payment_link(db, org, other, first.id)
    assert pay_error.value.status_code == 404


def test_second_installment_cannot_be_paid_before_first() -> None:
    db = build_db()
    org, user, _formation, session = seed_sale(db)
    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="installments"),
    )
    second = db.scalar(select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.order_id == checkout.order_id,
        OrderInstallmentRecord.sequence == 2,
    ))
    assert second is not None

    with pytest.raises(HTTPException) as exc:
        create_installment_payment_link(db, org, user, second.id)
    assert exc.value.status_code == 409
    assert "échéances précédentes" in str(exc.value.detail)


def test_existing_enrollment_cannot_buy_same_session_again() -> None:
    db = build_db()
    org, user, _formation, session = seed_sale(db)
    db.add(EnrollmentRecord(
        organization_id=org.id,
        session_id=session.id,
        student_id=user.id,
        status="active",
    ))
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_checkout(
            db,
            org,
            user,
            CheckoutCreate(session_id=session.id, payment_mode="full"),
        )
    assert exc.value.status_code == 409
    assert "déjà inscrit" in str(exc.value.detail)


def test_staff_payment_confirmation_goes_to_review_without_student_access(monkeypatch) -> None:
    db = build_db()
    org, user, _formation, session = seed_sale(db)
    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="full"),
    )

    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=user.id,
        role="teacher",
        status="active",
    )
    db.add(member)
    db.commit()

    monkeypatch.setattr(
        "app.services.purchase_policy.verify_payment",
        lambda reference: SimpleNamespace(
            status="paid",
            product_id=reference,
            amount=300_000,
            paid_at=datetime.now(UTC),
        ),
    )

    reviewed = review_blocked_staff_payment(
        db,
        checkout.provider_reference,
        organization_id=org.id,
        user_id=user.id,
    )
    assert reviewed is not None
    assert reviewed.status == "payment_review"
    assert reviewed.access_status == "pending_review"
    assert reviewed.paid_cents == 300_000
    assert load_effective_member_roles(db, member) == frozenset({"teacher"})
    assert db.scalar(select(OrganizationStudentProfileRecord.id).where(
        OrganizationStudentProfileRecord.organization_id == org.id,
        OrganizationStudentProfileRecord.user_id == user.id,
    )) is None
    assert db.scalar(select(EnrollmentRecord.id).where(
        EnrollmentRecord.organization_id == org.id,
        EnrollmentRecord.student_id == user.id,
        EnrollmentRecord.session_id == session.id,
    )) is None


def test_staff_unpaid_order_can_be_cancelled_before_lifecycle() -> None:
    from app.services.purchase_policy import cancel_blocked_staff_unpaid_orders

    db = build_db()
    org, user, _formation, session = seed_sale(db)
    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="full"),
    )
    db.add(OrganizationMemberRecord(
        organization_id=org.id,
        user_id=user.id,
        role="admin",
        status="active",
    ))
    db.commit()

    assert cancel_blocked_staff_unpaid_orders(db, organization_id=org.id) == 1
    order = db.get(StudentOrderRecord, checkout.order_id)
    assert order.status == "cancelled"
    assert order.access_status == "cancelled"
    assert all(
        row.status == "cancelled"
        for row in db.scalars(select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.order_id == order.id,
        )).all()
    )
