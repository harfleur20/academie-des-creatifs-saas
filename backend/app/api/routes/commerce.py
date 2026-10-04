from __future__ import annotations

import hmac
import json

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import CommunicationOutboxRecord, OrderInvoiceRecord, StudentOrderRecord, UserRecord
from app.schemas.commerce import (
    CheckoutCreate,
    CheckoutRead,
    CommercialDashboardRead,
    CouponCreate,
    CouponRead,
    InvoiceRead,
    OrderRead,
    PricePreviewRead,
    PricePreviewRequest,
    PromotionCreate,
    PromotionRead,
    SchoolIdentityPayload,
    SchoolIdentityRead,
    StudentManagementRead,
)
from app.services.assets import store_school_asset
from app.services.communication_delivery import process_communication_outbox
from app.services.school_documents import build_invoice_pdf
from app.services.public_catalog import get_public_organization
from app.services.school_branding import get_school_identity, update_school_identity
from app.services.school_commerce import (
    commercial_dashboard,
    cancel_pending_order,
    confirm_demo_checkout,
    create_checkout,
    create_coupon,
    create_installment_payment_link,
    create_promotion,
    get_order_for_user,
    list_coupons,
    list_invoices,
    list_orders,
    list_orders_for_user,
    list_promotions,
    list_students,
    price_preview,
    process_installment_lifecycle,
    reconcile_tara_for_user,
    reconcile_tara_reference,
    set_coupon_active,
    set_promotion_active,
    verified_return_origin,
)
from app.services.tara_webhook import verify_webhook_authentication
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/commerce", tags=["commerce"])
MAX_TARA_WEBHOOK_BYTES = 16 * 1024


