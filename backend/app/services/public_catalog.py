from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    PromotionRecord,
    StudentOrderRecord,
    SessionTeacherRecord,
)
from app.schemas.commerce import (
    PaymentScheduleLine,
    PublicFormationCardRead,
    PublicFormationDetailRead,
    PublicHomeRead,
    PublicSchoolRead,
    PublicSessionRead,
)
from app.services.school_branding import (
    DEFAULT_ACCENT,
    DEFAULT_PRIMARY,
    DEFAULT_SECONDARY,
    get_or_create_identity_records,
)
from app.services.publication import formation_content_issues, site_publication_issues
from app.services.session_lifecycle import enrollment_closes_at
from app.services.session_payment_plans import (
    reservation_balance_due_date,
    reservation_deposit_amount,
    reservation_deposit_available,
)


def get_public_organization(
    db: Session,
    school_key: str,
) -> OrganizationRecord:
    key = school_key.strip().lower()
    org = db.scalar(
        select(OrganizationRecord).where(
            or_(
                func.lower(OrganizationRecord.slug) == key,
                func.lower(OrganizationRecord.subdomain) == key,
            ),
            OrganizationRecord.is_active.is_(True),
            OrganizationRecord.status == "active",
        )
    )
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "École introuvable.")
    return org


def public_school_read(
    db: Session,
    org: OrganizationRecord,
) -> PublicSchoolRead:
    site, legal, _comm, _cert = get_or_create_identity_records(db, org)
    if not site.is_published or site_publication_issues(site, legal, org):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Le site public de cette école n'est pas publié.")
    return PublicSchoolRead(
        organization_id=org.id,
        slug=org.slug,
        subdomain=org.subdomain,
        default_currency=legal.default_currency,
        name=org.name,
        site_name=site.site_name or org.name,
        tagline=site.tagline,
        seo_description=site.seo_description,
        logo_url=org.logo_url,
        favicon_url=site.favicon_url,
        primary_color=org.primary_color or DEFAULT_PRIMARY,
        secondary_color=org.secondary_color or DEFAULT_SECONDARY,
        accent_color=org.accent_color or DEFAULT_ACCENT,
        font_heading=site.font_heading,
        font_body=site.font_body,
        font_size_scale=site.font_size_scale,
        heading_size_scale=site.heading_size_scale,
        subtitle_size_scale=site.subtitle_size_scale,
        hero_title=site.hero_title,
        hero_subtitle=site.hero_subtitle,
        hero_cta_label=site.hero_cta_label,
        hero_image_url=site.hero_image_url,
        auth_background_image_url=site.auth_background_image_url,
        auth_show_school_name=site.auth_show_school_name,
        announcement_enabled=site.announcement_enabled,
        announcement_text=site.announcement_text,
        announcement_background_color=site.announcement_background_color,
        announcement_text_color=site.announcement_text_color,
        about_title=site.about_title,
        about_text=site.about_text,
        contact_phone=site.contact_phone,
        contact_email=site.contact_email or org.contact_email,
        contact_address=site.contact_address,
        social_links=site.social_links or {},
        footer_text=site.footer_text,
        legal_notice=site.legal_notice,
        sales_terms=site.sales_terms,
        privacy_policy=site.privacy_policy,
        refund_policy=site.refund_policy,
        white_label=school_white_label(db, org.id),
        is_demo=_is_demo(org),
        platform_url=settings.frontend_url,
    )


def _is_demo(org: OrganizationRecord) -> bool:
    from app.services.demo import is_demo_organization

    return is_demo_organization(org)


def school_white_label(db: Session, organization_id: int) -> bool:
    """Business plans show the school's brand alone, without the platform's signature."""
    from app.services.plan_limits import included
    from app.services.subscriptions import get_effective_plan

    return included(get_effective_plan(db, organization_id), "white_label")


