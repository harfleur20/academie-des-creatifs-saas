from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    CommunicationOutboxRecord,
    CouponRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrderInstallmentRecord,
    OrderInvoiceRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    PromotionRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.commerce import (
    CheckoutCreate,
    CheckoutRead,
    CommercialDashboardRead,
    CouponCreate,
    CouponRead,
    InstallmentRead,
    InvoiceRead,
    OrderRead,
    PricePreviewRead,
    PromotionCreate,
    PromotionRead,
    StudentManagementRead,
)
from app.services.membership_roles import (
    load_effective_member_roles,
    replace_effective_roles,
)
from app.services.public_catalog import (
    _active_promotion,
    _session_availability,
)
from app.services.school_branding import (
    branding_snapshot,
    get_or_create_identity_records,
)
from app.services.tara_money import create_payment_link, verify_payment


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _require_manager(tenant) -> None:
    if tenant.support_mode:
        return
    if not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès gestion requis.")


def _discount(price: int, discount_type: str, value: int) -> int:
    result = round(price * value / 100) if discount_type == "percentage" else value
    return max(0, min(price, result))


def _load_session_formation(
    db: Session,
    org: OrganizationRecord,
    session_id: int,
) -> tuple[FormationSessionRecord, FormationRecord]:
    session = db.scalar(
        select(FormationSessionRecord).where(
            FormationSessionRecord.id == session_id,
            FormationSessionRecord.organization_id == org.id,
        )
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session introuvable.")
    formation = db.scalar(
        select(FormationRecord).where(
            FormationRecord.id == session.formation_id,
            FormationRecord.organization_id == org.id,
            FormationRecord.status == "published",
        )
    )
    if formation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formation introuvable.")
    return session, formation


def _valid_coupon(
    db: Session,
    org: OrganizationRecord,
    *,
    user_id: int,
    formation_id: int,
    session_id: int,
    price_after_promotion: int,
    promotion_active: bool,
    coupon_code: str | None,
) -> tuple[CouponRecord | None, int]:
    if not coupon_code:
        return None, 0
    code = coupon_code.strip().upper()
    coupon = db.scalar(
        select(CouponRecord).where(
            CouponRecord.organization_id == org.id,
            func.upper(CouponRecord.code) == code,
            CouponRecord.is_active.is_(True),
        )
    )
    if coupon is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Code promo invalide.")

    now = utc_now()
    if coupon.valid_from and now < _aware(coupon.valid_from):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo n'est pas encore actif.")
    if coupon.valid_until and now > _aware(coupon.valid_until):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo a expiré.")
    if coupon.max_uses is not None and coupon.uses_count >= coupon.max_uses:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo a atteint sa limite d'utilisation.")
    if coupon.minimum_order_cents and price_after_promotion < coupon.minimum_order_cents:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le montant minimum requis pour ce code promo n'est pas atteint.")
    if coupon.eligible_formation_ids and formation_id not in set(coupon.eligible_formation_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo ne s'applique pas à cette formation.")
    if coupon.eligible_session_ids and session_id not in set(coupon.eligible_session_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo ne s'applique pas à cette session.")
    if promotion_active and not coupon.allow_on_promotions:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo n'est pas cumulable avec la promotion en cours.")

    used = int(
        db.scalar(
            select(func.count(StudentOrderRecord.id)).where(
                StudentOrderRecord.organization_id == org.id,
                StudentOrderRecord.user_id == user_id,
                StudentOrderRecord.coupon_id == coupon.id,
                StudentOrderRecord.status.in_(["partially_paid", "paid", "late"]),
            )
        )
        or 0
    )
    if used >= coupon.max_uses_per_customer:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Vous avez déjà utilisé ce code promo.")

    return coupon, _discount(price_after_promotion, coupon.discount_type, coupon.discount_value)


def price_preview(
    db: Session,
    org: OrganizationRecord,
    *,
    user_id: int,
    session_id: int,
    coupon_code: str | None = None,
) -> PricePreviewRead:
    session, formation = _load_session_formation(db, org, session_id)
    available, reason, _remaining = _session_availability(db, formation, session)
    if not available:
        raise HTTPException(status.HTTP_409_CONFLICT, reason or "Cette session n'est pas disponible.")

    base = session.price_override_cents if session.price_override_cents is not None else formation.price_cents
    promotion, promotion_discount = _active_promotion(db, org.id, formation.id, session.id, base)
    after_promotion = max(0, base - promotion_discount)
    coupon, coupon_discount = _valid_coupon(
        db,
        org,
        user_id=user_id,
        formation_id=formation.id,
        session_id=session.id,
        price_after_promotion=after_promotion,
        promotion_active=promotion is not None,
        coupon_code=coupon_code,
    )
    final = max(0, after_promotion - coupon_discount)
    return PricePreviewRead(
        base_price_cents=base,
        promotion_discount_cents=promotion_discount,
        coupon_discount_cents=coupon_discount,
        total_discount_cents=promotion_discount + coupon_discount,
        final_price_cents=final,
        currency=formation.currency,
        promotion_label=promotion.name if promotion else None,
        coupon_code=coupon.code if coupon else None,
        installments_allowed=formation.allow_installments and formation.installment_count >= 2 and final > 0,
        installment_count=formation.installment_count if formation.allow_installments else 1,
    )


def _split_installments(
    total: int,
    count: int,
    *,
    session_end,
) -> list[tuple[int, datetime, datetime]]:
    count = max(1, count)
    now = utc_now()
    if count == 1:
        return [(total, now, now + timedelta(days=settings.commerce_grace_period_days))]
    quotient, remainder = divmod(total, count)
    amounts = [quotient + (1 if index < remainder else 0) for index in range(count)]
    end_dt = datetime.combine(session_end, time(hour=23, minute=59), tzinfo=UTC)
    if end_dt <= now:
        end_dt = now + timedelta(days=30 * (count - 1))
    span = max((end_dt - now).total_seconds(), 86400 * (count - 1))
    rows = []
    for index, amount in enumerate(amounts):
        due = now if index == 0 else now + timedelta(seconds=span * index / (count - 1))
        rows.append((amount, due, due + timedelta(days=settings.commerce_grace_period_days)))
    return rows


def _student_code(
    db: Session,
    org: OrganizationRecord,
) -> str:
    site, _legal, _comm, _cert = get_or_create_identity_records(db, org)
    prefix = (site.student_code_prefix or "AC").upper()[:8]
    year = utc_now().strftime("%y")
    base = f"{prefix}{year}-"
    existing = int(
        db.scalar(
            select(func.count(OrganizationStudentProfileRecord.id)).where(
                OrganizationStudentProfileRecord.organization_id == org.id,
                OrganizationStudentProfileRecord.student_code.like(f"{base}%"),
            )
        )
        or 0
    )
    for number in range(existing + 1, existing + 10_000):
        candidate = f"{base}{number:03d}"
        if db.scalar(
            select(OrganizationStudentProfileRecord.id).where(
                OrganizationStudentProfileRecord.organization_id == org.id,
                OrganizationStudentProfileRecord.student_code == candidate,
            )
        ) is None:
            return candidate
    raise HTTPException(status.HTTP_409_CONFLICT, "Impossible de générer un matricule unique.")


def _ensure_student_access(
    db: Session,
    org: OrganizationRecord,
    order: StudentOrderRecord,
) -> OrganizationStudentProfileRecord:
    member = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == org.id,
            OrganizationMemberRecord.user_id == order.user_id,
        )
    )
    if member is None:
        member = OrganizationMemberRecord(
            organization_id=org.id,
            user_id=order.user_id,
            role="student",
            status="active",
        )
        db.add(member)
        db.flush()
        replace_effective_roles(db, member, {"student"})
    else:
        member.status = "active"
        roles = set(load_effective_member_roles(db, member))
        roles.add("student")
        replace_effective_roles(db, member, roles)

    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == org.id,
            OrganizationStudentProfileRecord.user_id == order.user_id,
        )
    )
    if profile is None:
        profile = OrganizationStudentProfileRecord(
            organization_id=org.id,
            user_id=order.user_id,
            student_code=_student_code(db, org),
            status="active",
            first_purchase_at=utc_now(),
        )
        db.add(profile)
        db.flush()
    else:
        profile.status = "active"

    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == org.id,
            EnrollmentRecord.session_id == order.session_id,
            EnrollmentRecord.student_id == order.user_id,
        )
    )
    if enrollment is None:
        enrollment = EnrollmentRecord(
            organization_id=org.id,
            session_id=order.session_id,
            student_id=order.user_id,
            status="active",
        )
        db.add(enrollment)
    elif enrollment.status != "completed":
        enrollment.status = "active"

    return profile


