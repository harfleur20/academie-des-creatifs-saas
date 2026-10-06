from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    OrderInstallmentRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.services.membership_roles import load_effective_member_roles
from app.services.school_notifications import notify_school_managers
from app.services.tara_money import verify_payment


PURCHASE_BLOCKING_ROLES = frozenset({"owner", "admin", "manager", "teacher"})
PURCHASE_BLOCKED_MESSAGE = (
    "Un compte administrateur ou enseignant ne peut pas acheter une formation de cette école."
)


def is_public_purchase_blocked(
    db: Session,
    *,
    organization_id: int,
    user: UserRecord,
) -> bool:
    if user.platform_role == "super_admin":
        return True

    member = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == organization_id,
            OrganizationMemberRecord.user_id == user.id,
        )
    )
    if member is None:
        return False

    return bool(load_effective_member_roles(db, member).intersection(PURCHASE_BLOCKING_ROLES))


def require_public_purchase_allowed(
    db: Session,
    *,
    organization_id: int,
    user: UserRecord,
) -> None:
    if is_public_purchase_blocked(
        db,
        organization_id=organization_id,
        user=user,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, PURCHASE_BLOCKED_MESSAGE)


def review_blocked_staff_payment(
    db: Session,
    provider_reference: str,
    *,
    organization_id: int | None = None,
    user_id: int | None = None,
) -> StudentOrderRecord | None:
    """Record money received for a blocked staff account without granting student access.

    This protects old payment links created before a user became an owner/admin/manager/
    teacher. A real provider payment must never call the normal access-granting path for
    such an account. Instead the money is recorded and the order is sent to manual review.
    """

    installment_query = select(OrderInstallmentRecord).where(
        OrderInstallmentRecord.provider_reference == provider_reference
    )
    if organization_id is not None:
        installment_query = installment_query.where(
            OrderInstallmentRecord.organization_id == organization_id
        )
    installment = db.scalar(installment_query)
    if installment is None:
        return None

    order_query = (
        select(StudentOrderRecord)
        .options(
            selectinload(StudentOrderRecord.formation),
            selectinload(StudentOrderRecord.session),
        )
        .where(StudentOrderRecord.id == installment.order_id)
    )
    if user_id is not None:
        order_query = order_query.where(StudentOrderRecord.user_id == user_id)
    order = db.scalar(order_query)
    if order is None:
        return None

    user = db.get(UserRecord, order.user_id)
    if user is None or not is_public_purchase_blocked(
        db,
        organization_id=order.organization_id,
        user=user,
    ):
        return None

    if installment.status == "paid":
        return order

    verification = verify_payment(provider_reference)
    if verification.status == "pending":
        return order
    if verification.status == "failed":
        if order.status not in {"cancelled", "refunded", "payment_review"}:
            installment.status = "failed"
            db.commit()
        return order
    if verification.product_id != provider_reference:
        raise HTTPException(status.HTTP_409_CONFLICT, "Référence TaraMoney incohérente.")
    if verification.amount is None or verification.amount != installment.amount_cents:
        raise HTTPException(status.HTTP_409_CONFLICT, "Montant TaraMoney incohérent.")

    installment.status = "paid"
    installment.paid_at = verification.paid_at
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
    order.paid_at = verification.paid_at
    order.status = "payment_review"
    order.access_status = "pending_review"

    notify_school_managers(
        db,
        organization_id=order.organization_id,
        event_key=f"payment.staff_review:{installment.id}",
        title="Paiement d’un compte équipe à vérifier",
        message=(
            f"Le paiement de la commande {order.order_number} provient d’un compte "
            "administrateur ou enseignant. Aucun accès étudiant n’a été créé."
        ),
        category="payment",
        tone="warning",
        action_label="Vérifier le paiement",
        action_path="/app/manage/commerce",
    )
    db.commit()
    db.refresh(order)
    return order


def cancel_blocked_staff_unpaid_orders(
    db: Session,
    *,
    organization_id: int | None = None,
) -> int:
    """Cancel stale unpaid reservations owned by accounts that may no longer buy."""

    query = select(StudentOrderRecord).where(
        StudentOrderRecord.status == "pending",
        StudentOrderRecord.paid_cents == 0,
    )
    if organization_id is not None:
        query = query.where(StudentOrderRecord.organization_id == organization_id)

    changed = 0
    for order in db.scalars(query).all():
        user = db.get(UserRecord, order.user_id)
        if user is None or not is_public_purchase_blocked(
            db,
            organization_id=order.organization_id,
            user=user,
        ):
            continue

        order.status = "cancelled"
        order.access_status = "cancelled"
        for installment in db.scalars(
            select(OrderInstallmentRecord).where(
                OrderInstallmentRecord.order_id == order.id,
                OrderInstallmentRecord.status != "paid",
            )
        ).all():
            installment.status = "cancelled"
        changed += 1

    if changed:
        db.commit()
    return changed
