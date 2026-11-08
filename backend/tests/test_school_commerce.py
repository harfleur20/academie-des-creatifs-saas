from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import (
    ChapterRecord,
    CouponRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    CommunicationOutboxRecord,
    OrderInstallmentRecord,
    OrderInvoiceRecord,
    OrganizationMemberRecord,
    OrganizationDomainRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    PromotionRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.commerce import CheckoutCreate
from app.services.public_catalog import public_formation_detail
from app.services.school_documents import build_invoice_pdf
from app.services.school_branding import get_or_create_identity_records
from app.services.school_commerce import (
    cancel_pending_order,
    commercial_dashboard,
    confirm_demo_checkout,
    create_checkout,
    price_preview,
    process_installment_lifecycle,
    reconcile_tara_reference,
    verified_return_origin,
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
        contact_email="contact@example.com",
        subdomain="school-business",
    )
    user = UserRecord(
        email="student@test.dev",
        full_name="Francis Test",
        status="active",
    )
    db.add_all([org, user])
    db.flush()
    site, legal, *_ = get_or_create_identity_records(db, org)
    site.student_code_prefix = "SB"
    site.student_code_prefix_confirmed_at = datetime.now(UTC)
    site.legal_notice = "Mentions légales de School Business"
    site.sales_terms = "Conditions de vente de School Business"
    site.privacy_policy = "Politique de confidentialité de School Business"
    site.refund_policy = "Politique de remboursement de School Business"
    site.is_published = True
    legal.legal_name = "School Business SARL"
    legal.legal_address = "12 rue des écoles"
    legal.invoice_email = "factures@example.com"
    formation = FormationRecord(
        organization_id=org.id,
        slug="motion-design",
        title="Motion Design",
        description="Description",
        short_description="Court",
        cover_image_url="https://example.test/motion-design.jpg",
        public_program="Fondamentaux du motion design",
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


def test_public_formation_exposes_published_modules_from_next_session() -> None:
    db = build_db()
    org, _user, formation, session = seed(db)
    course = CourseRecord(
        organization_id=org.id,
        session_id=session.id,
        title="Fondamentaux",
        description="",
        status="published",
    )
    db.add(course)
    db.flush()
    db.add(
        ChapterRecord(
            organization_id=org.id,
            course_id=course.id,
            title="Principes de base",
            order_index=0,
        )
    )
    db.commit()

    detail = public_formation_detail(db, org.slug, formation.slug)
    assert len(detail.modules) == 1
    assert detail.modules[0].title == "Fondamentaux"
    assert detail.modules[0].chapters == ["Principes de base"]


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
    assert profile.student_code == f"SB{datetime.now(UTC):%y}-001"

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


def test_checkout_reuses_pending_order_and_reserves_last_seat() -> None:
    db = build_db()
    org, user, _formation, session = seed(db)
    session.seat_capacity = 1
    other = UserRecord(email="other@test.dev", full_name="Other Student", status="active")
    db.add(other)
    db.commit()
    payload = CheckoutCreate(session_id=session.id, payment_mode="installments")
    first = create_checkout(db, org, user, payload)
    repeated = create_checkout(db, org, user, payload)
    assert repeated.order_id == first.order_id
    assert repeated.checkout_url == first.checkout_url
    assert len(db.scalars(select(StudentOrderRecord)).all()) == 1
    with pytest.raises(HTTPException) as exc:
        create_checkout(db, org, other, payload)
    assert exc.value.status_code == 409

    paid = confirm_demo_checkout(db, org, user, first.order_id, first.provider_reference)
    assert paid.status == "partially_paid"
    repeated_return = confirm_demo_checkout(db, org, user, first.order_id, first.provider_reference)
    assert repeated_return.paid_cents == paid.paid_cents


def test_unpaid_demo_reservation_expires_without_enrollment() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    session.seat_capacity = 1
    db.commit()
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    order = db.get(StudentOrderRecord, checkout.order_id)
    order.created_at = datetime.now(UTC) - timedelta(minutes=settings.commerce_reservation_minutes + 1)
    db.commit()
    assert process_installment_lifecycle(db, organization_id=org.id) == 1
    assert db.get(StudentOrderRecord, checkout.order_id).status == "cancelled"
    assert price_preview(db, org, user_id=user.id, session_id=session.id).final_price_cents == formation.price_cents
    with pytest.raises(HTTPException):
        confirm_demo_checkout(db, org, user, checkout.order_id, checkout.provider_reference)


def test_expired_tara_reservation_releases_seat_and_late_payment_needs_review(monkeypatch) -> None:
    db = build_db()
    org, user, _formation, session = seed(db)
    session.seat_capacity = 1
    other = UserRecord(email="late-seat@test.dev", full_name="Other Student", status="active")
    db.add(other)
    db.commit()
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    order = db.get(StudentOrderRecord, checkout.order_id)
    first = db.scalar(select(OrderInstallmentRecord).where(OrderInstallmentRecord.order_id == order.id))
    order.payment_provider = "taramoney"
    first.provider_reference = "TARA-LATE-REF"
    order.created_at = datetime.now(UTC) - timedelta(minutes=settings.commerce_reservation_minutes + 1)
    db.commit()

    assert public_formation_detail(db, org.slug, "motion-design").can_purchase is True
    next_checkout = create_checkout(db, org, other, CheckoutCreate(session_id=session.id))
    db.refresh(order)
    assert order.status == "cancelled"
    assert next_checkout.order_id != order.id

    monkeypatch.setattr("app.services.school_commerce.verify_payment", lambda reference: SimpleNamespace(
        status="paid", product_id=reference, amount=first.amount_cents, paid_at=datetime.now(UTC),
    ))
    reviewed = reconcile_tara_reference(db, first.provider_reference)
    assert reviewed.status == "payment_review"
    assert reviewed.access_status == "pending_review"
    assert reviewed.paid_cents == first.amount_cents
    assert db.scalar(select(EnrollmentRecord.id).where(
        EnrollmentRecord.organization_id == org.id,
        EnrollmentRecord.student_id == user.id,
        EnrollmentRecord.session_id == session.id,
    )) is None
    assert db.get(StudentOrderRecord, next_checkout.order_id).status == "pending"


def test_tara_pending_payment_does_not_hold_seat_after_reservation_expires(monkeypatch) -> None:
    db = build_db()
    org, user, _formation, session = seed(db)
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    order = db.get(StudentOrderRecord, checkout.order_id)
    first = db.scalar(select(OrderInstallmentRecord).where(OrderInstallmentRecord.order_id == order.id))
    order.payment_provider = "taramoney"
    order.created_at = datetime.now(UTC) - timedelta(minutes=settings.commerce_reservation_minutes + 1)
    first.provider_reference = "TARA-STILL-PENDING"
    db.commit()
    monkeypatch.setattr("app.services.school_commerce.verify_payment", lambda _reference: SimpleNamespace(status="pending"))

    assert process_installment_lifecycle(db, organization_id=org.id) == 1
    db.refresh(order)
    assert order.status == "cancelled"
    assert first.status == "cancelled"


def test_student_can_cancel_pending_demo_order() -> None:
    db = build_db()
    org, user, _formation, session = seed(db)
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    cancelled = cancel_pending_order(db, org, user, checkout.order_id)
    assert cancelled.status == "cancelled"
    assert create_checkout(db, org, user, CheckoutCreate(session_id=session.id)).order_id != checkout.order_id


def test_unpublished_site_cannot_start_new_sale() -> None:
    db = build_db()
    org, user, _formation, session = seed(db)
    site = db.scalar(select(OrganizationPublicSiteRecord).where(OrganizationPublicSiteRecord.organization_id == org.id))
    site.is_published = False
    db.commit()
    with pytest.raises(HTTPException) as exc:
        create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    assert exc.value.status_code == 404


def test_payment_return_origin_must_belong_to_school(monkeypatch) -> None:
    db = build_db()
    org, _user, _formation, _session = seed(db)
    monkeypatch.setattr(settings, "frontend_url", "https://platform.test")
    monkeypatch.setattr(settings, "saas_base_domain", "schools.test")
    org.subdomain = "business"
    db.add(OrganizationDomainRecord(organization_id=org.id, hostname="school.example", status="verified", verification_token="test"))
    db.commit()
    assert verified_return_origin(db, org, "https://school.example") == "https://school.example"
    assert verified_return_origin(db, org, "https://business.schools.test") == "https://business.schools.test"
    assert verified_return_origin(db, org, "https://attacker.example") == "https://platform.test"
    assert verified_return_origin(db, org, "https://school.example:444") == "https://platform.test"


def test_commerce_totals_are_separated_by_currency() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    create_checkout(db, org, user, CheckoutCreate(session_id=session.id))
    second = UserRecord(email="eur@test.dev", full_name="Euro Student", status="active")
    formation_eur = FormationRecord(organization_id=org.id, slug="design-eur", title="Design EUR", description="Test", cover_image_url="https://example.test/design-eur.jpg", public_program="Programme Design EUR", status="published", format_type="live", price_cents=25000, currency="EUR")
    db.add_all([second, formation_eur])
    db.flush()
    session_eur = FormationSessionRecord(organization_id=org.id, formation_id=formation_eur.id, label="EUR", start_date=session.start_date, end_date=session.end_date, seat_capacity=10, status="open")
    db.add(session_eur)
    db.commit()
    create_checkout(db, org, second, CheckoutCreate(session_id=session_eur.id))
    dashboard = commercial_dashboard(db, SimpleNamespace(support_mode=False, organization_roles={"manager"}, organization_id=org.id))
    assert {row.currency: row.gross_sales_cents for row in dashboard.totals_by_currency} == {"EUR": 25000, "XAF": 300000}



def test_student_code_counter_continues_after_existing_profiles() -> None:
    db = build_db()
    org, _user, _formation, session = seed(db)
    site, *_ = get_or_create_identity_records(db, org)

    legacy_user = UserRecord(
        email="legacy@student.test",
        full_name="Legacy Student",
        status="active",
    )
    next_user = UserRecord(
        email="next@student.test",
        full_name="Next Student",
        status="active",
    )
    db.add_all([legacy_user, next_user])
    db.flush()
    code_year = datetime.now(UTC).strftime("%y")
    db.add(
        OrganizationStudentProfileRecord(
            organization_id=org.id,
            user_id=legacy_user.id,
            student_code=f"SB{code_year}-007",
            status="active",
        )
    )
    site.student_code_sequence_year = 0
    site.student_code_sequence = 0
    db.commit()

    checkout = create_checkout(
        db,
        org,
        next_user,
        CheckoutCreate(session_id=session.id, payment_mode="full"),
    )
    confirm_demo_checkout(db, org, next_user, checkout.order_id)

    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == org.id,
            OrganizationStudentProfileRecord.user_id == next_user.id,
        )
    )
    assert profile is not None
    assert profile.student_code == f"SB{code_year}-008"

    db.refresh(site)
    assert site.student_code_sequence_year == int(datetime.now(UTC).strftime("%Y"))
    assert site.student_code_sequence == 8


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



