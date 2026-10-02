from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    EnrollmentRecord, FormationRecord, FormationSessionRecord, OrganizationMemberRecord,
    OrganizationMemberRoleRecord, OrganizationPublicSiteRecord, OrganizationRecord,
    OrganizationStudentProfileRecord, PaymentInstallmentRecord, PromoCodeRecord,
    PromotionRecord, SchoolOrderRecord, SchoolPaymentRecord, StudentInvoiceRecord, UserRecord,
)
from app.schemas.commerce import *
from app.services.tara_money import create_payment_link, verify_payment
from app.services.tenancy import TenantContext


def now_utc() -> datetime:
    return datetime.now(UTC)

def _aware(v: datetime | None) -> datetime | None:
    if v is None: return None
    return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)

def require_manager(tenant: TenantContext) -> None:
    if tenant.user.platform_role == "super_admin" and tenant.support_mode: return
    if not tenant.organization_roles.intersection({"owner","admin","manager"}):
        raise HTTPException(403,"Accès gestion école requis.")

def get_school(db: Session, slug: str) -> OrganizationRecord:
    school=db.scalar(select(OrganizationRecord).where(OrganizationRecord.slug==slug.strip().lower(),OrganizationRecord.is_active.is_(True),OrganizationRecord.status=="active"))
    if school is None: raise HTTPException(404,"École introuvable.")
    return school

def ensure_site(db: Session, school: OrganizationRecord) -> OrganizationPublicSiteRecord:
    row=db.scalar(select(OrganizationPublicSiteRecord).where(OrganizationPublicSiteRecord.organization_id==school.id))
    if row is None:
        prefix="".join(part[0] for part in re.findall(r"[A-Za-zÀ-ÿ0-9]+",school.name)[:3]).upper() or "AC"
        row=OrganizationPublicSiteRecord(organization_id=school.id,hero_title=school.name,contact_email=school.contact_email,student_code_prefix=prefix[:8])
        db.add(row);db.commit();db.refresh(row)
    return row

def site_admin_read(db:Session,school:OrganizationRecord)->PublicSiteAdminRead:
    s=ensure_site(db,school)
    return PublicSiteAdminRead(organization_id=school.id,school_name=school.name,logo_url=school.logo_url,primary_color=school.primary_color,secondary_color=school.secondary_color,accent_color=school.accent_color,**{k:getattr(s,k) for k in PublicSiteUpdate.model_fields})

def update_site(db:Session,tenant:TenantContext,p:PublicSiteUpdate)->PublicSiteAdminRead:
    require_manager(tenant); school=db.get(OrganizationRecord,tenant.organization_id); s=ensure_site(db,school)
    for k,v in p.model_dump().items(): setattr(s,k,v.strip() if isinstance(v,str) else v)
    db.commit();return site_admin_read(db,school)

def _discount(base:int,kind:str,value:int)->int:
    if kind=="percentage": return min(base,max(0,round(base*min(value,100)/100)))
    return min(base,max(0,value))

def _active_promo(db:Session,org:int,formation:int,session:int,base:int)->tuple[int,PromotionRecord|None]:
    now=now_utc()
    rows=list(db.scalars(select(PromotionRecord).where(PromotionRecord.organization_id==org,PromotionRecord.is_active.is_(True))).all())
    best=(0,None)
    for row in rows:
        if row.formation_id not in {None,formation} or row.session_id not in {None,session}: continue
        if row.starts_at and _aware(row.starts_at)>now: continue
        if row.ends_at and _aware(row.ends_at)<now: continue
        if row.max_uses is not None and row.used_count>=row.max_uses: continue
        value=_discount(base,row.discount_type,row.discount_value)
        if value>best[0]: best=(value,row)
    return best

