from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.entities import (
    BillingInvoiceRecord,
    BillingPaymentAttemptRecord,
    PlanRecord,
    SubscriptionRecord,
)
from app.services.plan_limits import quote
from app.services.subscriptions import (
    aware_utc,
    configured_plan_price,
    get_latest_subscription,
    period_end,
)
from app.services.tara_money import (
    TaraPaymentVerification,
    create_payment_link,
    verify_payment,
)
from app.services.tenancy import TenantContext


def _utc_now() -> datetime:
    return datetime.now(UTC)


def require_demo_payments_enabled() -> None:
    if not settings.demo_payments_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le mode paiement démo est désactivé.",
        )


def _require_billing_admin(tenant: TenantContext) -> None:
    if tenant.user.platform_role == "super_admin":
        return
    if tenant.organization_role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls le propriétaire ou un administrateur peuvent gérer l'abonnement.",
        )


def _get_plan(
    db: Session,
    *,
    plan_code: str,
) -> PlanRecord:
    plan = db.scalar(
        select(PlanRecord)
        .options(selectinload(PlanRecord.entitlements))
        .where(
            PlanRecord.code == plan_code.strip().lower(),
            PlanRecord.is_active.is_(True),
            PlanRecord.is_public.is_(True),
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forfait introuvable.",
        )
    return plan


def _require_downgrade_confirmation(
    db: Session,
    tenant: TenantContext,
    target_plan: PlanRecord,
    *,
    confirmed: bool,
) -> None:
    """Require an explicit acknowledgement before starting a lower-tier checkout."""
    current = get_latest_subscription(db, tenant.organization_id)
    if current is None or current.status not in {"trialing", "active", "past_due"}:
        return

    current_plan = current.plan
    current_price = current_plan.monthly_price_cents
    target_price = target_plan.monthly_price_cents
    same_currency = current_plan.currency.upper() == target_plan.currency.upper()
    if (
        same_currency
        and current_price is not None
        and target_price is not None
        and target_price < current_price
        and not confirmed
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "plan_downgrade_confirmation_required",
                "message": "Ce forfait est inférieur à votre forfait actuel. Confirmez explicitement cette baisse pour continuer.",
            },
        )


def _demo_price_for_plan(
    plan: PlanRecord,
    billing_interval: str,
) -> int:
    configured = configured_plan_price(plan, billing_interval)
    if configured is not None and configured > 0:
        return configured
    return settings.demo_payment_amount_cents