def _queue_message(
    db: Session,
    *,
    org: OrganizationRecord,
    user: UserRecord,
    event_key: str,
    subject: str,
    body: str,
) -> None:
    snapshot = branding_snapshot(db, org)
    db.add(
        CommunicationOutboxRecord(
            organization_id=org.id,
            user_id=user.id,
            channel="email",
            recipient=user.email,
            event_key=event_key,
            subject=f"[{snapshot['school_name']}] {subject}",
            body=f"{body}\n\n{snapshot.get('email_signature') or snapshot['school_name']}",
            branding_snapshot=snapshot,
            status="pending",
        )
    )
    if user.phone:
        db.add(
            CommunicationOutboxRecord(
                organization_id=org.id,
                user_id=user.id,
                channel="whatsapp",
                recipient=user.phone,
                event_key=event_key,
                subject=None,
                body=f"{body}\n\n{snapshot.get('whatsapp_signature') or snapshot['school_name']}",
                branding_snapshot=snapshot,
                status="pending",
            )
        )


def _invoice_number(org: OrganizationRecord, order: StudentOrderRecord, sequence: int) -> str:
    return f"{org.slug[:8].upper()}-INV-{utc_now():%Y}-{order.id:06d}-{sequence:02d}"


def _create_invoice(
    db: Session,
    org: OrganizationRecord,
    order: StudentOrderRecord,
    installment: OrderInstallmentRecord,
) -> OrderInvoiceRecord:
    existing = db.scalar(
        select(OrderInvoiceRecord).where(
            OrderInvoiceRecord.organization_id == org.id,
            OrderInvoiceRecord.installment_id == installment.id,
        )
    )
    if existing:
        return existing
    invoice = OrderInvoiceRecord(
        organization_id=org.id,
        order_id=order.id,
        installment_id=installment.id,
        invoice_number=_invoice_number(org, order, installment.sequence),
        status="paid",
        amount_cents=installment.amount_cents,
        currency=order.currency,
        branding_snapshot=order.branding_snapshot,
        issued_at=utc_now(),
        paid_at=installment.paid_at or utc_now(),
    )
    db.add(invoice)
    return invoice