def _promo_code(db:Session,org:int,user:int,formation:int,session:int,base_after_direct:int,code:str|None,direct_discount:int)->tuple[int,PromoCodeRecord|None]:
    if not code: return 0,None
    row=db.scalar(select(PromoCodeRecord).where(PromoCodeRecord.organization_id==org,func.upper(PromoCodeRecord.code)==code.strip().upper(),PromoCodeRecord.is_active.is_(True)))
    if row is None: raise HTTPException(422,"Code promo invalide.")
    now=now_utc()
    if row.starts_at and _aware(row.starts_at)>now: raise HTTPException(422,"Ce code promo n'est pas encore actif.")
    if row.ends_at and _aware(row.ends_at)<now: raise HTTPException(422,"Ce code promo a expiré.")
    if row.max_uses is not None and row.used_count>=row.max_uses: raise HTTPException(422,"Ce code promo a atteint sa limite d'utilisation.")
    if row.formation_id not in {None,formation} or row.session_id not in {None,session}: raise HTTPException(422,"Ce code promo ne s'applique pas à cette session.")
    if direct_discount and not row.allow_on_promotions: raise HTTPException(422,"Ce code promo n'est pas cumulable avec la promotion en cours.")
    if base_after_direct<row.minimum_order_cents: raise HTTPException(422,"Le montant minimum pour ce code promo n'est pas atteint.")
    used=int(db.scalar(select(func.count(SchoolOrderRecord.id)).where(SchoolOrderRecord.organization_id==org,SchoolOrderRecord.student_user_id==user,func.upper(SchoolOrderRecord.promo_code)==row.code.upper(),SchoolOrderRecord.status.notin_(["cancelled","failed"]))) or 0)
    if used>=row.max_uses_per_customer: raise HTTPException(422,"Vous avez déjà utilisé ce code promo.")
    return _discount(base_after_direct,row.discount_type,row.discount_value),row

def _availability(db:Session,formation:FormationRecord,session:FormationSessionRecord)->tuple[bool,str|None,int|None]:
    if not session.public_enrollment_enabled: return False,"Inscriptions non ouvertes.",None
    if session.status!="open": return False,"Aucune nouvelle session disponible.",None
    now=now_utc()
    if session.enrollment_opens_at and _aware(session.enrollment_opens_at)>now: return False,"Les inscriptions ne sont pas encore ouvertes.",None
    if session.enrollment_closes_at and _aware(session.enrollment_closes_at)<now: return False,"Les inscriptions sont clôturées.",None
    count=int(db.scalar(select(func.count(EnrollmentRecord.id)).where(EnrollmentRecord.organization_id==formation.organization_id,EnrollmentRecord.session_id==session.id,EnrollmentRecord.status.in_(["active","completed"]))) or 0)
    remaining=None if session.seat_capacity<=0 else max(0,session.seat_capacity-count)
    if remaining==0:return False,"Cette session est complète.",0
    return True,None,remaining

def quote(db:Session,school:OrganizationRecord,formation:FormationRecord,session:FormationSessionRecord,user_id:int|None=None,code:str|None=None)->PriceQuoteRead:
    ok,reason,_=_availability(db,formation,session)
    if not ok: raise HTTPException(409,reason)
    base=session.price_override_cents if session.price_override_cents is not None else formation.base_price_cents
    direct,promo=_active_promo(db,school.id,formation.id,session.id,base)
    code_discount,code_row=_promo_code(db,school.id,user_id or 0,formation.id,session.id,base-direct,code,direct) if code else (0,None)
    final=max(0,base-direct-code_discount)
    return PriceQuoteRead(formation_id=formation.id,session_id=session.id,currency=formation.currency,base_price_cents=base,direct_discount_cents=direct,promo_code=code_row.code if code_row else None,promo_code_discount_cents=code_discount,final_price_cents=final,installment_count=formation.installment_count if formation.allow_installments else 1,allow_installments=formation.allow_installments)

