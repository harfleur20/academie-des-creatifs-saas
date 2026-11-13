from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


DiscountType = Literal["percentage", "fixed"]
PaymentMode = Literal["full", "installments"]


class PublicSiteConfigPayload(BaseModel):
    site_name: str = Field(default="", max_length=180)
    tagline: str = Field(default="", max_length=300)
    seo_description: str = Field(default="", max_length=500)
    logo_url: str | None = Field(default=None, max_length=1024)
    favicon_url: str | None = Field(default=None, max_length=1024)
    primary_color: str = Field(default="#1F2559", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(default="#18A7A3", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#131735", pattern=r"^#[0-9A-Fa-f]{6}$")
    font_heading: str = Field(default="Inter", max_length=80)
    font_body: str = Field(default="Inter", max_length=80)
    font_size_scale: int = Field(default=100, ge=85, le=125)
    heading_size_scale: int = Field(default=100, ge=85, le=125)
    subtitle_size_scale: int = Field(default=100, ge=85, le=125)
    hero_title: str = Field(default="", max_length=255)
    hero_subtitle: str = Field(default="", max_length=5000)
    hero_cta_label: str = Field(default="Découvrir nos formations", max_length=120)
    hero_image_url: str | None = Field(default=None, max_length=1024)
    announcement_enabled: bool = False
    announcement_text: str = Field(default="", max_length=600)
    announcement_background_color: str = Field(default="#FFF4E7", pattern=r"^#[0-9A-Fa-f]{6}$")
    announcement_text_color: str = Field(default="#7C4200", pattern=r"^#[0-9A-Fa-f]{6}$")
    about_title: str = Field(default="À propos", max_length=255)
    about_text: str = Field(default="", max_length=10000)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    contact_address: str | None = Field(default=None, max_length=500)
    social_links: dict[str, str] = Field(default_factory=dict)
    footer_text: str = Field(default="", max_length=5000)
    legal_notice: str = Field(default="", max_length=30000)
    sales_terms: str = Field(default="", max_length=30000)
    privacy_policy: str = Field(default="", max_length=30000)
    refund_policy: str = Field(default="", max_length=30000)
    student_code_prefix: str = Field(default="", max_length=8, pattern=r"^[A-Za-z0-9]*$")
    student_code_prefix_confirmed: bool = False
    is_published: bool = False


class LegalProfilePayload(BaseModel):
    legal_name: str = Field(default="", max_length=255)
    legal_address: str = Field(default="", max_length=500)
    registration_number: str = Field(default="", max_length=120)
    tax_number: str = Field(default="", max_length=120)
    invoice_email: EmailStr | None = None
    invoice_phone: str | None = Field(default=None, max_length=40)
    default_currency: str = Field(default="XAF", min_length=3, max_length=3)
    invoice_footer: str = Field(default="", max_length=5000)


class CommunicationProfilePayload(BaseModel):
    sender_name: str = Field(default="", max_length=180)
    reply_to_email: EmailStr | None = None
    email_signature: str = Field(default="", max_length=5000)
    whatsapp_signature: str = Field(default="", max_length=500)
    whatsapp_phone: str | None = Field(default=None, max_length=40)


class CertificationProfilePayload(BaseModel):
    signer_name: str = Field(default="", max_length=180)
    signer_title: str = Field(default="", max_length=180)
    signature_url: str | None = Field(default=None, max_length=1024)
    stamp_url: str | None = Field(default=None, max_length=1024)
    certificate_footer: str = Field(default="", max_length=5000)


class SchoolIdentityPayload(BaseModel):
    public_site: PublicSiteConfigPayload
    legal: LegalProfilePayload
    communications: CommunicationProfilePayload
    certification: CertificationProfilePayload


class SchoolIdentityRead(SchoolIdentityPayload):
    organization_id: int
    organization_name: str
    slug: str
    subdomain: str | None


class PublicSchoolRead(BaseModel):
    organization_id: int
    slug: str
    subdomain: str | None
    name: str
    site_name: str
    tagline: str
    seo_description: str
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_heading: str
    font_body: str
    font_size_scale: int
    heading_size_scale: int = 100
    subtitle_size_scale: int = 100
    hero_title: str
    hero_subtitle: str
    hero_cta_label: str
    hero_image_url: str | None
    announcement_enabled: bool
    announcement_text: str
    announcement_background_color: str
    announcement_text_color: str
    about_title: str
    about_text: str
    contact_phone: str | None
    contact_email: str | None
    contact_address: str | None
    social_links: dict[str, str]
    footer_text: str
    legal_notice: str
    sales_terms: str
    privacy_policy: str
    refund_policy: str
    # Business plans hide the platform's "Powered by" signature.
    white_label: bool = False
    # The read-only demonstration school: its site shows everything but takes no order.
    is_demo: bool = False


class PublicSessionRead(BaseModel):
    id: int
    label: str
    start_date: date
    end_date: date
    campus_label: str | None
    seat_capacity: int
    seats_remaining: int | None
    enrollment_open_at: datetime | None
    enrollment_close_at: datetime | None
    price_cents: int
    currency: str
    current_price_cents: int
    promotion_label: str | None
    promotion_discount_cents: int
    can_purchase: bool
    unavailable_reason: str | None


class PublicFormationCardRead(BaseModel):
    id: int
    slug: str
    title: str
    short_description: str
    cover_image_url: str | None
    category: str
    level: str
    format_type: str
    training_hours: int | None
    price_cents: int
    currency: str
    current_price_cents: int
    promotion_label: str | None
    promotion_discount_cents: int
    is_featured: bool
    featured_order: int
    available_session_count: int
    next_session: PublicSessionRead | None
    can_purchase: bool


class PublicProgramModuleRead(BaseModel):
    title: str
    chapters: list[str]


class PublicFormationDetailRead(PublicFormationCardRead):
    description: str
    presentation_video_url: str | None = None
    objectives: str
    prerequisites: str
    public_program: str
    allow_installments: bool
    installment_count: int
    reservation_deposit_percent: float | None = None
    modules: list[PublicProgramModuleRead]
    sessions: list[PublicSessionRead]
    teacher_names: list[str]


class PublicHomeRead(BaseModel):
    school: PublicSchoolRead
    featured_formations: list[PublicFormationCardRead]


class PromotionCreate(BaseModel):
    name: str = Field(default="%Promo", min_length=2, max_length=180)
    formation_id: int | None = Field(default=None, gt=0)
    session_id: int | None = Field(default=None, gt=0)
    discount_type: DiscountType
    discount_value: int = Field(gt=0)
    starts_at: datetime
    ends_at: datetime
    max_uses: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_discount(self):
        self.name = "%Promo"
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Une remise en pourcentage ne peut pas dépasser 100%.")
        if (self.formation_id is None) == (self.session_id is None):
            raise ValueError("La promotion doit cibler soit une formation, soit une session, mais pas les deux.")
        if self.ends_at <= self.starts_at:
            raise ValueError("La fin de la promotion doit suivre son début.")
        return self


class PromotionRead(BaseModel):
    id: int
    name: str
    formation_id: int | None
    session_id: int | None
    discount_type: DiscountType
    discount_value: int
    starts_at: datetime | None
    ends_at: datetime | None
    max_uses: int | None
    uses_count: int
    is_active: bool
    created_at: datetime


class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(default="", max_length=180)
    discount_type: DiscountType
    discount_value: int = Field(gt=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_uses: int | None = Field(default=None, gt=0)
    max_uses_per_customer: int = Field(default=1, ge=1, le=100)
    minimum_order_cents: int = Field(default=0, ge=0)
    eligible_formation_ids: list[int] = Field(default_factory=list)
    eligible_session_ids: list[int] = Field(default_factory=list)
    allow_on_promotions: bool = False
    is_active: bool = True

    @model_validator(mode="after")
    def validate_coupon(self):
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Une remise en pourcentage ne peut pas dépasser 100%.")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("La date de fin doit suivre la date de début.")
        return self


class CouponRead(CouponCreate):
    id: int
    uses_count: int
    created_at: datetime


class PricePreviewRequest(BaseModel):
    session_id: int = Field(gt=0)
    coupon_code: str | None = Field(default=None, max_length=64)


class PricePreviewRead(BaseModel):
    base_price_cents: int
    promotion_discount_cents: int
    coupon_discount_cents: int
    total_discount_cents: int
    final_price_cents: int
    currency: str
    promotion_label: str | None
    coupon_code: str | None
    installments_allowed: bool
    installment_count: int
    # Set when the live session is reserved with a non-refundable deposit, as on the mother site.
    deposit_cents: int | None = None
    deposit_percent: float | None = None
    balance_cents: int | None = None
    balance_due_date: date | None = None


class CheckoutCreate(BaseModel):
    session_id: int = Field(gt=0)
    payment_mode: PaymentMode = "full"
    coupon_code: str | None = Field(default=None, max_length=64)
    accept_deposit_terms: bool = False


class CheckoutRead(BaseModel):
    order_id: int
    order_number: str
    status: str
    access_status: str
    formation_id: int
    formation_title: str
    session_id: int
    session_label: str
    base_price_cents: int
    discount_amount_cents: int
    final_price_cents: int
    paid_cents: int
    currency: str
    payment_mode: str
    installment_count: int
    deposit_cents: int | None = None
    checkout_url: str | None
    provider_reference: str | None


class InstallmentRead(BaseModel):
    id: int
    order_id: int
    sequence: int
    amount_cents: int
    due_at: datetime
    grace_until: datetime
    status: str
    provider_reference: str | None
    checkout_url: str | None
    paid_at: datetime | None


class OrderRead(CheckoutRead):
    student_name: str
    student_email: str
    student_code: str | None
    coupon_code: str | None
    created_at: datetime
    paid_at: datetime | None
    installments: list[InstallmentRead]


class InvoiceRead(BaseModel):
    id: int
    order_id: int
    installment_id: int | None
    invoice_number: str
    status: str
    amount_cents: int
    currency: str
    branding_snapshot: dict
    issued_at: datetime
    paid_at: datetime | None


class CurrencyTotalsRead(BaseModel):
    currency: str
    gross_sales_cents: int
    collected_cents: int
    outstanding_cents: int


class StudentManagementRead(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: str | None
    avatar_url: str | None
    student_code: str
    status: str
    active_enrollments: int
    completed_enrollments: int
    totals_by_currency: list[CurrencyTotalsRead]
    last_purchase_at: datetime | None


class CommercialDashboardRead(BaseModel):
    order_count: int
    paid_order_count: int
    totals_by_currency: list[CurrencyTotalsRead]
    late_installments: int
    active_students: int


class CommunicationOutboxRead(BaseModel):
    id: int
    channel: str
    recipient: str
    event_key: str
    subject: str | None
    body: str
    status: str
    created_at: datetime