def _active_promotion(
    db: Session,
    org_id: int,
    formation_id: int,
    session_id: int | None,
    price_cents: int,
) -> tuple[PromotionRecord | None, int]:
    now = datetime.now(UTC)
    conditions = [
        PromotionRecord.organization_id == org_id,
        PromotionRecord.is_active.is_(True),
        or_(PromotionRecord.starts_at.is_(None), PromotionRecord.starts_at <= now),
        or_(PromotionRecord.ends_at.is_(None), PromotionRecord.ends_at >= now),
        or_(PromotionRecord.max_uses.is_(None), PromotionRecord.uses_count < PromotionRecord.max_uses),
    ]
    if session_id is not None:
        conditions.append(
            or_(
                PromotionRecord.session_id == session_id,
                (
                    PromotionRecord.session_id.is_(None)
                    & (PromotionRecord.formation_id == formation_id)
                ),
            )
        )
    else:
        conditions.append(
            PromotionRecord.session_id.is_(None)
            & (PromotionRecord.formation_id == formation_id)
        )
    rows = list(db.scalars(select(PromotionRecord).where(*conditions)).all())
    best = None
    best_discount = 0
    for row in rows:
        if row.max_uses is not None:
            reserved = int(db.scalar(select(func.count(StudentOrderRecord.id)).where(
                StudentOrderRecord.organization_id == org_id,
                StudentOrderRecord.promotion_id == row.id,
                StudentOrderRecord.status == "pending",
                StudentOrderRecord.created_at > datetime.now(UTC) - timedelta(minutes=settings.commerce_reservation_minutes),
            )) or 0)
            if row.uses_count + reserved >= row.max_uses:
                continue
        discount = (
            round(price_cents * row.discount_value / 100)
            if row.discount_type == "percentage"
            else row.discount_value
        )
        discount = max(0, min(price_cents, discount))
        if discount > best_discount or (
            discount == best_discount
            and best is not None
            and row.session_id is not None
            and best.session_id is None
        ):
            best = row
            best_discount = discount
    return best, best_discount


def _session_availability(
    db: Session,
    formation: FormationRecord,
    session: FormationSessionRecord,
) -> tuple[bool, str | None, int | None]:
    now = datetime.now(UTC)
    enrollment_open = session.enrollment_open_at
    enrollment_close = session.enrollment_close_at
    if enrollment_open and enrollment_open.tzinfo is None:
        enrollment_open = enrollment_open.replace(tzinfo=UTC)
    if enrollment_close and enrollment_close.tzinfo is None:
        enrollment_close = enrollment_close.replace(tzinfo=UTC)
    effective_price = session.price_override_cents if session.price_override_cents is not None else formation.price_cents
    if formation.format_type == "ligne":
        if session.status == "cancelled":
            return False, "Cette formation n'est pas disponible à l'inscription.", None
        if effective_price <= 0:
            return False, "Le prix de cette formation n'est pas défini.", None
        return True, None, None
    if session.status != "open":
        return False, "Cette session n'est pas ouverte aux inscriptions.", None
    if effective_price <= 0:
        return False, "Le prix de cette session n'est pas défini.", None
    if enrollment_open and now < enrollment_open:
        return False, "Les inscriptions ne sont pas encore ouvertes.", None
    if enrollment_close and now > enrollment_close:
        return False, "Les inscriptions sont clôturées.", None
    if now > enrollment_closes_at(session):
        # As on the mother site, a session can be joined until five days after its start.
        return False, f"Les inscriptions sont closes depuis le {enrollment_closes_at(session):%d/%m/%Y}.", None
    if session.end_date < now.date():
        return False, "Cette session est terminée.", None

    active_count = int(
        db.scalar(
            select(func.count(EnrollmentRecord.id)).where(
                EnrollmentRecord.organization_id == formation.organization_id,
                EnrollmentRecord.session_id == session.id,
                EnrollmentRecord.status.in_(["active", "completed", "suspended_payment"]),
            )
        )
        or 0
    )
    pending_count = int(db.scalar(select(func.count(StudentOrderRecord.id)).where(
        StudentOrderRecord.organization_id == formation.organization_id,
        StudentOrderRecord.session_id == session.id,
        StudentOrderRecord.status == "pending",
        StudentOrderRecord.created_at > now - timedelta(minutes=settings.commerce_reservation_minutes),
    )) or 0)
    remaining = None
    if session.seat_capacity > 0:
        remaining = max(0, session.seat_capacity - active_count - pending_count)
        if remaining <= 0:
            return False, "Cette session est complète.", 0
    return True, None, remaining