def _public_formation(db:Session,formation:FormationRecord,user_id:int|None=None)->PublicFormationRead:
    session_views=[]
    best_price=formation.base_price_cents
    best_discount=0
    for s in sorted(formation.sessions,key=lambda x:(x.start_date,x.id)):
        ok,reason,remaining=_availability(db,formation,s)
        base=s.price_override_cents if s.price_override_cents is not None else formation.base_price_cents
        direct,_=_active_promo(db,formation.organization_id,formation.id,s.id,base)
        if ok and (not session_views or base-direct<best_price-best_discount): best_price,best_discount=base,direct
        session_views.append(PublicSessionRead(id=s.id,label=s.label,start_date=s.start_date,end_date=s.end_date,campus_label=s.campus_label,seats_remaining=remaining,price_cents=max(0,base-direct),currency=formation.currency,is_available=ok,unavailable_reason=reason))
    return PublicFormationRead(id=formation.id,slug=formation.slug,title=formation.title,short_description=formation.short_description,description=formation.description,cover_url=formation.cover_url,category=formation.category,level=formation.level,format_type=formation.format_type,training_hours=formation.training_hours,objectives=formation.objectives,prerequisites=formation.prerequisites,public_program=formation.public_program,base_price_cents=formation.base_price_cents,currency=formation.currency,display_price_cents=max(0,best_price-best_discount),direct_discount_cents=best_discount,featured_on_home=formation.featured_on_home,featured_order=formation.featured_order,is_public=formation.is_public,allow_installments=formation.allow_installments,installment_count=formation.installment_count,installment_grace_days=formation.installment_grace_days,sessions=session_views,can_buy=any(x.is_available for x in session_views))

def public_school(db:Session,slug:str)->PublicSchoolRead:
    school=get_school(db,slug); site=site_admin_read(db,school)
    formations=list(db.scalars(select(FormationRecord).where(FormationRecord.organization_id==school.id,FormationRecord.status=="published",FormationRecord.is_public.is_(True)).order_by(FormationRecord.featured_order,FormationRecord.created_at.desc())).all())
    featured=[x for x in formations if x.featured_on_home][:6]
    if not featured:
        available=[x for x in formations if _public_formation(db,x).can_buy]
        featured=(available or formations)[:6]
    return PublicSchoolRead(organization_id=school.id,slug=school.slug,name=school.name,logo_url=school.logo_url,primary_color=school.primary_color,secondary_color=school.secondary_color,accent_color=school.accent_color,site=site,featured_formations=[_public_formation(db,x) for x in featured])

def public_catalog(db:Session,slug:str)->PublicCatalogRead:
    school=get_school(db,slug); root=public_school(db,slug)
    rows=list(db.scalars(select(FormationRecord).where(FormationRecord.organization_id==school.id,FormationRecord.status=="published",FormationRecord.is_public.is_(True)).order_by(FormationRecord.created_at.desc())).all())
    return PublicCatalogRead(school=root,formations=[_public_formation(db,x) for x in rows])

def public_formation(db:Session,slug:str,formation_slug:str)->PublicFormationRead:
    school=get_school(db,slug); row=db.scalar(select(FormationRecord).where(FormationRecord.organization_id==school.id,FormationRecord.slug==formation_slug,FormationRecord.status=="published",FormationRecord.is_public.is_(True)))
    if row is None: raise HTTPException(404,"Formation introuvable.")
    return _public_formation(db,row)

def update_commercial_formation(db:Session,tenant:TenantContext,formation_id:int,p:CommercialFormationUpdate):
    require_manager(tenant); row=db.scalar(select(FormationRecord).where(FormationRecord.id==formation_id,FormationRecord.organization_id==tenant.organization_id))
    if not row: raise HTTPException(404,"Formation introuvable.")
    for k,v in p.model_dump(exclude_unset=True).items(): setattr(row,k,v.upper() if k=="currency" and isinstance(v,str) else v)
    db.commit();return row

