from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator

DiscountType = Literal["percentage", "fixed"]
PaymentPlan = Literal["full", "installments"]

class PublicSiteUpdate(BaseModel):
    hero_title: str = Field(default="", max_length=255)
    hero_subtitle: str = Field(default="", max_length=500)
    hero_image_url: str | None = Field(default=None, max_length=1024)
    hero_button_label: str = Field(default="Découvrir nos formations", max_length=80)
    about_title: str = Field(default="À propos", max_length=255)
    about_text: str = Field(default="", max_length=10000)
    about_image_url: str | None = Field(default=None, max_length=1024)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: str | None = Field(default=None, max_length=180)
    contact_address: str | None = Field(default=None, max_length=500)
    social_links: dict[str, str] = Field(default_factory=dict)
    footer_text: str = Field(default="", max_length=5000)
    legal_notice: str = Field(default="", max_length=30000)
    terms_of_sale: str = Field(default="", max_length=30000)
    privacy_policy: str = Field(default="", max_length=30000)
    refund_policy: str = Field(default="", max_length=30000)
    legal_name: str | None = Field(default=None, max_length=255)
    legal_registration_number: str | None = Field(default=None, max_length=120)
    tax_number: str | None = Field(default=None, max_length=120)
    billing_address: str | None = Field(default=None, max_length=500)
    sender_name: str | None = Field(default=None, max_length=180)
    reply_to_email: str | None = Field(default=None, max_length=180)
    certificate_signatory_name: str | None = Field(default=None, max_length=180)
    certificate_signatory_title: str | None = Field(default=None, max_length=180)
    certificate_signature_url: str | None = Field(default=None, max_length=1024)
    certificate_stamp_url: str | None = Field(default=None, max_length=1024)
    student_code_prefix: str | None = Field(default=None, min_length=2, max_length=8)

class PublicSiteAdminRead(PublicSiteUpdate):
    organization_id: int
    school_name: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str

class PublicSessionRead(BaseModel):
    id: int
    label: str
    start_date: date
    end_date: date
    campus_label: str | None
    seats_remaining: int | None
    price_cents: int
    currency: str
    is_available: bool
    unavailable_reason: str | None

class PublicFormationRead(BaseModel):
    id: int
    slug: str
    title: str
    short_description: str
    description: str
    cover_url: str | None
    category: str
    level: str
    format_type: str
    training_hours: int | None
    objectives: str
    prerequisites: str
    public_program: str
    base_price_cents: int
    currency: str
    display_price_cents: int
    direct_discount_cents: int
    featured_on_home: bool
    sessions: list[PublicSessionRead]
    can_buy: bool

class PublicSchoolRead(BaseModel):
    organization_id: int
    slug: str
    name: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    site: PublicSiteAdminRead
    featured_formations: list[PublicFormationRead]

class PublicCatalogRead(BaseModel):
    school: PublicSchoolRead
    formations: list[PublicFormationRead]

class CommercialFormationUpdate(BaseModel):
    short_description: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=1024)
    objectives: str | None = Field(default=None, max_length=10000)
    prerequisites: str | None = Field(default=None, max_length=10000)
    public_program: str | None = Field(default=None, max_length=20000)
    base_price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    allow_installments: bool | None = None
    installment_count: int | None = Field(default=None, ge=1, le=12)
    installment_grace_days: int | None = Field(default=None, ge=0, le=30)
    is_public: bool | None = None
    featured_on_home: bool | None = None
    featured_order: int | None = Field(default=None, ge=0, le=1000)

class CommercialSessionUpdate(BaseModel):
    enrollment_opens_at: datetime | None = None
    enrollment_closes_at: datetime | None = None
    public_enrollment_enabled: bool | None = None
    price_override_cents: int | None = Field(default=None, ge=0)

class PromotionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    formation_id: int | None = None
    session_id: int | None = None
    discount_type: DiscountType
    discount_value: int = Field(gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    is_active: bool = True

class PromotionRead(PromotionCreate):
    id: int
    used_count: int
    created_at: datetime

class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    discount_type: DiscountType
    discount_value: int = Field(gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_uses: int | None = Field(default=None, ge=1)
    max_uses_per_customer: int = Field(default=1, ge=1, le=100)
    minimum_order_cents: int = Field(default=0, ge=0)
    formation_id: int | None = None
    session_id: int | None = None
    allow_on_promotions: bool = False
    is_active: bool = True

class PromoCodeRead(PromoCodeCreate):
    id: int
    used_count: int
    created_at: datetime

class PromoQuotePayload(BaseModel):
    session_id: int
    promo_code: str | None = Field(default=None, max_length=40)

class PriceQuoteRead(BaseModel):
    formation_id: int
    session_id: int
    currency: str
    base_price_cents: int
    direct_discount_cents: int
    promo_code: str | None
    promo_code_discount_cents: int
    final_price_cents: int
    installment_count: int
    allow_installments: bool

class OrderCreate(BaseModel):
    session_id: int
    promo_code: str | None = Field(default=None, max_length=40)
    payment_plan: PaymentPlan = "full"

class InstallmentRead(BaseModel):
    id: int
    installment_number: int
    amount_cents: int
    due_at: datetime
    grace_until: datetime | None
    status: str
    paid_at: datetime | None

class OrderRead(BaseModel):
    id: int
    order_reference: str
    school_name: str
    student_name: str
    formation_title: str
    session_label: str
    status: str
    currency: str
    base_price_cents: int
    direct_discount_cents: int
    promo_code: str | None
    promo_code_discount_cents: int
    final_price_cents: int
    payment_plan: str
    installment_count: int
    paid_cents: int
    student_code: str | None
    access_status: str | None
    installments: list[InstallmentRead]
    created_at: datetime

class PaymentCheckoutRead(BaseModel):
    payment_id: int
    provider: str
    amount_cents: int
    currency: str
    status: str
    checkout_url: str | None

class DemoPaymentConfirmRead(BaseModel):
    order: OrderRead
    payment: PaymentCheckoutRead

class StudentManagementRead(BaseModel):
    user_id: int
    full_name: str
    email: str
    student_code: str
    access_status: str
    access_suspended_reason: str | None
    session_count: int
    paid_cents: int
    outstanding_cents: int

class CommercialDashboardRead(BaseModel):
    paid_revenue_cents: int
    pending_revenue_cents: int
    overdue_cents: int
    order_count: int
    student_count: int
    currency: str