def test_purchase_does_not_reactivate_administratively_suspended_member() -> None:
    db = build_db()
    org, user, _formation, session = seed(db)
    member = OrganizationMemberRecord(
        organization_id=org.id,
        user_id=user.id,
        role="student",
        status="suspended",
    )
    db.add(member)
    db.commit()

    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="full"))
    confirmed = confirm_demo_checkout(db, org, user, checkout.order_id)

    db.refresh(member)
    assert confirmed.status == "paid"
    assert member.status == "suspended"
    assert db.scalar(select(EnrollmentRecord).where(
        EnrollmentRecord.organization_id == org.id,
        EnrollmentRecord.student_id == user.id,
        EnrollmentRecord.session_id == session.id,
    )).status == "active"


def test_paid_installment_generates_branded_pdf_invoice() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    org.logo_url = None
    site, legal, communication, _cert = get_or_create_identity_records(db, org)
    site.site_name = "School Business"
    legal.legal_name = "School Business SARL"
    legal.tax_number = "TAX-001"
    communication.sender_name = "School Business"
    db.commit()

    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="full"),
    )
    confirm_demo_checkout(db, org, user, checkout.order_id)

    invoice = db.scalar(
        select(OrderInvoiceRecord).where(
            OrderInvoiceRecord.order_id == checkout.order_id
        )
    )
    assert invoice is not None
    assert invoice.branding_snapshot["school_name"] == "School Business"
    assert invoice.branding_snapshot["legal_name"] == "School Business SARL"
    filename, pdf = build_invoice_pdf(db, invoice)
    assert filename == f"{invoice.invoice_number}.pdf"
    assert pdf.startswith(b"%PDF")


def test_payment_confirmation_queues_school_branded_communications() -> None:
    db = build_db()
    org, user, formation, session = seed(db)
    user.phone = "+237680950319"
    site, _legal, comm, _cert = get_or_create_identity_records(db, org)
    site.site_name = "School Business"
    comm.sender_name = "School Business"
    comm.email_signature = "L'équipe School Business"
    comm.whatsapp_signature = "School Business"
    db.commit()

    checkout = create_checkout(
        db,
        org,
        user,
        CheckoutCreate(session_id=session.id, payment_mode="full"),
    )
    confirm_demo_checkout(db, org, user, checkout.order_id)

    rows = list(
        db.scalars(
            select(CommunicationOutboxRecord)
            .where(CommunicationOutboxRecord.organization_id == org.id)
            .order_by(CommunicationOutboxRecord.id)
        ).all()
    )
    assert {row.channel for row in rows} == {"email", "whatsapp"}
    email = next(row for row in rows if row.channel == "email")
    whatsapp = next(row for row in rows if row.channel == "whatsapp")
    assert email.subject.startswith("[School Business]")
    assert "L'équipe School Business" in email.body
    assert email.branding_snapshot["school_name"] == "School Business"
    assert whatsapp.body.endswith("School Business")