def update_commercial_session(db:Session,tenant:TenantContext,formation_id:int,session_id:int,p:CommercialSessionUpdate):
    require_manager(tenant); row=db.scalar(select(FormationSessionRecord).where(FormationSessionRecord.id==session_id,FormationSessionRecord.formation_id==formation_id,FormationSessionRecord.organization_id==tenant.organization_id))
    if not row: raise HTTPException(404,"Session introuvable.")
    for k,v in p.model_dump(exclude_unset=True).items(): setattr(row,k,v)
    db.commit();return row

def create_promotion(db:Session,tenant:TenantContext,p:PromotionCreate)->PromotionRecord:
    require_manager(tenant); row=PromotionRecord(organization_id=tenant.organization_id,**p.model_dump());db.add(row);db.commit();db.refresh(row);return row
def create_code(db:Session,tenant:TenantContext,p:PromoCodeCreate)->PromoCodeRecord:
    require_manager(tenant); data=p.model_dump();data["code"]=data["code"].strip().upper();row=PromoCodeRecord(organization_id=tenant.organization_id,**data);db.add(row);db.commit();db.refresh(row);return row
def list_promotions(db:Session,tenant:TenantContext): require_manager(tenant);return list(db.scalars(select(PromotionRecord).where(PromotionRecord.organization_id==tenant.organization_id).order_by(PromotionRecord.created_at.desc())).all())
def list_codes(db:Session,tenant:TenantContext): require_manager(tenant);return list(db.scalars(select(PromoCodeRecord).where(PromoCodeRecord.organization_id==tenant.organization_id).order_by(PromoCodeRecord.created_at.desc())).all())

def _brand_snapshot(db:Session,school:OrganizationRecord)->dict:
    site=ensure_site(db,school)
    return {"school_name":school.name,"logo_url":school.logo_url,"primary_color":school.primary_color,"secondary_color":school.secondary_color,"accent_color":school.accent_color,"legal_name":site.legal_name,"registration_number":site.legal_registration_number,"tax_number":site.tax_number,"billing_address":site.billing_address,"contact_email":site.contact_email,"contact_phone":site.contact_phone}

def _installments(db:Session,order:SchoolOrderRecord,grace_days:int):
    if order.payment_plan!="installments" or order.installment_count<=1:
        count=1
    else: count=order.installment_count
    quotient,remainder=divmod(order.final_price_cents,count)
    now=now_utc()
    rows=[]
    for i in range(count):
        amount=quotient+(1 if i<remainder else 0)
        due=now if i==0 else now+timedelta(days=30*i)
        row=PaymentInstallmentRecord(organization_id=order.organization_id,order_id=order.id,installment_number=i+1,amount_cents=amount,due_at=due,grace_until=due+timedelta(days=grace_days),status="due" if i==0 else "pending")
        db.add(row);rows.append(row)
    db.flush();return rows

def _student_code(db:Session,school:OrganizationRecord,user:UserRecord)->OrganizationStudentProfileRecord:
    existing=db.scalar(select(OrganizationStudentProfileRecord).where(OrganizationStudentProfileRecord.organization_id==school.id,OrganizationStudentProfileRecord.user_id==user.id))
    if existing:return existing
    site=ensure_site(db,school);prefix=(site.student_code_prefix or "AC").upper()
    year=now_utc().year%100
    seq=int(db.scalar(select(func.max(OrganizationStudentProfileRecord.code_sequence)).where(OrganizationStudentProfileRecord.organization_id==school.id,OrganizationStudentProfileRecord.code_year==year)) or 0)+1
    row=OrganizationStudentProfileRecord(organization_id=school.id,user_id=user.id,student_code=f"{prefix}{year:02d}-{seq:03d}",code_year=year,code_sequence=seq,access_status="active")
    db.add(row);db.flush();return row