def _session_read(
    db: Session,
    formation: FormationRecord,
    session: FormationSessionRecord,
) -> PublicSessionRead:
    base = (
        session.price_override_cents
        if session.price_override_cents is not None
        else formation.price_cents
    )
    promo, discount = _active_promotion(
        db,
        formation.organization_id,
        formation.id,
        session.id,
        base,
    )
    available, reason, remaining = _session_availability(db, formation, session)
    if formation.status != "published":
        available = False
        reason = "Cette formation n'est pas disponible à l'inscription."
    price = max(0, base - discount)
    plan = _payment_plan(formation, session, price) if available and price > 0 else {}
    return PublicSessionRead(
        id=session.id,
        label=session.label,
        start_date=session.start_date,
        end_date=session.end_date,
        campus_label=session.campus_label,
        seat_capacity=session.seat_capacity,
        seats_remaining=remaining,
        enrollment_open_at=session.enrollment_open_at,
        enrollment_close_at=session.enrollment_close_at,
        price_cents=base,
        currency=formation.currency,
        current_price_cents=max(0, base - discount),
        promotion_label=promo.name if promo else None,
        promotion_discount_cents=discount,
        can_purchase=available,
        unavailable_reason=reason,
        **plan,
    )


def _payment_plan(formation: FormationRecord, session: FormationSessionRecord, price: int) -> dict:
    """The deposit and the instalments of a purchase made today, as the checkout will create them."""
    # Imported here: school_commerce builds on this module.
    from app.services.school_commerce import _installment_due_dates, _installment_rows

    deposit = None
    if reservation_deposit_available(
        format_type=formation.format_type, enabled=formation.reservation_deposit_enabled, total=price,
        currency=formation.currency, session_start=session.start_date, today=datetime.now(UTC).date(),
    ):
        deposit = reservation_deposit_amount(price, formation.reservation_deposit_percent, formation.currency)
    schedule = []
    if len(_installment_due_dates(formation, session, price)) >= 2:
        rows = _installment_rows(formation, session, price, formation.currency, installments=True, deposit=deposit)
        schedule = [PaymentScheduleLine(amount_cents=amount, due_date=due.date()) for amount, due, _grace in rows]
    return {
        "deposit_cents": deposit,
        "deposit_percent": formation.reservation_deposit_percent if deposit is not None else None,
        "balance_cents": price - deposit if deposit is not None else None,
        "balance_due_date": reservation_balance_due_date(session.start_date) if deposit is not None else None,
        "schedule_installments": schedule,
    }


def _session_display_order(session: FormationSessionRecord) -> tuple:
    """As on the mother site, sessions still to start come first, then the ones already running."""
    today = datetime.now(UTC).date()
    return (0 if session.start_date > today else 1, session.start_date, session.id)


def _public_formation_query(org_id: int):
    return (
        select(FormationRecord)
        .options(
            selectinload(FormationRecord.sessions)
            .selectinload(FormationSessionRecord.teachers)
            .selectinload(SessionTeacherRecord.teacher),
            selectinload(FormationRecord.sessions)
            .selectinload(FormationSessionRecord.courses)
            .selectinload(CourseRecord.chapters),
        )
        .where(
            FormationRecord.organization_id == org_id,
            FormationRecord.status == "published",
        )
    )


def _formation_card(
    db: Session,
    formation: FormationRecord,
) -> PublicFormationCardRead:
    sessions = [
        _session_read(db, formation, item)
        for item in sorted(formation.sessions, key=_session_display_order)
        if formation.format_type == "ligne" or item.status not in {"cancelled", "completed"}
    ]
    available = [item for item in sessions if item.can_purchase]
    next_session = available[0] if available else (sessions[0] if sessions else None)
    display_base = next_session.price_cents if next_session else formation.price_cents
    display_current = next_session.current_price_cents if next_session else display_base
    display_discount = next_session.promotion_discount_cents if next_session else 0
    display_label = next_session.promotion_label if next_session else None
    return PublicFormationCardRead(
        id=formation.id,
        slug=formation.slug,
        title=formation.title,
        short_description=formation.short_description or formation.description[:500],
        cover_image_url=formation.cover_image_url,
        category=formation.category,
        level=formation.level,
        format_type=formation.format_type,
        training_hours=formation.training_hours,
        price_cents=display_base,
        currency=formation.currency,
        current_price_cents=display_current,
        promotion_label=display_label,
        promotion_discount_cents=display_discount,
        is_featured=formation.is_featured,
        featured_order=formation.featured_order,
        available_session_count=len(available),
        next_session=next_session,
        can_purchase=bool(available),
    )