def _load_attempt(
    db: Session,
    attempt_id: int,
) -> BillingPaymentAttemptRecord | None:
    return db.scalar(
        select(BillingPaymentAttemptRecord)
        .options(
            selectinload(BillingPaymentAttemptRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(BillingPaymentAttemptRecord.id == attempt_id)
    )


def _load_subscription(
    db: Session,
    subscription_id: int,
) -> SubscriptionRecord | None:
    return db.scalar(
        select(SubscriptionRecord)
        .options(
            selectinload(SubscriptionRecord.plan).selectinload(
                PlanRecord.entitlements
            )
        )
        .where(SubscriptionRecord.id == subscription_id)
    )


def _invoice_number(now: datetime, attempt_id: int) -> str:
    return f"INV-{now:%Y%m%d}-{attempt_id:08d}"


def _mark_or_create_paid_invoice(
    db: Session,
    *,
    attempt: BillingPaymentAttemptRecord,
    subscription: SubscriptionRecord,
    paid_at: datetime,
    period_start_value: datetime,
    period_end_value: datetime,
) -> BillingInvoiceRecord:
    existing_for_attempt = db.scalar(
        select(BillingInvoiceRecord).where(
            BillingInvoiceRecord.payment_attempt_id == attempt.id
        )
    )
    if existing_for_attempt is not None:
        return existing_for_attempt

    open_invoice = db.scalar(
        select(BillingInvoiceRecord)
        .where(
            BillingInvoiceRecord.subscription_id == subscription.id,
            BillingInvoiceRecord.status == "open",
            BillingInvoiceRecord.plan_id == attempt.plan_id,
            BillingInvoiceRecord.billing_interval == attempt.billing_interval,
        )
        .order_by(BillingInvoiceRecord.issued_at.desc())
    )

    if open_invoice is not None:
        open_invoice.payment_attempt_id = attempt.id
        open_invoice.status = "paid"
        open_invoice.amount_cents = attempt.amount_cents
        open_invoice.lines = attempt.lines
        open_invoice.currency = attempt.currency
        open_invoice.paid_at = paid_at
        open_invoice.due_at = None
        db.add(open_invoice)
        return open_invoice

    invoice = BillingInvoiceRecord(
        organization_id=attempt.organization_id,
        subscription_id=subscription.id,
        plan_id=attempt.plan_id,
        payment_attempt_id=attempt.id,
        invoice_number=_invoice_number(paid_at, attempt.id),
        status="paid",
        amount_cents=attempt.amount_cents,
        lines=attempt.lines,
        currency=attempt.currency,
        billing_interval=attempt.billing_interval,
        period_start=period_start_value,
        period_end=period_end_value,
        issued_at=paid_at,
        due_at=None,
        paid_at=paid_at,
    )
    db.add(invoice)
    return invoice


def _activate_paid_attempt(
    db: Session,
    attempt: BillingPaymentAttemptRecord,
    *,
    provider: str,
    paid_at: datetime | None = None,
    provider_transaction_id: str | None = None,
) -> tuple[BillingPaymentAttemptRecord, SubscriptionRecord]:
    if attempt.activated_subscription_id is not None:
        existing = _load_subscription(db, attempt.activated_subscription_id)
        if existing is not None:
            return attempt, existing

    now = aware_utc(paid_at) or _utc_now()

    existing_same = db.scalar(
        select(SubscriptionRecord)
        .options(selectinload(SubscriptionRecord.plan))
        .where(
            SubscriptionRecord.organization_id == attempt.organization_id,
            SubscriptionRecord.plan_id == attempt.plan_id,
            SubscriptionRecord.billing_interval == attempt.billing_interval,
            SubscriptionRecord.status.in_(["active", "past_due", "suspended"]),
        )
        .order_by(SubscriptionRecord.created_at.desc())
        .with_for_update()
    )

    if existing_same is not None:
        old_end = aware_utc(existing_same.current_period_end)
        if existing_same.status == "active" and old_end is not None and old_end > now:
            new_period_start = old_end
            new_period_end = period_end(old_end, attempt.billing_interval)
            existing_same.current_period_end = new_period_end
        else:
            new_period_start = now
            new_period_end = period_end(now, attempt.billing_interval)
            existing_same.current_period_start = new_period_start
            existing_same.current_period_end = new_period_end

        existing_same.status = "active"
        existing_same.trial_ends_at = None
        existing_same.grace_period_ends_at = None
        existing_same.suspended_at = None
        existing_same.cancel_at_period_end = False
        existing_same.cancelled_at = None
        existing_same.provider = provider
        existing_same.provider_subscription_id = (
            f"{provider}:{attempt.provider_reference}"
        )
        subscription = existing_same

        other_subscriptions = list(
            db.scalars(
                select(SubscriptionRecord)
                .where(
                    SubscriptionRecord.organization_id == attempt.organization_id,
                    SubscriptionRecord.id != subscription.id,
                    SubscriptionRecord.status.in_(
                        ["trialing", "active", "past_due", "suspended"]
                    ),
                )
                .with_for_update()
            ).all()
        )
        for other in other_subscriptions:
            other.status = "cancelled"
            other.cancelled_at = now
            other.cancel_at_period_end = False
            db.add(other)
    else:
        active_subscriptions = list(
            db.scalars(
                select(SubscriptionRecord)
                .where(
                    SubscriptionRecord.organization_id == attempt.organization_id,
                    SubscriptionRecord.status.in_(
                        ["trialing", "active", "past_due", "suspended"]
                    ),
                )
                .with_for_update()
            ).all()
        )
        for old in active_subscriptions:
            old.status = "cancelled"
            old.cancelled_at = now
            old.cancel_at_period_end = False
            db.add(old)

        new_period_start = now
        new_period_end = period_end(now, attempt.billing_interval)
        subscription = SubscriptionRecord(
            organization_id=attempt.organization_id,
            plan_id=attempt.plan_id,
            status="active",
            billing_interval=attempt.billing_interval,
            started_at=now,
            trial_ends_at=None,
            current_period_start=new_period_start,
            current_period_end=new_period_end,
            grace_period_ends_at=None,
            suspended_at=None,
            cancel_at_period_end=False,
            provider=provider,
            provider_subscription_id=f"{provider}:{attempt.provider_reference}",
        )
        db.add(subscription)
        db.flush()

    attempt.status = "paid"
    attempt.confirmed_at = now
    attempt.provider_transaction_id = provider_transaction_id
    attempt.activated_subscription_id = subscription.id
    attempt.failure_reason = None
    db.add(attempt)

    _mark_or_create_paid_invoice(
        db,
        attempt=attempt,
        subscription=subscription,
        paid_at=now,
        period_start_value=new_period_start,
        period_end_value=new_period_end,
    )

    db.commit()
    payment = _load_attempt(db, attempt.id)
    refreshed = _load_subscription(db, subscription.id)
    return payment, refreshed


def create_demo_payment_attempt(
    db: Session,
    tenant: TenantContext,
    *,
    plan_code: str,
    billing_interval: str,
    confirm_downgrade: bool = False,
) -> BillingPaymentAttemptRecord:
    require_demo_payments_enabled()
    _require_billing_admin(tenant)
    plan = _get_plan(db, plan_code=plan_code)
    _require_downgrade_confirmation(db, tenant, plan, confirmed=confirm_downgrade)
    billed = quote(db, tenant.organization_id, plan, billing_interval)

    attempt = BillingPaymentAttemptRecord(
        organization_id=tenant.organization_id,
        plan_id=plan.id,
        billing_interval=billing_interval,
        provider="demo",
        provider_reference=f"DEMO-{tenant.organization_id}-{uuid4().hex}",
        status="pending",
        amount_cents=billed.total_cents if billed else _demo_price_for_plan(plan, billing_interval),
        lines=billed.line_dicts() if billed else None,
        currency=plan.currency,
    )
    db.add(attempt)
    db.commit()
    return _load_attempt(db, attempt.id)


def confirm_demo_payment_attempt(
    db: Session,
    tenant: TenantContext,
    *,
    payment_attempt_id: int,
) -> tuple[BillingPaymentAttemptRecord, SubscriptionRecord]:
    require_demo_payments_enabled()
    _require_billing_admin(tenant)

    attempt = db.scalar(
        select(BillingPaymentAttemptRecord)
        .where(
            BillingPaymentAttemptRecord.id == payment_attempt_id,
            BillingPaymentAttemptRecord.organization_id == tenant.organization_id,
            BillingPaymentAttemptRecord.provider == "demo",
        )
        .with_for_update()
    )
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paiement démo introuvable.",
        )

    if attempt.status == "paid" and attempt.activated_subscription_id is not None:
        return _activate_paid_attempt(db, attempt, provider="demo")

    if attempt.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce paiement démo ne peut plus être confirmé.",
        )

    return _activate_paid_attempt(db, attempt, provider="demo")