def _has_blocking_overdue(db: Session, organization_id: int, user_id: int) -> bool:
    order_ids = select(SchoolOrderRecord.id).where(
        SchoolOrderRecord.organization_id == organization_id,
        SchoolOrderRecord.student_user_id == user_id,
        SchoolOrderRecord.status.notin_(["cancelled", "failed"]),
    )
    return (
        db.scalar(
            select(PaymentInstallmentRecord.id).where(
                PaymentInstallmentRecord.organization_id == organization_id,
                PaymentInstallmentRecord.order_id.in_(order_ids),
                PaymentInstallmentRecord.status == "late",
            ).limit(1)
        )
        is not None
    )


def _grant_access(db:Session,order:SchoolOrderRecord)->OrganizationStudentProfileRecord:
    school=db.get(OrganizationRecord,order.organization_id); user=db.get(UserRecord,order.student_user_id)
    member=db.scalar(select(OrganizationMemberRecord).where(OrganizationMemberRecord.organization_id==school.id,OrganizationMemberRecord.user_id==user.id))
    if member is None:
        member=OrganizationMemberRecord(organization_id=school.id,user_id=user.id,role="student",status="active");db.add(member);db.flush()
    elif member.status!="active": member.status="active"
    if member.role!="student":
        role=db.scalar(select(OrganizationMemberRoleRecord).where(OrganizationMemberRoleRecord.organization_id==school.id,OrganizationMemberRoleRecord.member_id==member.id,OrganizationMemberRoleRecord.role=="student"))
        if role is None: db.add(OrganizationMemberRoleRecord(organization_id=school.id,member_id=member.id,role="student"))
    profile=_student_code(db,school,user)
    if not _has_blocking_overdue(db, school.id, user.id):
        profile.access_status="active";profile.access_suspended_reason=None;profile.access_suspended_at=None
    enrollment=db.scalar(select(EnrollmentRecord).where(EnrollmentRecord.organization_id==school.id,EnrollmentRecord.session_id==order.session_id,EnrollmentRecord.student_id==user.id))
    if enrollment is None: db.add(EnrollmentRecord(organization_id=school.id,session_id=order.session_id,student_id=user.id,status="active"))
    else: enrollment.status="active"
    if order.access_granted_at is None:order.access_granted_at=now_utc()
    if order.status=="pending":order.status="partially_paid"
    return profile

def create_order(db:Session,school_slug:str,user:UserRecord,p:OrderCreate)->OrderRead:
    school=get_school(db,school_slug)
    session=db.scalar(select(FormationSessionRecord).where(FormationSessionRecord.id==p.session_id,FormationSessionRecord.organization_id==school.id))
    if not session:raise HTTPException(404,"Session introuvable.")
    formation=db.get(FormationRecord,session.formation_id)
    if not formation or not formation.is_public or formation.status!="published":raise HTTPException(404,"Formation introuvable.")
    q=quote(db,school,formation,session,user.id,p.promo_code)
    if p.payment_plan=="installments" and not q.allow_installments:raise HTTPException(422,"Le paiement en plusieurs fois n'est pas disponible.")
    count=q.installment_count if p.payment_plan=="installments" else 1
    order=SchoolOrderRecord(organization_id=school.id,order_reference=f"ORD-{school.id}-{uuid4().hex[:14].upper()}",student_user_id=user.id,formation_id=formation.id,session_id=session.id,status="pending",currency=q.currency,base_price_cents=q.base_price_cents,direct_discount_cents=q.direct_discount_cents,promo_code=q.promo_code,promo_code_discount_cents=q.promo_code_discount_cents,final_price_cents=q.final_price_cents,payment_plan=p.payment_plan,installment_count=count,brand_snapshot=_brand_snapshot(db,school))
    db.add(order);db.flush();_installments(db,order,formation.installment_grace_days)
    if q.promo_code:
        code=db.scalar(select(PromoCodeRecord).where(PromoCodeRecord.organization_id==school.id,func.upper(PromoCodeRecord.code)==q.promo_code.upper()).with_for_update())
        if code:code.used_count+=1
    direct,promotion=_active_promo(db,school.id,formation.id,session.id,q.base_price_cents)
    if promotion and direct:promotion.used_count+=1
    db.commit();return order_read(db,order)