@router.get("/identity", response_model=SchoolIdentityRead)
def read_identity(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return get_school_identity(db, tenant)


@router.put("/identity", response_model=SchoolIdentityRead)
def save_identity(
    payload: SchoolIdentityPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return update_school_identity(db, tenant, payload)


@router.post("/assets", status_code=201)
async def upload_school_asset(
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    if not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès gestion requis.")
    return await store_school_asset(file, tenant.organization_id)


@router.get("/dashboard", response_model=CommercialDashboardRead)
def dashboard(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return commercial_dashboard(db, tenant)


@router.get("/communications/needs-review")
def communications_needing_review(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès gestion requis.")
    rows = db.scalars(select(CommunicationOutboxRecord).where(
        CommunicationOutboxRecord.organization_id == tenant.organization_id,
        CommunicationOutboxRecord.status == "needs_review",
    ).order_by(CommunicationOutboxRecord.created_at)).all()
    return [{
        "id": row.id,
        "channel": row.channel,
        "recipient": row.recipient,
        "event_key": row.event_key,
        "attempts_count": row.attempts_count,
        "last_error": row.last_error,
        "claimed_at": row.claimed_at,
    } for row in rows]


@router.post("/communications/{message_id}/retry", status_code=204)
def retry_communication_after_review(
    message_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if tenant.support_mode or not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès gestion requis.")
    row = db.scalar(select(CommunicationOutboxRecord).where(
        CommunicationOutboxRecord.id == message_id,
        CommunicationOutboxRecord.organization_id == tenant.organization_id,
    ).with_for_update())
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message introuvable.")
    if row.status != "needs_review":
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce message ne nécessite pas de reprise.")
    row.status = "pending"
    row.attempts_count = 0
    row.claimed_at = None
    row.claim_token = None
    row.last_error = None
    db.commit()
    return None


@router.get("/orders", response_model=list[OrderRead])
def orders(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_orders(db, tenant)


@router.get("/invoices", response_model=list[InvoiceRead])
def invoices(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_invoices(db, tenant)


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès gestion requis.")
    invoice = db.get(OrderInvoiceRecord, invoice_id)
    if invoice is None or invoice.organization_id != tenant.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facture introuvable.")
    filename, content = build_invoice_pdf(db, invoice)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/public/{school_key}/orders/{order_id}/invoices",
    response_model=list[InvoiceRead],
)
def read_my_invoices(
    school_key: str,
    order_id: int,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    order = db.get(StudentOrderRecord, order_id)
    if (
        order is None
        or order.organization_id != org.id
        or order.user_id != user.id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable.")
    rows = db.query(OrderInvoiceRecord).filter(
        OrderInvoiceRecord.organization_id == org.id,
        OrderInvoiceRecord.order_id == order.id,
    ).order_by(OrderInvoiceRecord.issued_at.desc()).all()
    return [
        InvoiceRead(
            id=row.id,
            order_id=row.order_id,
            installment_id=row.installment_id,
            invoice_number=row.invoice_number,
            status=row.status,
            amount_cents=row.amount_cents,
            currency=row.currency,
            branding_snapshot=row.branding_snapshot or {},
            issued_at=row.issued_at,
            paid_at=row.paid_at,
        )
        for row in rows
    ]


@router.get("/public/{school_key}/invoices/{invoice_id}/pdf")
def download_my_invoice_pdf(
    school_key: str,
    invoice_id: int,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    invoice = db.get(OrderInvoiceRecord, invoice_id)
    if invoice is None or invoice.organization_id != org.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facture introuvable.")
    order = db.get(StudentOrderRecord, invoice.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Facture introuvable.")
    filename, content = build_invoice_pdf(db, invoice)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/students", response_model=list[StudentManagementRead])
def students(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_students(db, tenant)


@router.get("/promotions", response_model=list[PromotionRead])
def promotions(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_promotions(db, tenant)


@router.post("/promotions", response_model=PromotionRead, status_code=201)
def add_promotion(
    payload: PromotionCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_promotion(db, tenant, payload)


@router.patch("/promotions/{promotion_id}", response_model=PromotionRead)
def toggle_promotion(
    promotion_id: int,
    active: bool,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return set_promotion_active(db, tenant, promotion_id, active)


@router.get("/coupons", response_model=list[CouponRead])
def coupons(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_coupons(db, tenant)


@router.post("/coupons", response_model=CouponRead, status_code=201)
def add_coupon(
    payload: CouponCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_coupon(db, tenant, payload)


@router.patch("/coupons/{coupon_id}", response_model=CouponRead)
def toggle_coupon(
    coupon_id: int,
    active: bool,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return set_coupon_active(db, tenant, coupon_id, active)


@router.post(
    "/public/{school_key}/price-preview",
    response_model=PricePreviewRead,
)
def preview_public_price(
    school_key: str,
    payload: PricePreviewRequest,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return price_preview(
        db,
        org,
        user_id=user.id,
        session_id=payload.session_id,
        coupon_code=payload.coupon_code,
    )


@router.post(
    "/public/{school_key}/checkout",
    response_model=CheckoutRead,
    status_code=201,
)
def checkout_public(
    school_key: str,
    payload: CheckoutCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return create_checkout(
        db, org, user, payload,
        return_origin=verified_return_origin(db, org, request.headers.get("origin")),
    )


@router.get("/public/{school_key}/orders", response_model=list[OrderRead])
def list_my_orders(
    school_key: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return list_orders_for_user(db, org, user)


@router.get(
    "/public/{school_key}/orders/{order_id}",
    response_model=OrderRead,
)
def read_my_order(
    school_key: str,
    order_id: int,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return get_order_for_user(db, org, user, order_id)


@router.post("/public/{school_key}/orders/{order_id}/cancel", response_model=CheckoutRead)
def cancel_my_order(
    school_key: str,
    order_id: int,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return cancel_pending_order(db, org, user, order_id)


@router.post(
    "/public/{school_key}/orders/{order_id}/demo-confirm",
    response_model=CheckoutRead,
)
def demo_confirm(
    school_key: str,
    order_id: int,
    payment_ref: str | None = None,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return confirm_demo_checkout(db, org, user, order_id, payment_ref)


@router.post(
    "/public/{school_key}/installments/{installment_id}/pay",
)
def pay_installment(
    school_key: str,
    installment_id: int,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return {
        "checkout_url": create_installment_payment_link(
            db, org, user, installment_id
        )
    }


@router.post(
    "/public/{school_key}/tara/reconcile/{provider_reference}",
    response_model=CheckoutRead,
)
def reconcile_checkout(
    school_key: str,
    provider_reference: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return reconcile_tara_for_user(db, org, user, provider_reference)


@router.post("/internal/lifecycle", include_in_schema=False)
def commerce_lifecycle(
    db: Session = Depends(get_db),
    cron_secret: str | None = Header(default=None, alias="X-Billing-Cron-Secret"),
):
    if (
        not settings.billing_cron_secret
        or not cron_secret
        or not hmac.compare_digest(settings.billing_cron_secret, cron_secret)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Secret cron invalide.")
    transitioned = process_installment_lifecycle(db)
    communications = process_communication_outbox(db)
    return {
        "transitioned": transitioned,
        "communications": communications,
    }


@router.post("/tara/webhook")
async def commerce_tara_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    if len(raw_body) > MAX_TARA_WEBHOOK_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Notification trop volumineuse.")
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Payload non JSON.") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Payload invalide.")

    authenticated = verify_webhook_authentication(raw_body, request.headers)
    product_id = payload.get("productId") or payload.get("product_id")
    if not isinstance(product_id, str) or not product_id.startswith("SCH-"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Référence paiement invalide.")
    if not authenticated:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Notification non vérifiable.")

    order = reconcile_tara_reference(db, product_id)
    return {
        "received": True,
        "authenticated": authenticated,
        "order_id": order.id,
        "status": order.status,
    }