def _refresh_order_access_after_payment(
    db: Session,
    org: OrganizationRecord,
    order: StudentOrderRecord,
) -> None:
    overdue = list(
        db.scalars(
            select(OrderInstallmentRecord).where(
                OrderInstallmentRecord.organization_id == org.id,
                OrderInstallmentRecord.order_id == order.id,
                OrderInstallmentRecord.status.in_(["late", "failed"]),
            )
        ).all()
    )
    if overdue:
        return
    order.access_status = "active"
    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == org.id,
            EnrollmentRecord.session_id == order.session_id,
            EnrollmentRecord.student_id == order.user_id,
        )
    )
    if enrollment and enrollment.status == "suspended_payment":
        enrollment.status = "active"
    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == org.id,
            OrganizationStudentProfileRecord.user_id == order.user_id,
        )
    )
    if profile and profile.status == "suspended_payment":
        profile.status = "active"


def _apply_installment_payment(
    db: Session,
    org: OrganizationRecord,
    order: StudentOrderRecord,
    installment: OrderInstallmentRecord,
    *,
    paid_at: datetime | None = None,
) -> StudentOrderRecord:
    if installment.status == "paid":
        return order
    was_unpaid = order.paid_cents == 0
    paid_time = _aware(paid_at) or utc_now()
    installment.status = "paid"
    installment.paid_at = paid_time
    db.flush()

    order.paid_cents = int(
        db.scalar(
            select(func.coalesce(func.sum(OrderInstallmentRecord.amount_cents), 0)).where(
                OrderInstallmentRecord.order_id == order.id,
                OrderInstallmentRecord.status == "paid",
            )
        )
        or 0
    )
    if order.paid_cents >= order.final_price_cents:
        order.status = "paid"
        order.paid_at = paid_time
    else:
        order.status = "partially_paid"

    profile = _ensure_student_access(db, org, order)
    _refresh_order_access_after_payment(db, org, order)
    _create_invoice(db, org, order, installment)

    if was_unpaid:
        if order.promotion_id:
            promo = db.get(PromotionRecord, order.promotion_id)
            if promo:
                promo.uses_count += 1
        if order.coupon_id:
            coupon = db.get(CouponRecord, order.coupon_id)
            if coupon:
                coupon.uses_count += 1

    user = db.get(UserRecord, order.user_id)
    formation = db.get(FormationRecord, order.formation_id)
    session = db.get(FormationSessionRecord, order.session_id)
    if user and formation and session:
        _queue_message(
            db,
            org=org,
            user=user,
            event_key="student.payment.confirmed",
            subject="Paiement confirmé",
            body=(
                f"Bonjour {user.full_name},\n"
                f"votre paiement pour {formation.title} — {session.label} est confirmé.\n"
                f"Votre matricule est {profile.student_code}."
            ),
        )
    db.commit()
    db.refresh(order)
    return order