def order_read(db:Session,order:SchoolOrderRecord)->OrderRead:
    school=db.get(OrganizationRecord,order.organization_id);user=db.get(UserRecord,order.student_user_id);formation=db.get(FormationRecord,order.formation_id);session=db.get(FormationSessionRecord,order.session_id)
    profile=db.scalar(select(OrganizationStudentProfileRecord).where(OrganizationStudentProfileRecord.organization_id==order.organization_id,OrganizationStudentProfileRecord.user_id==order.student_user_id))
    rows=list(db.scalars(select(PaymentInstallmentRecord).where(PaymentInstallmentRecord.order_id==order.id).order_by(PaymentInstallmentRecord.installment_number)).all())
    return OrderRead(id=order.id,order_reference=order.order_reference,school_name=school.name,student_name=user.full_name,formation_title=formation.title,session_label=session.label,status=order.status,currency=order.currency,base_price_cents=order.base_price_cents,direct_discount_cents=order.direct_discount_cents,promo_code=order.promo_code,promo_code_discount_cents=order.promo_code_discount_cents,final_price_cents=order.final_price_cents,payment_plan=order.payment_plan,installment_count=order.installment_count,paid_cents=order.paid_cents,student_code=profile.student_code if profile else None,access_status=profile.access_status if profile else None,installments=[InstallmentRead.model_validate(x,from_attributes=True) for x in rows],created_at=order.created_at)

def list_orders(db:Session,tenant:TenantContext):
    require_manager(tenant);return [order_read(db,x) for x in db.scalars(select(SchoolOrderRecord).where(SchoolOrderRecord.organization_id==tenant.organization_id).order_by(SchoolOrderRecord.created_at.desc())).all()]

def checkout_payment(db:Session,school_slug:str,user:UserRecord,order_id:int)->PaymentCheckoutRead:
    school=get_school(db,school_slug);order=db.scalar(select(SchoolOrderRecord).where(SchoolOrderRecord.id==order_id,SchoolOrderRecord.organization_id==school.id,SchoolOrderRecord.student_user_id==user.id))
    if not order:raise HTTPException(404,"Commande introuvable.")
    installment=db.scalar(select(PaymentInstallmentRecord).where(PaymentInstallmentRecord.order_id==order.id,PaymentInstallmentRecord.status.in_(["due","pending","late"])).order_by(PaymentInstallmentRecord.installment_number))
    if not installment:raise HTTPException(409,"Aucune échéance à payer.")
    ref=f"SCHOOL-{school.id}-{order.id}-{installment.installment_number}-{uuid4().hex[:8]}"
    provider="demo" if settings.payment_mode=="demo" else "taramoney"
    payment=SchoolPaymentRecord(organization_id=school.id,order_id=order.id,installment_id=installment.id,provider=provider,provider_reference=ref,status="pending",amount_cents=installment.amount_cents,currency=order.currency)
    db.add(payment);db.commit();db.refresh(payment)
    if provider=="taramoney":
        if order.currency!="XAF":raise HTTPException(422,"TaraMoney exige une tarification en XAF.")
        session=create_payment_link(product_id=ref,product_name=f"{order.brand_snapshot.get('school_name','École')} - {db.get(FormationRecord,order.formation_id).title}",amount_xaf=payment.amount_cents,description=f"Échéance {installment.installment_number}/{order.installment_count}",return_url=f"{settings.frontend_url}/schools/{school.slug}/checkout/success?order={order.id}",webhook_url=f"{settings.backend_public_url}{settings.api_prefix}/commerce/payments/tara/reconcile/{ref}")
        payment.checkout_url=session.checkout_url;db.commit()
    return PaymentCheckoutRead(payment_id=payment.id,provider=payment.provider,amount_cents=payment.amount_cents,currency=payment.currency,status=payment.status,checkout_url=payment.checkout_url)

