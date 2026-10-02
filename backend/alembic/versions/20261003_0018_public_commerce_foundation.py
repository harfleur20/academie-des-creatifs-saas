"""public school commerce foundation

Revision ID: 20261003_0018
Revises: 20261002_0017
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision="20261003_0018"
down_revision="20261002_0017"
branch_labels: Sequence[str] | None=None
depends_on: Sequence[str] | None=None

def upgrade():
    for name,column in [
        ("short_description",sa.Column("short_description",sa.String(500),nullable=False,server_default="")),
        ("cover_image_url",sa.Column("cover_image_url",sa.String(1024),nullable=True)),
        ("objectives",sa.Column("objectives",sa.Text(),nullable=False,server_default="")),
        ("prerequisites",sa.Column("prerequisites",sa.Text(),nullable=False,server_default="")),
        ("public_program",sa.Column("public_program",sa.Text(),nullable=False,server_default="")),
        ("price_cents",sa.Column("price_cents",sa.Integer(),nullable=False,server_default="0")),
        ("currency",sa.Column("currency",sa.String(3),nullable=False,server_default="XAF")),
        ("allow_installments",sa.Column("allow_installments",sa.Boolean(),nullable=False,server_default=sa.false())),
        ("installment_count",sa.Column("installment_count",sa.Integer(),nullable=False,server_default="3")),
        ("is_featured",sa.Column("is_featured",sa.Boolean(),nullable=False,server_default=sa.false())),
        ("featured_order",sa.Column("featured_order",sa.Integer(),nullable=False,server_default="0")),
    ]: op.add_column("formations",column)
    op.add_column("formation_sessions",sa.Column("enrollment_open_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("formation_sessions",sa.Column("enrollment_close_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("formation_sessions",sa.Column("price_override_cents",sa.Integer(),nullable=True))

    op.create_table("organization_public_sites",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("site_name",sa.String(180),nullable=False,server_default=""),sa.Column("tagline",sa.String(300),nullable=False,server_default=""),sa.Column("seo_description",sa.String(500),nullable=False,server_default=""),
      sa.Column("favicon_url",sa.String(1024)),sa.Column("hero_title",sa.String(255),nullable=False,server_default=""),sa.Column("hero_subtitle",sa.Text(),nullable=False,server_default=""),
      sa.Column("hero_cta_label",sa.String(120),nullable=False,server_default="Découvrir nos formations"),sa.Column("hero_image_url",sa.String(1024)),
      sa.Column("about_title",sa.String(255),nullable=False,server_default="À propos"),sa.Column("about_text",sa.Text(),nullable=False,server_default=""),
      sa.Column("contact_phone",sa.String(40)),sa.Column("contact_email",sa.String(180)),sa.Column("contact_address",sa.String(500)),
      sa.Column("social_links",sa.JSON(),nullable=False),sa.Column("footer_text",sa.Text(),nullable=False,server_default=""),sa.Column("legal_notice",sa.Text(),nullable=False,server_default=""),
      sa.Column("sales_terms",sa.Text(),nullable=False,server_default=""),sa.Column("privacy_policy",sa.Text(),nullable=False,server_default=""),sa.Column("refund_policy",sa.Text(),nullable=False,server_default=""),
      sa.Column("font_heading",sa.String(80),nullable=False,server_default="Inter"),sa.Column("font_body",sa.String(80),nullable=False,server_default="Inter"),
      sa.Column("student_code_prefix",sa.String(8),nullable=False,server_default=""),sa.Column("is_published",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("organization_id",name="uq_public_site_organization"))
    op.create_index("ix_organization_public_sites_organization_id","organization_public_sites",["organization_id"])

    op.create_table("organization_legal_profiles",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("legal_name",sa.String(255),nullable=False,server_default=""),sa.Column("legal_address",sa.String(500),nullable=False,server_default=""),
      sa.Column("registration_number",sa.String(120),nullable=False,server_default=""),sa.Column("tax_number",sa.String(120),nullable=False,server_default=""),
      sa.Column("invoice_email",sa.String(180)),sa.Column("invoice_phone",sa.String(40)),sa.Column("default_currency",sa.String(3),nullable=False,server_default="XAF"),sa.Column("invoice_footer",sa.Text(),nullable=False,server_default=""),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("organization_id",name="uq_legal_profile_organization"))
    op.create_index("ix_organization_legal_profiles_organization_id","organization_legal_profiles",["organization_id"])

    op.create_table("organization_communication_profiles",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("sender_name",sa.String(180),nullable=False,server_default=""),sa.Column("reply_to_email",sa.String(180)),sa.Column("email_signature",sa.Text(),nullable=False,server_default=""),
      sa.Column("whatsapp_signature",sa.String(500),nullable=False,server_default=""),sa.Column("whatsapp_phone",sa.String(40)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("organization_id",name="uq_communication_profile_organization"))
    op.create_index("ix_organization_communication_profiles_organization_id","organization_communication_profiles",["organization_id"])

    op.create_table("organization_certification_profiles",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("signer_name",sa.String(180),nullable=False,server_default=""),sa.Column("signer_title",sa.String(180),nullable=False,server_default=""),
      sa.Column("signature_url",sa.String(1024)),sa.Column("stamp_url",sa.String(1024)),sa.Column("certificate_footer",sa.Text(),nullable=False,server_default=""),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("organization_id",name="uq_certification_profile_organization"))
    op.create_index("ix_organization_certification_profiles_organization_id","organization_certification_profiles",["organization_id"])

    op.create_table("organization_student_profiles",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("student_code",sa.String(40),nullable=False),
      sa.Column("status",sa.String(24),nullable=False,server_default="active"),sa.Column("first_purchase_at",sa.DateTime(timezone=True)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("organization_id","user_id",name="uq_student_profile_org_user"),sa.UniqueConstraint("organization_id","student_code",name="uq_student_profile_org_code"))
    for n in ("organization_id","user_id","student_code"): op.create_index(f"ix_organization_student_profiles_{n}","organization_student_profiles",[n])
    op.create_index("ix_student_profiles_org_status","organization_student_profiles",["organization_id","status"])

    op.create_table("promotions",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("name",sa.String(180),nullable=False),sa.Column("formation_id",sa.Integer(),sa.ForeignKey("formations.id",ondelete="CASCADE")),sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE")),
      sa.Column("discount_type",sa.String(24),nullable=False),sa.Column("discount_value",sa.Integer(),nullable=False),sa.Column("starts_at",sa.DateTime(timezone=True)),sa.Column("ends_at",sa.DateTime(timezone=True)),
      sa.Column("max_uses",sa.Integer()),sa.Column("uses_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","formation_id","session_id"): op.create_index(f"ix_promotions_{n}","promotions",[n])
    op.create_index("ix_promotions_org_active_dates","promotions",["organization_id","is_active","starts_at","ends_at"])

    op.create_table("coupons",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("code",sa.String(64),nullable=False),sa.Column("name",sa.String(180),nullable=False,server_default=""),sa.Column("discount_type",sa.String(24),nullable=False),sa.Column("discount_value",sa.Integer(),nullable=False),
      sa.Column("valid_from",sa.DateTime(timezone=True)),sa.Column("valid_until",sa.DateTime(timezone=True)),sa.Column("max_uses",sa.Integer()),sa.Column("max_uses_per_customer",sa.Integer(),nullable=False,server_default="1"),
      sa.Column("uses_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("minimum_order_cents",sa.Integer(),nullable=False,server_default="0"),
      sa.Column("eligible_formation_ids",sa.JSON(),nullable=False),sa.Column("eligible_session_ids",sa.JSON(),nullable=False),sa.Column("allow_on_promotions",sa.Boolean(),nullable=False,server_default=sa.false()),
      sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("organization_id","code",name="uq_coupons_org_code"))
    for n in ("organization_id","code"): op.create_index(f"ix_coupons_{n}","coupons",[n])
    op.create_index("ix_coupons_org_active","coupons",["organization_id","is_active"])

    op.create_table("student_orders",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("order_number",sa.String(80),nullable=False),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("formation_id",sa.Integer(),sa.ForeignKey("formations.id",ondelete="RESTRICT"),nullable=False),sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="RESTRICT"),nullable=False),
      sa.Column("status",sa.String(24),nullable=False,server_default="pending"),sa.Column("access_status",sa.String(32),nullable=False,server_default="pending"),
      sa.Column("base_price_cents",sa.Integer(),nullable=False),sa.Column("discount_amount_cents",sa.Integer(),nullable=False,server_default="0"),sa.Column("final_price_cents",sa.Integer(),nullable=False),
      sa.Column("paid_cents",sa.Integer(),nullable=False,server_default="0"),sa.Column("currency",sa.String(3),nullable=False,server_default="XAF"),sa.Column("discount_source",sa.String(32)),
      sa.Column("promotion_id",sa.Integer(),sa.ForeignKey("promotions.id",ondelete="SET NULL")),sa.Column("coupon_id",sa.Integer(),sa.ForeignKey("coupons.id",ondelete="SET NULL")),sa.Column("coupon_code",sa.String(64)),
      sa.Column("payment_mode",sa.String(24),nullable=False,server_default="full"),sa.Column("installment_count",sa.Integer(),nullable=False,server_default="1"),
      sa.Column("payment_provider",sa.String(40),nullable=False,server_default="taramoney"),sa.Column("provider_reference",sa.String(180),unique=True),sa.Column("checkout_url",sa.Text()),
      sa.Column("branding_snapshot",sa.JSON(),nullable=False),sa.Column("paid_at",sa.DateTime(timezone=True)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("order_number",name="uq_student_orders_number"))
    for n in ("organization_id","order_number","user_id","formation_id","session_id","promotion_id","coupon_id","provider_reference"): op.create_index(f"ix_student_orders_{n}","student_orders",[n],unique=(n in {"order_number","provider_reference"}))
    op.create_index("ix_student_orders_org_user","student_orders",["organization_id","user_id"]);op.create_index("ix_student_orders_org_status","student_orders",["organization_id","status"])

    op.create_table("order_installments",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("order_id",sa.Integer(),sa.ForeignKey("student_orders.id",ondelete="CASCADE"),nullable=False),sa.Column("sequence",sa.Integer(),nullable=False),sa.Column("amount_cents",sa.Integer(),nullable=False),
      sa.Column("due_at",sa.DateTime(timezone=True),nullable=False),sa.Column("grace_until",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="pending"),
      sa.Column("provider_reference",sa.String(180),unique=True),sa.Column("checkout_url",sa.Text()),sa.Column("paid_at",sa.DateTime(timezone=True)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("order_id","sequence",name="uq_order_installments_order_sequence"))
    for n in ("organization_id","order_id","provider_reference"): op.create_index(f"ix_order_installments_{n}","order_installments",[n],unique=(n=="provider_reference"))
    op.create_index("ix_order_installments_org_status_due","order_installments",["organization_id","status","due_at"])

    op.create_table("order_invoices",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("order_id",sa.Integer(),sa.ForeignKey("student_orders.id",ondelete="CASCADE"),nullable=False),sa.Column("installment_id",sa.Integer(),sa.ForeignKey("order_installments.id",ondelete="SET NULL")),
      sa.Column("invoice_number",sa.String(80),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="paid"),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("currency",sa.String(3),nullable=False),
      sa.Column("branding_snapshot",sa.JSON(),nullable=False),sa.Column("issued_at",sa.DateTime(timezone=True),nullable=False),sa.Column("paid_at",sa.DateTime(timezone=True)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
      sa.UniqueConstraint("invoice_number",name="uq_order_invoices_number"))
    for n in ("organization_id","order_id","installment_id","invoice_number"): op.create_index(f"ix_order_invoices_{n}","order_invoices",[n],unique=(n=="invoice_number"))
    op.create_index("ix_order_invoices_org_order","order_invoices",["organization_id","order_id"])

    op.create_table("communication_outbox",
      sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
      sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("channel",sa.String(24),nullable=False),sa.Column("recipient",sa.String(255),nullable=False),
      sa.Column("event_key",sa.String(120),nullable=False),sa.Column("subject",sa.String(255)),sa.Column("body",sa.Text(),nullable=False),sa.Column("branding_snapshot",sa.JSON(),nullable=False),
      sa.Column("status",sa.String(24),nullable=False,server_default="pending"),sa.Column("sent_at",sa.DateTime(timezone=True)),
      sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","user_id"): op.create_index(f"ix_communication_outbox_{n}","communication_outbox",[n])
    op.create_index("ix_communication_outbox_org_status","communication_outbox",["organization_id","status"])

def downgrade():
    for table in ("communication_outbox","order_invoices","order_installments","student_orders","coupons","promotions","organization_student_profiles","organization_certification_profiles","organization_communication_profiles","organization_legal_profiles","organization_public_sites"):
        op.drop_table(table)
    for col in ("price_override_cents","enrollment_close_at","enrollment_open_at"): op.drop_column("formation_sessions",col)
    for col in ("featured_order","is_featured","installment_count","allow_installments","currency","price_cents","public_program","prerequisites","objectives","cover_image_url","short_description"): op.drop_column("formations",col)