def _provider_link(
    db: Session,
    org: OrganizationRecord,
    order: StudentOrderRecord,
    installment: OrderInstallmentRecord,
) -> str | None:
    if installment.amount_cents <= 0:
        _apply_installment_payment(db, org, order, installment)
        return None

    if settings.demo_payments_enabled:
        reference = f"SCH-DEMO-{org.id}-{order.id}-{installment.sequence}-{uuid4().hex[:10]}"
        installment.provider_reference = reference
        order.provider_reference = order.provider_reference or reference
        url = (
            f"{settings.frontend_url}/school/{org.slug}/checkout"
            f"?order={order.id}&demo=1"
        )
        installment.checkout_url = url
        order.checkout_url = url
        order.payment_provider = "demo"
        db.commit()
        return url

    if not settings.tara_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Le paiement en ligne n'est pas configuré.",
        )
    if order.currency.upper() != "XAF":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "TaraMoney exige une tarification en XAF.",
        )
    reference = f"SCH-{org.id}-O{order.id}-E{installment.sequence}-{uuid4().hex[:12]}"
    payment = create_payment_link(
        product_id=reference,
        product_name=f"{order.formation.title} - {order.session.label}",
        amount_xaf=installment.amount_cents,
        description=f"Échéance {installment.sequence}/{order.installment_count} - {org.name}",
        return_url=(
            f"{settings.frontend_url}/school/{org.slug}/checkout"
            f"?order={order.id}&payment=return"
        ),
        webhook_url=(
            f"{settings.backend_public_url}{settings.api_prefix}"
            "/commerce/tara/webhook"
        ),
    )
    installment.provider_reference = reference
    installment.checkout_url = payment.checkout_url
    order.provider_reference = order.provider_reference or reference
    order.checkout_url = payment.checkout_url
    order.payment_provider = "taramoney"
    db.commit()
    return payment.checkout_url


def _checkout_read(order: StudentOrderRecord) -> CheckoutRead:
    return CheckoutRead(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        access_status=order.access_status,
        formation_id=order.formation_id,
        formation_title=order.formation.title,
        session_id=order.session_id,
        session_label=order.session.label,
        base_price_cents=order.base_price_cents,
        discount_amount_cents=order.discount_amount_cents,
        final_price_cents=order.final_price_cents,
        paid_cents=order.paid_cents,
        currency=order.currency,
        payment_mode=order.payment_mode,
        installment_count=order.installment_count,
        checkout_url=order.checkout_url,
        provider_reference=order.provider_reference,
    )