def _mark_paid(db:Session,payment:SchoolPaymentRecord,transaction_id:str|None=None)->OrderRead:
    if payment.status=="paid":return order_read(db,db.get(SchoolOrderRecord,payment.order_id))
    order=db.get(SchoolOrderRecord,payment.order_id);installment=db.get(PaymentInstallmentRecord,payment.installment_id)
    payment.status="paid";payment.paid_at=now_utc();payment.provider_transaction_id=transaction_id
    installment.status="paid";installment.paid_at=payment.paid_at
    order.paid_cents=min(order.final_price_cents,order.paid_cents+payment.amount_cents)
    _grant_access(db,order)
    remaining=int(db.scalar(select(func.count(PaymentInstallmentRecord.id)).where(PaymentInstallmentRecord.order_id==order.id,PaymentInstallmentRecord.status!="paid")) or 0)
    order.status="paid" if remaining==0 else "partially_paid"
    invoice=StudentInvoiceRecord(organization_id=order.organization_id,order_id=order.id,payment_id=payment.id,invoice_number=f"INV-{order.organization_id}-{payment.paid_at:%Y%m%d}-{payment.id:06d}",status="paid",amount_cents=payment.amount_cents,currency=payment.currency,issued_at=payment.paid_at,paid_at=payment.paid_at,brand_snapshot=dict(order.brand_snapshot))
    db.add(invoice);db.commit();return order_read(db,order)

def confirm_demo(db:Session,school_slug:str,user:UserRecord,payment_id:int)->DemoPaymentConfirmRead:
    school=get_school(db,school_slug);payment=db.scalar(select(SchoolPaymentRecord).join(SchoolOrderRecord,SchoolOrderRecord.id==SchoolPaymentRecord.order_id).where(SchoolPaymentRecord.id==payment_id,SchoolPaymentRecord.organization_id==school.id,SchoolPaymentRecord.provider=="demo",SchoolOrderRecord.student_user_id==user.id))
    if not payment:raise HTTPException(404,"Paiement introuvable.")
    order=_mark_paid(db,payment,f"DEMO-{uuid4().hex[:12]}")
    return DemoPaymentConfirmRead(order=order,payment=PaymentCheckoutRead(payment_id=payment.id,provider=payment.provider,amount_cents=payment.amount_cents,currency=payment.currency,status="paid",checkout_url=None))

def reconcile_tara(db:Session,reference:str)->OrderRead:
    payment=db.scalar(select(SchoolPaymentRecord).where(SchoolPaymentRecord.provider_reference==reference,SchoolPaymentRecord.provider=="taramoney"))
    if not payment:raise HTTPException(404,"Paiement introuvable.")
    v=verify_payment(reference)
    if v.status=="pending":return order_read(db,db.get(SchoolOrderRecord,payment.order_id))
    if v.status=="failed":payment.status="failed";payment.failure_reason=v.message;db.commit();return order_read(db,db.get(SchoolOrderRecord,payment.order_id))
    if v.amount!=payment.amount_cents:raise HTTPException(409,"Montant TaraMoney incohérent.")
    return _mark_paid(db,payment,v.transaction_id)

def apply_installment_lifecycle(db:Session,tenant:TenantContext|None=None)->int:
    now=now_utc();stmt=select(PaymentInstallmentRecord).where(PaymentInstallmentRecord.status.in_(["pending","due","late"]))
    if tenant: require_manager(tenant);stmt=stmt.where(PaymentInstallmentRecord.organization_id==tenant.organization_id)
    changed=0
    for inst in db.scalars(stmt).all():
        due=_aware(inst.due_at);grace=_aware(inst.grace_until)
        if due and due<=now and inst.status=="pending":inst.status="due";changed+=1
        if grace and grace<now and inst.status!="paid":
            inst.status="late";order=db.get(SchoolOrderRecord,inst.order_id)
            if order and order.access_granted_at:
                profile=db.scalar(select(OrganizationStudentProfileRecord).where(OrganizationStudentProfileRecord.organization_id==order.organization_id,OrganizationStudentProfileRecord.user_id==order.student_user_id))
                if profile and profile.access_status!="suspended":
                    profile.access_status="suspended";profile.access_suspended_reason="Échéance de paiement impayée.";profile.access_suspended_at=now;changed+=1
                    # Keep enrollments and all pedagogical history intact.
                    # Access gating is handled by the organization student profile.
    db.commit();return changed

