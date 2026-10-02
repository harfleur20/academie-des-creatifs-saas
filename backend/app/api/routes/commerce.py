from __future__ import annotations

import hmac
import json

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import UserRecord
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
from app.services.public_catalog import get_public_organization
from app.services.school_branding import get_school_identity, update_school_identity
from app.services.school_commerce import (
    commercial_dashboard,
    confirm_demo_checkout,
    create_checkout,
    create_coupon,
    create_installment_payment_link,
    create_promotion,
    get_order_for_user,
    list_coupons,
    list_invoices,
    list_orders,
    list_promotions,
    list_students,
    price_preview,
    process_installment_lifecycle,
    reconcile_tara_for_user,
    reconcile_tara_reference,
    set_coupon_active,
    set_promotion_active,
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
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return create_checkout(db, org, user, payload)


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


@router.post(
    "/public/{school_key}/orders/{order_id}/demo-confirm",
    response_model=CheckoutRead,
)
def demo_confirm(
    school_key: str,
    order_id: int,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = get_public_organization(db, school_key)
    return confirm_demo_checkout(db, org, user, order_id)


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
    return {"transitioned": process_installment_lifecycle(db)}


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
    business_id = payload.get("businessId")
    if not isinstance(product_id, str) or not product_id.startswith("SCH-"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Référence paiement invalide.")
    if not authenticated and business_id != settings.tara_business_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Notification non vérifiable.")

    order = reconcile_tara_reference(db, product_id)
    return {
        "received": True,
        "authenticated": authenticated,
        "order_id": order.id,
        "status": order.status,
    }