def create_checkout(
    db: Session,
    org: OrganizationRecord,
    user: UserRecord,
    payload: CheckoutCreate,
) -> CheckoutRead:
    session, formation = _load_session_formation(db, org, payload.session_id)
    preview = price_preview(
        db,
        org,
        user_id=user.id,
        session_id=session.id,
        coupon_code=payload.coupon_code,
    )
    if payload.payment_mode == "installments" and not preview.installments_allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le paiement en plusieurs tranches n'est pas disponible pour cette formation.")

    existing_enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == org.id,
            EnrollmentRecord.session_id == session.id,
            EnrollmentRecord.student_id == user.id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )
    )
    if existing_enrollment:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous êtes déjà inscrit à cette session.")

    promotion, _promo_discount = _active_promotion(
        db, org.id, formation.id, session.id, preview.base_price_cents
    )
    coupon = None
    if preview.coupon_code:
        coupon = db.scalar(
            select(CouponRecord).where(
                CouponRecord.organization_id == org.id,
                func.upper(CouponRecord.code) == preview.coupon_code.upper(),
            )
        )

    count = (
        formation.installment_count
        if payload.payment_mode == "installments"
        else 1
    )
    order = StudentOrderRecord(
        organization_id=org.id,
        order_number=f"{org.slug[:8].upper()}-{utc_now():%Y%m%d}-{uuid4().hex[:8].upper()}",
        user_id=user.id,
        formation_id=formation.id,
        session_id=session.id,
        status="pending",
        access_status="pending",
        base_price_cents=preview.base_price_cents,
        discount_amount_cents=preview.total_discount_cents,
        final_price_cents=preview.final_price_cents,
        paid_cents=0,
        currency=preview.currency,
        discount_source=(
            "coupon+promotion"
            if preview.coupon_discount_cents and preview.promotion_discount_cents
            else "coupon"
            if preview.coupon_discount_cents
            else "promotion"
            if preview.promotion_discount_cents
            else None
        ),
        promotion_id=promotion.id if promotion else None,
        coupon_id=coupon.id if coupon else None,
        coupon_code=preview.coupon_code,
        payment_mode=payload.payment_mode,
        installment_count=count,
        payment_provider="demo" if settings.demo_payments_enabled else "taramoney",
        branding_snapshot=branding_snapshot(db, org),
    )
    db.add(order)
    db.flush()

    installment_rows = []
    for sequence, (amount, due, grace) in enumerate(
        _split_installments(preview.final_price_cents, count, session_end=session.end_date),
        start=1,
    ):
        row = OrderInstallmentRecord(
            organization_id=org.id,
            order_id=order.id,
            sequence=sequence,
            amount_cents=amount,
            due_at=due,
            grace_until=grace,
            status="pending",
        )
        db.add(row)
        installment_rows.append(row)
    db.commit()
    order = db.scalar(
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(StudentOrderRecord.id == order.id)
    )
    first = db.scalar(
        select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.order_id == order.id,
            OrderInstallmentRecord.sequence == 1,
        )
    )
    if preview.final_price_cents == 0:
        _apply_installment_payment(db, org, order, first)
    else:
        _provider_link(db, org, order, first)
    db.refresh(order)
    return _checkout_read(order)


def confirm_demo_checkout(
    db: Session,
    org: OrganizationRecord,
    user: UserRecord,
    order_id: int,
) -> CheckoutRead:
    if not settings.demo_payments_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le paiement démo est désactivé.")
    order = db.scalar(
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(
            StudentOrderRecord.id == order_id,
            StudentOrderRecord.organization_id == org.id,
            StudentOrderRecord.user_id == user.id,
        )
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable.")
    installment = db.scalar(
        select(OrderInstallmentRecord)
        .where(
            OrderInstallmentRecord.order_id == order.id,
            OrderInstallmentRecord.status != "paid",
        )
        .order_by(OrderInstallmentRecord.sequence)
    )
    if installment is None:
        return _checkout_read(order)
    _apply_installment_payment(db, org, order, installment)
    db.refresh(order)
    return _checkout_read(order)


def reconcile_tara_reference(
    db: Session,
    provider_reference: str,
) -> StudentOrderRecord:
    installment = db.scalar(
        select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.provider_reference == provider_reference
        )
    )
    if installment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Échéance de paiement introuvable.")
    order = db.scalar(
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(StudentOrderRecord.id == installment.order_id)
        .with_for_update()
    )
    org = db.get(OrganizationRecord, order.organization_id)
    verification = verify_payment(provider_reference)
    if verification.status == "pending":
        db.rollback()
        return order
    if verification.status == "failed":
        installment.status = "failed"
        db.commit()
        return order
    if verification.product_id != provider_reference:
        raise HTTPException(status.HTTP_409_CONFLICT, "Référence TaraMoney incohérente.")
    if verification.amount is None or verification.amount != installment.amount_cents:
        raise HTTPException(status.HTTP_409_CONFLICT, "Montant TaraMoney incohérent.")
    _apply_installment_payment(
        db,
        org,
        order,
        installment,
        paid_at=verification.paid_at,
    )
    return order


