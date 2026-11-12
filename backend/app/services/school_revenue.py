"""What each school earns from its sales, and how it gets paid (docs/FORFAITS.md).

Students pay on the platform's TaraMoney account. Each paid instalment is credited to the
school, minus the commission of its plan at that moment (Tara's fees are included in it).
The school asks for a payout of its balance; a super admin transfers it and marks it paid.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    OrderInstallmentRecord,
    OrganizationRecord,
    SchoolLedgerEntryRecord,
    SchoolPayoutRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.services.plan_limits import commission_bps, format_xaf
from app.services.tenancy import TenantContext

MIN_PAYOUT = 10_000  # FCFA
PAYOUT_CURRENCY = "XAF"
PAYOUT_METHODS = {"mobile_money": "Mobile Money", "bank": "Virement bancaire"}
OPEN_PAYOUT = "requested"


@dataclass(frozen=True)
class RevenueSummary:
    currency: str
    gross_cents: int
    commission_cents: int
    earned_cents: int
    paid_out_cents: int
    pending_payout_cents: int
    available_cents: int
    commission_bps: int
    min_payout_cents: int


def record_sale(
    db: Session,
    org: OrganizationRecord,
    order: StudentOrderRecord,
    installment: OrderInstallmentRecord,
    paid_at: datetime,
) -> SchoolLedgerEntryRecord | None:
    """Credit the school with a paid instalment, net of the commission of its current plan. Once."""
    existing = db.scalar(select(SchoolLedgerEntryRecord).where(SchoolLedgerEntryRecord.installment_id == installment.id))
    if existing is not None:
        return existing
    rate = commission_bps(db, org.id)
    gross = installment.amount_cents
    commission = (gross * rate + 5_000) // 10_000  # rounded to the nearest franc
    entry = SchoolLedgerEntryRecord(
        organization_id=org.id, kind="sale", gross_cents=gross, commission_bps=rate, commission_cents=commission,
        amount_cents=gross - commission, currency=order.currency, order_id=order.id, installment_id=installment.id,
        description=f"Commande {order.order_number} · échéance {installment.sequence}/{order.installment_count}",
        occurred_at=paid_at,
    )
    db.add(entry)
    db.flush()
    return entry


def _sum(db: Session, column, *conditions) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(column), 0)).where(*conditions)) or 0)


def revenue_summary(db: Session, organization_id: int) -> RevenueSummary:
    in_currency = (SchoolLedgerEntryRecord.organization_id == organization_id, SchoolLedgerEntryRecord.currency == PAYOUT_CURRENCY)
    payouts = (SchoolPayoutRecord.organization_id == organization_id, SchoolPayoutRecord.currency == PAYOUT_CURRENCY)
    earned = _sum(db, SchoolLedgerEntryRecord.amount_cents, *in_currency)
    paid_out = _sum(db, SchoolPayoutRecord.amount_cents, *payouts, SchoolPayoutRecord.status == "paid")
    pending = _sum(db, SchoolPayoutRecord.amount_cents, *payouts, SchoolPayoutRecord.status == OPEN_PAYOUT)
    return RevenueSummary(
        currency=PAYOUT_CURRENCY,
        gross_cents=_sum(db, SchoolLedgerEntryRecord.gross_cents, *in_currency),
        commission_cents=_sum(db, SchoolLedgerEntryRecord.commission_cents, *in_currency),
        earned_cents=earned,
        paid_out_cents=paid_out,
        pending_payout_cents=pending,
        available_cents=max(0, earned - paid_out - pending),
        commission_bps=commission_bps(db, organization_id),
        min_payout_cents=MIN_PAYOUT,
    )


def list_ledger(db: Session, organization_id: int, *, limit: int = 100) -> list[SchoolLedgerEntryRecord]:
    return list(db.scalars(select(SchoolLedgerEntryRecord).where(
        SchoolLedgerEntryRecord.organization_id == organization_id,
    ).order_by(SchoolLedgerEntryRecord.occurred_at.desc(), SchoolLedgerEntryRecord.id.desc()).limit(limit)).all())


def list_payouts(db: Session, organization_id: int) -> list[SchoolPayoutRecord]:
    return list(db.scalars(select(SchoolPayoutRecord).where(
        SchoolPayoutRecord.organization_id == organization_id,
    ).order_by(SchoolPayoutRecord.requested_at.desc(), SchoolPayoutRecord.id.desc())).all())


def require_finance_admin(tenant: TenantContext) -> None:
    if tenant.user.platform_role == "super_admin" and not tenant.support_mode:
        return
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    if tenant.organization_role not in {"owner", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seuls le propriétaire ou un administrateur gèrent les reversements.")


def request_payout(
    db: Session,
    tenant: TenantContext,
    *,
    amount_cents: int,
    method: str,
    destination: str,
    account_name: str,
) -> SchoolPayoutRecord:
    require_finance_admin(tenant)
    if method not in PAYOUT_METHODS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisissez Mobile Money ou virement bancaire.")
    if not destination.strip() or not account_name.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez le numéro ou le compte, et le nom du titulaire.")
    db.scalar(select(OrganizationRecord).where(OrganizationRecord.id == tenant.organization_id).with_for_update())
    if db.scalar(select(SchoolPayoutRecord.id).where(
        SchoolPayoutRecord.organization_id == tenant.organization_id, SchoolPayoutRecord.status == OPEN_PAYOUT,
    )) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un retrait est déjà en cours de traitement.")
    if amount_cents < MIN_PAYOUT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Le retrait minimum est de {format_xaf(MIN_PAYOUT)}.")
    available = revenue_summary(db, tenant.organization_id).available_cents
    if amount_cents > available:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Votre solde disponible est de {format_xaf(available)}.")
    payout = SchoolPayoutRecord(
        organization_id=tenant.organization_id, amount_cents=amount_cents, currency=PAYOUT_CURRENCY, method=method,
        destination=destination.strip(), account_name=account_name.strip(), status=OPEN_PAYOUT,
        requested_by_user_id=tenant.user.id, requested_at=datetime.now(UTC),
    )
    db.add(payout)
    db.commit()
    db.refresh(payout)
    return payout


def cancel_payout(db: Session, tenant: TenantContext, payout_id: int) -> SchoolPayoutRecord:
    require_finance_admin(tenant)
    payout = db.scalar(select(SchoolPayoutRecord).where(
        SchoolPayoutRecord.id == payout_id, SchoolPayoutRecord.organization_id == tenant.organization_id,
    ).with_for_update())
    if payout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Retrait introuvable.")
    if payout.status != OPEN_PAYOUT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce retrait est déjà traité.")
    payout.status = "cancelled"
    payout.processed_at = datetime.now(UTC)
    db.commit()
    db.refresh(payout)
    return payout


def admin_list_payouts(db: Session, *, status_filter: str | None = None) -> list[tuple[SchoolPayoutRecord, OrganizationRecord]]:
    query = select(SchoolPayoutRecord, OrganizationRecord).join(
        OrganizationRecord, OrganizationRecord.id == SchoolPayoutRecord.organization_id,
    ).order_by(SchoolPayoutRecord.requested_at.desc(), SchoolPayoutRecord.id.desc())
    if status_filter:
        query = query.where(SchoolPayoutRecord.status == status_filter)
    return [(payout, org) for payout, org in db.execute(query).all()]


def process_payout(
    db: Session,
    admin: UserRecord,
    payout_id: int,
    *,
    paid: bool,
    transfer_reference: str | None = None,
    note: str | None = None,
) -> SchoolPayoutRecord:
    """A super admin marks a payout as transferred, or rejects it; the school's managers are told."""
    from app.services.school_notifications import notify_school_managers

    payout = db.scalar(select(SchoolPayoutRecord).where(SchoolPayoutRecord.id == payout_id).with_for_update())
    if payout is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Retrait introuvable.")
    if payout.status != OPEN_PAYOUT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce retrait est déjà traité.")
    if paid and not (transfer_reference or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez la référence du virement.")
    if not paid and not (note or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indiquez la raison du refus.")
    payout.status = "paid" if paid else "rejected"
    payout.processed_by_user_id = admin.id
    payout.processed_at = datetime.now(UTC)
    payout.transfer_reference = (transfer_reference or "").strip() or None
    payout.note = (note or "").strip() or None
    amount = format_xaf(payout.amount_cents)
    notify_school_managers(
        db, organization_id=payout.organization_id, event_key=f"payout.{payout.status}:{payout.id}",
        title="Retrait versé" if paid else "Retrait refusé",
        message=(f"{amount} ont été versés ({PAYOUT_METHODS[payout.method]}, réf. {payout.transfer_reference})."
                 if paid else f"Votre demande de retrait de {amount} a été refusée : {payout.note}"),
        category="billing", tone="success" if paid else "warning",
        action_label="Voir mes revenus", action_path="/app/manage/revenue",
    )
    db.commit()
    db.refresh(payout)
    return payout
