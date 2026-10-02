from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import (
    CouponRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrderInstallmentRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    PromotionRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.commerce import CheckoutCreate
from app.services.public_catalog import public_formation_detail
from app.services.school_branding import get_or_create_identity_records
from app.services.school_commerce import (
    confirm_demo_checkout,
    create_checkout,
    price_preview,
    process_installment_lifecycle,
)


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    org = OrganizationRecord(
        name="School Business",
        slug="school-business",
        status="active",
        is_active=True,
        primary_color="#1122AA",
        secondary_color="#22AA77",
        accent_color="#172033",
    )
    user = UserRecord(
        email="student@test.dev",
        full_name="Francis Test",
        status="active",
    )
    db.add_all([org, user])
    db.flush()
    site, *_ = get_or_create_identity_records(db, org)
    site.student_code_prefix = "SB"
    formation = FormationRecord(
        organization_id=org.id,
        slug="motion-design",
        title="Motion Design",
        description="Description",
        short_description="Court",
        status="published",
        format_type="live",
        price_cents=300_000,
        currency="XAF",
        allow_installments=True,
        installment_count=2,
    )
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(
        organization_id=org.id,
        formation_id=formation.id,
        label="Octobre 2026",
        start_date=date(2026, 10, 10),
        end_date=date(2026, 12, 20),
        seat_capacity=20,
        status="open",
        enrollment_open_at=datetime(2026, 9, 1, tzinfo=UTC),
        enrollment_close_at=datetime(2026, 10, 9, 23, 59, tzinfo=UTC),
    )
    db.add(session)
    db.commit()
    return org, user, formation, session


@pytest.fixture(autouse=True)
def demo_payments(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)


def test_public_formation_requires_available_session(monkeypatch) -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    monkeypatch.setattr("app.services.public_catalog.datetime", datetime)
    detail = public_formation_detail(db, org.slug, formation.slug)
    assert detail.can_purchase is True
    assert detail.available_session_count == 1

    session.status = "completed"
    db.commit()
    detail = public_formation_detail(db, org.slug, formation.slug)
    assert detail.can_purchase is False
    assert detail.available_session_count == 0


def test_promotion_and_coupon_rules() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    promo = PromotionRecord(
        organization_id=org.id,
        name="Rentrée",
        formation_id=formation.id,
        discount_type="percentage",
        discount_value=20,
        is_active=True,
    )
    coupon = CouponRecord(
        organization_id=org.id,
        code="WELCOME10",
        name="Bienvenue",
        discount_type="percentage",
        discount_value=10,
        max_uses_per_customer=1,
        eligible_formation_ids=[],
        eligible_session_ids=[],
        allow_on_promotions=False,
        is_active=True,
    )
    db.add_all([promo, coupon])
    db.commit()

    preview = price_preview(
        db,
        org,
        user_id=user.id,
        session_id=session.id,
    )
    assert preview.base_price_cents == 300_000
    assert preview.promotion_discount_cents == 60_000
    assert preview.final_price_cents == 240_000

    with pytest.raises(HTTPException) as exc:
        price_preview(
            db,
            org,
            user_id=user.id,
            session_id=session.id,
            coupon_code="WELCOME10",
        )
    assert exc.value.status_code == 422

    coupon.allow_on_promotions = True
    db.commit()
    preview = price_preview(
        db,
        org,
        user_id=user.id,
        session_id=session.id,
        coupon_code="WELCOME10",
    )
    assert preview.promotion_discount_cents == 60_000
    assert preview.coupon_discount_cents == 24_000
    assert preview.final_price_cents == 216_000


def test_full_payment_creates_student_profile_membership_and_enrollment() -> None:
    db = build_db()
    org, user, formation, session = seed(db)

    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(
            session_id=session.id,
            payment_mode="full",
        ),
    )
    assert checkout.status == "pending"
    assert checkout.checkout_url is not None

    confirmed = confirm_demo_checkout(db, org, user, checkout.order_id)
    assert confirmed.status == "paid"
    assert confirmed.access_status == "active"
    assert confirmed.paid_cents == 300_000

    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == org.id,
            OrganizationStudentProfileRecord.user_id == user.id,
        )
    )
    assert profile is not None
    assert profile.student_code == "SB26-001"

    member = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == org.id,
            OrganizationMemberRecord.user_id == user.id,
        )
    )
    assert member is not None
    assert member.role == "student"

    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == org.id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.student_id == user.id,
        )
    )
    assert enrollment is not None
    assert enrollment.status == "active"


def test_installment_late_suspends_then_payment_reactivates() -> None:
    db = build_db()
    org, user, formation, session = seed(db)

    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(
            session_id=session.id,
            payment_mode="installments",
        ),
    )
    first = confirm_demo_checkout(db, org, user, checkout.order_id)
    assert first.status == "partially_paid"
    assert first.access_status == "active"
    assert first.paid_cents == 150_000

    second = db.scalar(
        select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.order_id == checkout.order_id,
            OrderInstallmentRecord.sequence == 2,
        )
    )
    second.due_at = datetime.now(UTC) - timedelta(days=10)
    second.grace_until = datetime.now(UTC) - timedelta(days=2)
    db.commit()

    assert process_installment_lifecycle(db, organization_id=org.id) == 1
    order = db.get(StudentOrderRecord, checkout.order_id)
    assert order.status == "late"
    assert order.access_status == "suspended_payment"

    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == org.id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.student_id == user.id,
        )
    )
    assert enrollment.status == "suspended_payment"

    confirmed = confirm_demo_checkout(db, org, user, checkout.order_id)
    assert confirmed.status == "paid"
    assert confirmed.access_status == "active"
    assert confirmed.paid_cents == 300_000
    db.refresh(enrollment)
    assert enrollment.status == "active"