def create_installment_payment_link(
    db: Session,
    org: OrganizationRecord,
    user: UserRecord,
    installment_id: int,
) -> str | None:
    installment = db.scalar(
        select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.id == installment_id,
            OrderInstallmentRecord.organization_id == org.id,
        )
    )
    if installment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Échéance introuvable.")
    order = db.scalar(
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(
            StudentOrderRecord.id == installment.order_id,
            StudentOrderRecord.user_id == user.id,
        )
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable.")
    if installment.status == "paid":
        return installment.checkout_url
    return _provider_link(db, org, order, installment)


def process_installment_lifecycle(
    db: Session,
    *,
    organization_id: int | None = None,
) -> int:
    now = utc_now()
    query = select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.status.in_(["pending", "due", "failed"]),
        OrderInstallmentRecord.due_at <= now,
    )
    if organization_id is not None:
        query = query.where(OrderInstallmentRecord.organization_id == organization_id)
    rows = list(db.scalars(query).all())
    changed = 0
    for row in rows:
        order = db.get(StudentOrderRecord, row.order_id)
        org = db.get(OrganizationRecord, row.organization_id)
        if not order or not org:
            continue
        if now <= _aware(row.grace_until):
            if row.status == "pending":
                row.status = "due"
                changed += 1
            continue
        if row.status != "late":
            row.status = "late"
            order.status = "late"
            order.access_status = "suspended_payment"
            enrollment = db.scalar(
                select(EnrollmentRecord).where(
                    EnrollmentRecord.organization_id == org.id,
                    EnrollmentRecord.session_id == order.session_id,
                    EnrollmentRecord.student_id == order.user_id,
                )
            )
            if enrollment and enrollment.status != "completed":
                enrollment.status = "suspended_payment"
            profile = db.scalar(
                select(OrganizationStudentProfileRecord).where(
                    OrganizationStudentProfileRecord.organization_id == org.id,
                    OrganizationStudentProfileRecord.user_id == order.user_id,
                )
            )
            if profile:
                profile.status = "suspended_payment"
            user = db.get(UserRecord, order.user_id)
            if user:
                _queue_message(
                    db,
                    org=org,
                    user=user,
                    event_key="student.payment.overdue",
                    subject="Échéance impayée",
                    body="Une échéance de votre formation est en retard. Votre accès pédagogique est suspendu jusqu'à régularisation.",
                )
            changed += 1
    db.commit()
    return changed