def create_tara_payment_attempt(
    db: Session,
    tenant: TenantContext,
    *,
    plan_code: str,
    billing_interval: str,
    confirm_downgrade: bool = False,
) -> tuple[BillingPaymentAttemptRecord, str]:
    _require_billing_admin(tenant)

    if settings.payment_mode == "demo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le mode démo est actif. Utilisez le paiement démo.",
        )
    if not settings.tara_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TaraMoney n'est pas configuré.",
        )

    plan = _get_plan(db, plan_code=plan_code)
    _require_downgrade_confirmation(db, tenant, plan, confirmed=confirm_downgrade)
    if plan.currency.upper() != "XAF":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="TaraMoney exige un forfait configuré en FCFA.",
        )

    amount = configured_plan_price(plan, billing_interval)
    if amount is None or amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le tarif de ce forfait n'est pas encore configuré.",
        )
    # The plan, then each add-on the school uses beyond the quotas of this plan.
    billed = quote(db, tenant.organization_id, plan, billing_interval)
    amount = billed.total_cents

    reference = f"SAAS-{tenant.organization_id}-{uuid4().hex[:24]}"
    attempt = BillingPaymentAttemptRecord(
        organization_id=tenant.organization_id,
        plan_id=plan.id,
        billing_interval=billing_interval,
        provider="taramoney",
        provider_reference=reference,
        status="pending",
        amount_cents=amount,
        lines=billed.line_dicts(),
        currency="XAF",
    )
    db.add(attempt)
    db.commit()

    return_url = (
        f"{settings.frontend_url}/app/billing"
        f"?tara_order={reference}"
    )
    webhook_url = (
        f"{settings.backend_public_url}"
        f"{settings.api_prefix}/billing/tara/webhook"
    )

    try:
        session = create_payment_link(
            product_id=reference,
            product_name=f"Abonnement {plan.name}",
            amount_xaf=amount,
            description=(
                f"Abonnement {plan.name} - "
                f"{'annuel' if billing_interval == 'annual' else 'mensuel'}"
            ),
            return_url=return_url,
            webhook_url=webhook_url,
        )
    except ValueError as exc:
        attempt.status = "failed"
        attempt.failure_reason = str(exc)[:500]
        db.add(attempt)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    attempt.checkout_url = session.checkout_url
    db.add(attempt)
    db.commit()
    return _load_attempt(db, attempt.id), session.checkout_url