def students(db:Session,tenant:TenantContext):
    require_manager(tenant);rows=list(db.scalars(select(OrganizationStudentProfileRecord).where(OrganizationStudentProfileRecord.organization_id==tenant.organization_id).order_by(OrganizationStudentProfileRecord.created_at.desc())).all());out=[]
    for p in rows:
        u=db.get(UserRecord,p.user_id);sessions=int(db.scalar(select(func.count(EnrollmentRecord.id)).where(EnrollmentRecord.organization_id==tenant.organization_id,EnrollmentRecord.student_id==p.user_id)) or 0)
        orders=list(db.scalars(select(SchoolOrderRecord).where(SchoolOrderRecord.organization_id==tenant.organization_id,SchoolOrderRecord.student_user_id==p.user_id)).all())
        paid=sum(x.paid_cents for x in orders);outstanding=sum(max(0,x.final_price_cents-x.paid_cents) for x in orders if x.status not in {"cancelled","failed"})
        out.append(StudentManagementRead(user_id=u.id,full_name=u.full_name,email=u.email,student_code=p.student_code,access_status=p.access_status,access_suspended_reason=p.access_suspended_reason,session_count=sessions,paid_cents=paid,outstanding_cents=outstanding))
    return out

def dashboard(db:Session,tenant:TenantContext)->CommercialDashboardRead:
    require_manager(tenant);orders=list(db.scalars(select(SchoolOrderRecord).where(SchoolOrderRecord.organization_id==tenant.organization_id)).all());profiles=int(db.scalar(select(func.count(OrganizationStudentProfileRecord.id)).where(OrganizationStudentProfileRecord.organization_id==tenant.organization_id)) or 0)
    paid=sum(x.paid_cents for x in orders);pending=sum(max(0,x.final_price_cents-x.paid_cents) for x in orders if x.status not in {"cancelled","failed"})
    overdue=sum(x.amount_cents for x in db.scalars(select(PaymentInstallmentRecord).where(PaymentInstallmentRecord.organization_id==tenant.organization_id,PaymentInstallmentRecord.status=="late")).all())
    currency=orders[0].currency if orders else "XAF"
    return CommercialDashboardRead(paid_revenue_cents=paid,pending_revenue_cents=pending,overdue_cents=overdue,order_count=len(orders),student_count=profiles,currency=currency)


def admin_catalog(db:Session,tenant:TenantContext)->list[PublicFormationRead]:
    require_manager(tenant)
    rows=list(db.scalars(select(FormationRecord).where(FormationRecord.organization_id==tenant.organization_id,FormationRecord.status!="archived").order_by(FormationRecord.created_at.desc())).all())
    return [_public_formation(db,x) for x in rows]


def student_orders(db: Session, tenant: TenantContext) -> list[OrderRead]:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")
    rows = list(
        db.scalars(
            select(SchoolOrderRecord)
            .where(
                SchoolOrderRecord.organization_id == tenant.organization_id,
                SchoolOrderRecord.student_user_id == tenant.user.id,
            )
            .order_by(SchoolOrderRecord.created_at.desc())
        ).all()
    )
    return [order_read(db, row) for row in rows]


def student_order_checkout(
    db: Session,
    tenant: TenantContext,
    order_id: int,
) -> PaymentCheckoutRead:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")
    school = db.get(OrganizationRecord, tenant.organization_id)
    return checkout_payment(db, school.slug, tenant.user, order_id)
