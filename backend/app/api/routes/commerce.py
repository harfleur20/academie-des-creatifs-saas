from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, get_tenant_context
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.commerce import *
from app.services.commerce import *
from app.services.tenancy import TenantContext

router=APIRouter(prefix="/commerce",tags=["commerce"])

@router.get("/public/{school_slug}",response_model=PublicSchoolRead)
def school_public(school_slug:str,db:Session=Depends(get_db)): return public_school(db,school_slug)

@router.get("/public/{school_slug}/formations",response_model=PublicCatalogRead)
def school_catalog(school_slug:str,db:Session=Depends(get_db)): return public_catalog(db,school_slug)

@router.get("/public/{school_slug}/formations/{formation_slug}",response_model=PublicFormationRead)
def formation_public(school_slug:str,formation_slug:str,db:Session=Depends(get_db)): return public_formation(db,school_slug,formation_slug)

@router.post("/public/{school_slug}/quote",response_model=PriceQuoteRead)
def price_quote(school_slug:str,p:PromoQuotePayload,db:Session=Depends(get_db),user:UserRecord=Depends(get_current_user)):
    school=get_school(db,school_slug);session=db.get(FormationSessionRecord,p.session_id)
    if not session or session.organization_id!=school.id: raise HTTPException(404,"Session introuvable.")
    formation=db.get(FormationRecord,session.formation_id)
    return quote(db,school,formation,session,user.id,p.promo_code)

@router.post("/public/{school_slug}/orders",response_model=OrderRead,status_code=201)
def new_order(school_slug:str,p:OrderCreate,db:Session=Depends(get_db),user:UserRecord=Depends(get_current_user)): return create_order(db,school_slug,user,p)

@router.post("/public/{school_slug}/orders/{order_id}/checkout",response_model=PaymentCheckoutRead)
def new_checkout(school_slug:str,order_id:int,db:Session=Depends(get_db),user:UserRecord=Depends(get_current_user)): return checkout_payment(db,school_slug,user,order_id)

@router.post("/public/{school_slug}/payments/{payment_id}/demo-confirm",response_model=DemoPaymentConfirmRead)
def demo_confirm(school_slug:str,payment_id:int,db:Session=Depends(get_db),user:UserRecord=Depends(get_current_user)): return confirm_demo(db,school_slug,user,payment_id)

@router.post("/payments/tara/reconcile/{reference}",response_model=OrderRead)
def tara_reconcile(reference:str,db:Session=Depends(get_db)): return reconcile_tara(db,reference)

@router.get("/admin/site",response_model=PublicSiteAdminRead)
def admin_site(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)):
    require_manager(tenant);return site_admin_read(db,db.get(OrganizationRecord,tenant.organization_id))

@router.put("/admin/site",response_model=PublicSiteAdminRead)
def admin_site_update(p:PublicSiteUpdate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return update_site(db,tenant,p)

@router.patch("/admin/formations/{formation_id}/commercial")
def admin_formation_commercial(formation_id:int,p:CommercialFormationUpdate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)):
    row=update_commercial_formation(db,tenant,formation_id,p);return {"id":row.id,"ok":True}

@router.patch("/admin/formations/{formation_id}/sessions/{session_id}/commercial")
def admin_session_commercial(formation_id:int,session_id:int,p:CommercialSessionUpdate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)):
    row=update_commercial_session(db,tenant,formation_id,session_id,p);return {"id":row.id,"ok":True}

@router.get("/admin/promotions",response_model=list[PromotionRead])
def promotions(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_promotions(db,tenant)
@router.post("/admin/promotions",response_model=PromotionRead,status_code=201)
def promotion_create(p:PromotionCreate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return create_promotion(db,tenant,p)

@router.get("/admin/promo-codes",response_model=list[PromoCodeRead])
def promo_codes(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_codes(db,tenant)
@router.post("/admin/promo-codes",response_model=PromoCodeRead,status_code=201)
def promo_code_create(p:PromoCodeCreate,db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return create_code(db,tenant,p)

@router.get("/admin/orders",response_model=list[OrderRead])
def orders(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return list_orders(db,tenant)
@router.get("/admin/students",response_model=list[StudentManagementRead])
def student_management(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return students(db,tenant)
@router.get("/admin/dashboard",response_model=CommercialDashboardRead)
def commercial_dashboard(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return dashboard(db,tenant)
@router.post("/admin/installments/lifecycle")
def installment_lifecycle(db:Session=Depends(get_db),tenant:TenantContext=Depends(get_tenant_context)): return {"changed":apply_installment_lifecycle(db,tenant)}