def _validate_tara_verification(
    db: Session,
    attempt: BillingPaymentAttemptRecord,
    verification: TaraPaymentVerification,
    *,
    received_at: datetime,
) -> None:
    if verification.product_id != attempt.provider_reference:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La référence vérifiée par TaraMoney ne correspond pas au paiement attendu.",
        )
    if verification.amount is None or verification.amount != attempt.amount_cents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le montant vérifié par TaraMoney est absent ou différent.",
        )

    paid_at = aware_utc(verification.paid_at)
    created_at = aware_utc(attempt.created_at)
    if paid_at is not None and created_at is not None:
        skew = timedelta(minutes=10)
        if paid_at < created_at - skew or paid_at > received_at + skew:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="L'horodatage du paiement TaraMoney est incohérent.",
            )

    if verification.transaction_id:
        duplicate = db.scalar(
            select(BillingPaymentAttemptRecord).where(
                BillingPaymentAttemptRecord.provider_transaction_id
                == verification.transaction_id,
                BillingPaymentAttemptRecord.id != attempt.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cette transaction TaraMoney a déjà été utilisée.",
            )


def reconcile_tara_attempt(
    db: Session,
    *,
    provider_reference: str,
    organization_id: int | None = None,
) -> tuple[BillingPaymentAttemptRecord, SubscriptionRecord | None, str]:
    query = select(BillingPaymentAttemptRecord).where(
        BillingPaymentAttemptRecord.provider_reference == provider_reference,
        BillingPaymentAttemptRecord.provider == "taramoney",
    )
    if organization_id is not None:
        query = query.where(
            BillingPaymentAttemptRecord.organization_id == organization_id,
        )

    attempt = db.scalar(query.with_for_update())
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paiement TaraMoney introuvable.",
        )

    if attempt.status == "paid" and attempt.activated_subscription_id is not None:
        payment, subscription = _activate_paid_attempt(
            db,
            attempt,
            provider="taramoney",
            provider_transaction_id=attempt.provider_transaction_id,
        )
        return payment, subscription, "paid"

    try:
        verification = verify_payment(attempt.provider_reference)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if verification.status == "pending":
        db.rollback()
        return _load_attempt(db, attempt.id), None, "pending"

    if verification.status == "failed":
        attempt.status = "failed"
        attempt.failure_reason = verification.message or "Paiement refusé ou expiré."
        db.add(attempt)
        db.commit()
        return _load_attempt(db, attempt.id), None, "failed"

    received_at = _utc_now()
    _validate_tara_verification(
        db,
        attempt,
        verification,
        received_at=received_at,
    )

    payment, subscription = _activate_paid_attempt(
        db,
        attempt,
        provider="taramoney",
        paid_at=aware_utc(verification.paid_at) or received_at,
        provider_transaction_id=verification.transaction_id,
    )
    return payment, subscription, "paid"