def list_public_formations(
    db: Session,
    org: OrganizationRecord,
) -> list[PublicFormationCardRead]:
    rows = list(
        db.scalars(
            _public_formation_query(org.id)
            .order_by(FormationRecord.created_at.desc())
        ).unique().all()
    )
    return [_formation_card(db, row) for row in rows if not formation_content_issues(row)]


def public_home(
    db: Session,
    school_key: str,
) -> PublicHomeRead:
    org = get_public_organization(db, school_key)
    school = public_school_read(db, org)
    formations = list_public_formations(db, org)
    featured = sorted(
        [item for item in formations if item.is_featured],
        key=lambda item: (item.featured_order, item.title),
    )[:6]
    if not featured:
        featured = sorted(
            formations,
            key=lambda item: (
                not item.can_purchase,
                item.next_session.start_date if item.next_session else datetime.max.date(),
            ),
        )[:6]
    return PublicHomeRead(school=school, featured_formations=featured)


def public_formation_detail(
    db: Session,
    school_key: str,
    formation_slug: str,
) -> PublicFormationDetailRead:
    org = get_public_organization(db, school_key)
    public_school_read(db, org)
    formation = db.scalar(
        _public_formation_query(org.id).where(
            FormationRecord.slug == formation_slug.strip().lower()
        )
    )
    if formation is None or formation_content_issues(formation):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formation introuvable.")
    card = _formation_card(db, formation)
    session_reads = [
        _session_read(db, formation, item)
        for item in sorted(formation.sessions, key=_session_display_order)
        if formation.format_type != "ligne" and item.status not in {"cancelled", "completed"}
    ]
    source_session = next(
        (
            item
            for item in formation.sessions
            if card.next_session and item.id == card.next_session.id
        ),
        None,
    )
    modules = []
    if source_session is not None:
        for course in sorted(source_session.courses, key=lambda item: item.id):
            if course.status != "published":
                continue
            modules.append(
                {
                    "title": course.title,
                    "chapters": [
                        chapter.title
                        for chapter in sorted(
                            course.chapters,
                            key=lambda item: (item.order_index, item.id),
                        )
                    ],
                }
            )

    teacher_names: list[str] = []
    teachers: list[dict] = []
    seen: set[int] = set()
    for session in formation.sessions:
        for assignment in session.teachers:
            if assignment.teacher_id not in seen:
                seen.add(assignment.teacher_id)
                teacher_names.append(assignment.teacher.full_name)
                teachers.append({"full_name": assignment.teacher.full_name, "avatar_url": assignment.teacher.avatar_url})
    installment_count = formation.installment_count if formation.allow_installments else 1
    if source_session is not None and card.next_session is not None:
        # The price and the time left of the highlighted session cap the school's count.
        from app.services.school_commerce import _installment_due_dates  # builds on this module

        installment_count = len(_installment_due_dates(formation, source_session, card.next_session.current_price_cents))
    return PublicFormationDetailRead(
        **card.model_dump(),
        description=formation.description,
        presentation_video_url=formation.presentation_video_url,
        objectives=formation.objectives,
        prerequisites=formation.prerequisites,
        public_program=formation.public_program,
        allow_installments=formation.allow_installments and installment_count >= 2,
        installment_count=installment_count,
        reservation_deposit_percent=(
            formation.reservation_deposit_percent
            if formation.format_type == "live" and formation.reservation_deposit_enabled else None
        ),
        modules=modules,
        sessions=session_reads,
        teacher_names=teacher_names,
        teachers=teachers,
    )