def create_promotion(db: Session, tenant, payload: PromotionCreate) -> PromotionRead:
    _require_manager(tenant)
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    if payload.formation_id:
        formation = db.scalar(select(FormationRecord).where(FormationRecord.id == payload.formation_id, FormationRecord.organization_id == tenant.organization_id))
        if formation is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Formation invalide.")
    if payload.session_id:
        session = db.scalar(select(FormationSessionRecord).where(FormationSessionRecord.id == payload.session_id, FormationSessionRecord.organization_id == tenant.organization_id))
        if session is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Session invalide.")
    row = PromotionRecord(organization_id=tenant.organization_id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return PromotionRead(**payload.model_dump(), id=row.id, uses_count=row.uses_count, created_at=row.created_at)


def list_promotions(db: Session, tenant) -> list[PromotionRead]:
    _require_manager(tenant)
    rows = db.scalars(select(PromotionRecord).where(PromotionRecord.organization_id == tenant.organization_id).order_by(PromotionRecord.created_at.desc())).all()
    return [PromotionRead(
        id=row.id,name=row.name,formation_id=row.formation_id,session_id=row.session_id,
        discount_type=row.discount_type,discount_value=row.discount_value,starts_at=row.starts_at,ends_at=row.ends_at,
        max_uses=row.max_uses,uses_count=row.uses_count,is_active=row.is_active,created_at=row.created_at,
    ) for row in rows]


def create_coupon(db: Session, tenant, payload: CouponCreate) -> CouponRead:
    _require_manager(tenant)
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    code = payload.code.strip().upper()
    if db.scalar(select(CouponRecord.id).where(CouponRecord.organization_id == tenant.organization_id, func.upper(CouponRecord.code) == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce code promo existe déjà.")
    values=payload.model_dump(); values["code"]=code
    row=CouponRecord(organization_id=tenant.organization_id,**values)
    db.add(row);db.commit();db.refresh(row)
    return CouponRead(**values,id=row.id,uses_count=row.uses_count,created_at=row.created_at)


def list_coupons(db: Session, tenant) -> list[CouponRead]:
    _require_manager(tenant)
    rows=db.scalars(select(CouponRecord).where(CouponRecord.organization_id==tenant.organization_id).order_by(CouponRecord.created_at.desc())).all()
    return [CouponRead(
        id=row.id,code=row.code,name=row.name,discount_type=row.discount_type,discount_value=row.discount_value,
        valid_from=row.valid_from,valid_until=row.valid_until,max_uses=row.max_uses,max_uses_per_customer=row.max_uses_per_customer,
        uses_count=row.uses_count,minimum_order_cents=row.minimum_order_cents,eligible_formation_ids=row.eligible_formation_ids or [],
        eligible_session_ids=row.eligible_session_ids or [],allow_on_promotions=row.allow_on_promotions,is_active=row.is_active,created_at=row.created_at,
    ) for row in rows]


def _order_read(db: Session, order: StudentOrderRecord) -> OrderRead:
    user=db.get(UserRecord,order.user_id)
    profile=db.scalar(select(OrganizationStudentProfileRecord).where(OrganizationStudentProfileRecord.organization_id==order.organization_id,OrganizationStudentProfileRecord.user_id==order.user_id))
    installments=db.scalars(select(OrderInstallmentRecord).where(OrderInstallmentRecord.order_id==order.id).order_by(OrderInstallmentRecord.sequence)).all()
    base=_checkout_read(order)
    return OrderRead(
        **base.model_dump(),
        student_name=user.full_name if user else "—",
        student_email=user.email if user else "—",
        student_code=profile.student_code if profile else None,
        coupon_code=order.coupon_code,
        created_at=order.created_at,
        paid_at=order.paid_at,
        installments=[InstallmentRead(
            id=row.id,order_id=row.order_id,sequence=row.sequence,amount_cents=row.amount_cents,due_at=row.due_at,
            grace_until=row.grace_until,status=row.status,checkout_url=row.checkout_url,paid_at=row.paid_at,
        ) for row in installments],
    )


def list_orders(db: Session, tenant) -> list[OrderRead]:
    _require_manager(tenant)
    rows=db.scalars(
        select(StudentOrderRecord)
        .options(selectinload(StudentOrderRecord.formation),selectinload(StudentOrderRecord.session))
        .where(StudentOrderRecord.organization_id==tenant.organization_id)
        .order_by(StudentOrderRecord.created_at.desc())
    ).all()
    return [_order_read(db,row) for row in rows]


def list_invoices(db: Session, tenant) -> list[InvoiceRead]:
    _require_manager(tenant)
    rows=db.scalars(select(OrderInvoiceRecord).where(OrderInvoiceRecord.organization_id==tenant.organization_id).order_by(OrderInvoiceRecord.issued_at.desc())).all()
    return [InvoiceRead(
        id=row.id,order_id=row.order_id,installment_id=row.installment_id,invoice_number=row.invoice_number,status=row.status,
        amount_cents=row.amount_cents,currency=row.currency,branding_snapshot=row.branding_snapshot or {},issued_at=row.issued_at,paid_at=row.paid_at,
    ) for row in rows]


def list_students(db: Session, tenant) -> list[StudentManagementRead]:
    _require_manager(tenant)
    profiles=db.scalars(
        select(OrganizationStudentProfileRecord)
        .options(selectinload(OrganizationStudentProfileRecord.user))
        .where(OrganizationStudentProfileRecord.organization_id==tenant.organization_id)
        .order_by(OrganizationStudentProfileRecord.created_at.desc())
    ).all()
    result=[]
    for profile in profiles:
        active=int(db.scalar(select(func.count(EnrollmentRecord.id)).where(EnrollmentRecord.organization_id==tenant.organization_id,EnrollmentRecord.student_id==profile.user_id,EnrollmentRecord.status=="active")) or 0)
        completed=int(db.scalar(select(func.count(EnrollmentRecord.id)).where(EnrollmentRecord.organization_id==tenant.organization_id,EnrollmentRecord.student_id==profile.user_id,EnrollmentRecord.status=="completed")) or 0)
        orders=db.scalars(select(StudentOrderRecord).where(StudentOrderRecord.organization_id==tenant.organization_id,StudentOrderRecord.user_id==profile.user_id)).all()
        paid=sum(row.paid_cents for row in orders)
        outstanding=sum(max(0,row.final_price_cents-row.paid_cents) for row in orders if row.status not in {"cancelled","refunded"})
        last=max((row.created_at for row in orders),default=profile.first_purchase_at)
        result.append(StudentManagementRead(
            user_id=profile.user_id,full_name=profile.user.full_name,email=profile.user.email,phone=profile.user.phone,avatar_url=profile.user.avatar_url,
            student_code=profile.student_code,status=profile.status,active_enrollments=active,completed_enrollments=completed,
            total_paid_cents=paid,outstanding_cents=outstanding,last_purchase_at=last,
        ))
    return result


def commercial_dashboard(db: Session, tenant) -> CommercialDashboardRead:
    _require_manager(tenant)
    orders=list(db.scalars(select(StudentOrderRecord).where(StudentOrderRecord.organization_id==tenant.organization_id)).all())
    late=int(db.scalar(select(func.count(OrderInstallmentRecord.id)).where(OrderInstallmentRecord.organization_id==tenant.organization_id,OrderInstallmentRecord.status=="late")) or 0)
    students=int(db.scalar(select(func.count(OrganizationStudentProfileRecord.id)).where(OrganizationStudentProfileRecord.organization_id==tenant.organization_id,OrganizationStudentProfileRecord.status=="active")) or 0)
    currency=orders[0].currency if orders else "XAF"
    return CommercialDashboardRead(
        order_count=len(orders),paid_order_count=sum(1 for row in orders if row.status=="paid"),
        gross_sales_cents=sum(row.final_price_cents for row in orders if row.status not in {"cancelled","refunded"}),
        collected_cents=sum(row.paid_cents for row in orders),
        outstanding_cents=sum(max(0,row.final_price_cents-row.paid_cents) for row in orders if row.status not in {"cancelled","refunded"}),
        late_installments=late,active_students=students,currency=currency,
    )



def get_order_for_user(
    db: Session,
    org: OrganizationRecord,
    user: UserRecord,
    order_id: int,
) -> OrderRead:
    order = db.scalar(
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(
            StudentOrderRecord.id == order_id,
            StudentOrderRecord.organization_id == org.id,
            StudentOrderRecord.user_id == user.id,
        )
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable.")
    return _order_read(db, order)


def reconcile_tara_for_user(
    db: Session,
    org: OrganizationRecord,
    user: UserRecord,
    provider_reference: str,
) -> CheckoutRead:
    installment = db.scalar(
        select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.provider_reference == provider_reference,
            OrderInstallmentRecord.organization_id == org.id,
        )
    )
    if installment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paiement introuvable.")
    order = db.scalar(
        select(StudentOrderRecord).where(
            StudentOrderRecord.id == installment.order_id,
            StudentOrderRecord.user_id == user.id,
        )
    )
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable.")
    reconciled = reconcile_tara_reference(db, provider_reference)
    reconciled = db.scalar(
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(StudentOrderRecord.id == reconciled.id)
    )
    return _checkout_read(reconciled)


def set_promotion_active(db: Session, tenant, promotion_id: int, active: bool) -> PromotionRead:
    _require_manager(tenant)
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    row = db.scalar(select(PromotionRecord).where(PromotionRecord.id == promotion_id, PromotionRecord.organization_id == tenant.organization_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promotion introuvable.")
    row.is_active = active
    db.commit(); db.refresh(row)
    return PromotionRead(
        id=row.id,name=row.name,formation_id=row.formation_id,session_id=row.session_id,
        discount_type=row.discount_type,discount_value=row.discount_value,starts_at=row.starts_at,ends_at=row.ends_at,
        max_uses=row.max_uses,uses_count=row.uses_count,is_active=row.is_active,created_at=row.created_at,
    )


def set_coupon_active(db: Session, tenant, coupon_id: int, active: bool) -> CouponRead:
    _require_manager(tenant)
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    row = db.scalar(select(CouponRecord).where(CouponRecord.id == coupon_id, CouponRecord.organization_id == tenant.organization_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Code promo introuvable.")
    row.is_active = active
    db.commit(); db.refresh(row)
    return CouponRead(
        id=row.id,code=row.code,name=row.name,discount_type=row.discount_type,discount_value=row.discount_value,
        valid_from=row.valid_from,valid_until=row.valid_until,max_uses=row.max_uses,max_uses_per_customer=row.max_uses_per_customer,
        uses_count=row.uses_count,minimum_order_cents=row.minimum_order_cents,eligible_formation_ids=row.eligible_formation_ids or [],
        eligible_session_ids=row.eligible_session_ids or [],allow_on_promotions=row.allow_on_promotions,is_active=row.is_active,created_at=row.created_at,
    )
