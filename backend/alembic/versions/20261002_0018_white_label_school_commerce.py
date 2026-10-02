"""white label school commerce

Revision ID: 20261002_0018
Revises: 20261002_0017
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision="20261002_0018"
down_revision="20261002_0017"
branch_labels: Sequence[str] | None=None
depends_on: Sequence[str] | None=None

def upgrade() -> None:
    for column in [
        sa.Column("short_description",sa.String(500),nullable=False,server_default=""),
        sa.Column("cover_url",sa.String(1024)),
        sa.Column("objectives",sa.Text(),nullable=False,server_default=""),
        sa.Column("prerequisites",sa.Text(),nullable=False,server_default=""),
        sa.Column("public_program",sa.Text(),nullable=False,server_default=""),
        sa.Column("base_price_cents",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("currency",sa.String(3),nullable=False,server_default="XAF"),
        sa.Column("allow_installments",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("installment_count",sa.Integer(),nullable=False,server_default="1"),
        sa.Column("installment_grace_days",sa.Integer(),nullable=False,server_default="3"),
        sa.Column("is_public",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("featured_on_home",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("featured_order",sa.Integer(),nullable=False,server_default="0"),
    ]: op.add_column("formations",column)
    op.create_index("ix_formations_is_public","formations",["is_public"])
    op.create_index("ix_formations_featured_on_home","formations",["featured_on_home"])

    for column in [
        sa.Column("enrollment_opens_at",sa.DateTime(timezone=True)),
        sa.Column("enrollment_closes_at",sa.DateTime(timezone=True)),
        sa.Column("public_enrollment_enabled",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("price_override_cents",sa.Integer()),
    ]: op.add_column("formation_sessions",column)

    op.create_table("organization_public_sites",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("hero_title",sa.String(255),nullable=False,server_default=""),
        sa.Column("hero_subtitle",sa.String(500),nullable=False,server_default=""),
        sa.Column("hero_image_url",sa.String(1024)),
        sa.Column("hero_button_label",sa.String(80),nullable=False,server_default="Découvrir nos formations"),
        sa.Column("about_title",sa.String(255),nullable=False,server_default="À propos"),
        sa.Column("about_text",sa.Text(),nullable=False,server_default=""),
        sa.Column("about_image_url",sa.String(1024)),
        sa.Column("contact_phone",sa.String(40)),sa.Column("contact_email",sa.String(180)),sa.Column("contact_address",sa.String(500)),
        sa.Column("social_links",sa.JSON(),nullable=False,server_default="{}"),
        sa.Column("footer_text",sa.Text(),nullable=False,server_default=""),
        sa.Column("legal_notice",sa.Text(),nullable=False,server_default=""),sa.Column("terms_of_sale",sa.Text(),nullable=False,server_default=""),
        sa.Column("privacy_policy",sa.Text(),nullable=False,server_default=""),sa.Column("refund_policy",sa.Text(),nullable=False,server_default=""),
        sa.Column("legal_name",sa.String(255)),sa.Column("legal_registration_number",sa.String(120)),sa.Column("tax_number",sa.String(120)),sa.Column("billing_address",sa.String(500)),
        sa.Column("sender_name",sa.String(180)),sa.Column("reply_to_email",sa.String(180)),
        sa.Column("certificate_signatory_name",sa.String(180)),sa.Column("certificate_signatory_title",sa.String(180)),sa.Column("certificate_signature_url",sa.String(1024)),sa.Column("certificate_stamp_url",sa.String(1024)),
        sa.Column("student_code_prefix",sa.String(8)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("organization_id",name="uq_org_public_site"))
    op.create_index("ix_organization_public_sites_organization_id","organization_public_sites",["organization_id"])

    op.create_table("organization_student_profiles",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("student_code",sa.String(32),nullable=False),
        sa.Column("code_year",sa.Integer(),nullable=False),sa.Column("code_sequence",sa.Integer(),nullable=False),
        sa.Column("access_status",sa.String(24),nullable=False,server_default="active"),sa.Column("access_suspended_reason",sa.String(500)),sa.Column("access_suspended_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("organization_id","user_id",name="uq_org_student_profile_user"),sa.UniqueConstraint("organization_id","student_code",name="uq_org_student_code"))
    op.create_index("ix_organization_student_profiles_organization_id","organization_student_profiles",["organization_id"])
    op.create_index("ix_organization_student_profiles_user_id","organization_student_profiles",["user_id"])
    op.create_index("ix_org_student_profiles_code","organization_student_profiles",["organization_id","student_code"])

    op.create_table("promotions",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("name",sa.String(180),nullable=False),sa.Column("formation_id",sa.Integer(),sa.ForeignKey("formations.id",ondelete="CASCADE")),sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE")),
        sa.Column("discount_type",sa.String(24),nullable=False),sa.Column("discount_value",sa.Integer(),nullable=False),sa.Column("starts_at",sa.DateTime(timezone=True)),sa.Column("ends_at",sa.DateTime(timezone=True)),
        sa.Column("max_uses",sa.Integer()),sa.Column("used_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for n in ("organization_id","formation_id","session_id"): op.create_index(f"ix_promotions_{n}","promotions",[n])
    op.create_index("ix_promotions_org_active_dates","promotions",["organization_id","is_active","starts_at","ends_at"])

    op.create_table("promo_codes",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("code",sa.String(40),nullable=False),sa.Column("discount_type",sa.String(24),nullable=False),sa.Column("discount_value",sa.Integer(),nullable=False),
        sa.Column("starts_at",sa.DateTime(timezone=True)),sa.Column("ends_at",sa.DateTime(timezone=True)),sa.Column("max_uses",sa.Integer()),sa.Column("max_uses_per_customer",sa.Integer(),nullable=False,server_default="1"),
        sa.Column("minimum_order_cents",sa.Integer(),nullable=False,server_default="0"),sa.Column("formation_id",sa.Integer(),sa.ForeignKey("formations.id",ondelete="CASCADE")),sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="CASCADE")),
        sa.Column("allow_on_promotions",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("used_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("organization_id","code",name="uq_promo_codes_org_code"))
    for n in ("organization_id","formation_id","session_id"): op.create_index(f"ix_promo_codes_{n}","promo_codes",[n])
    op.create_index("ix_promo_codes_org_active","promo_codes",["organization_id","is_active"])

    op.create_table("school_orders",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("order_reference",sa.String(80),nullable=False),sa.Column("student_user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("formation_id",sa.Integer(),sa.ForeignKey("formations.id",ondelete="RESTRICT"),nullable=False),sa.Column("session_id",sa.Integer(),sa.ForeignKey("formation_sessions.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("status",sa.String(24),nullable=False,server_default="pending"),sa.Column("currency",sa.String(3),nullable=False,server_default="XAF"),
        sa.Column("base_price_cents",sa.Integer(),nullable=False),sa.Column("direct_discount_cents",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("promo_code",sa.String(40)),sa.Column("promo_code_discount_cents",sa.Integer(),nullable=False,server_default="0"),sa.Column("final_price_cents",sa.Integer(),nullable=False),
        sa.Column("payment_plan",sa.String(24),nullable=False,server_default="full"),sa.Column("installment_count",sa.Integer(),nullable=False,server_default="1"),sa.Column("paid_cents",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("access_granted_at",sa.DateTime(timezone=True)),sa.Column("brand_snapshot",sa.JSON(),nullable=False,server_default="{}"),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("order_reference",name="uq_school_orders_reference"))
    for n in ("organization_id","student_user_id","formation_id","session_id"): op.create_index(f"ix_school_orders_{n}","school_orders",[n])
    op.create_index("ix_school_orders_org_status","school_orders",["organization_id","status"]);op.create_index("ix_school_orders_student","school_orders",["organization_id","student_user_id"])

    op.create_table("payment_installments",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("order_id",sa.Integer(),sa.ForeignKey("school_orders.id",ondelete="CASCADE"),nullable=False),sa.Column("installment_number",sa.Integer(),nullable=False),
        sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("due_at",sa.DateTime(timezone=True),nullable=False),sa.Column("grace_until",sa.DateTime(timezone=True)),
        sa.Column("status",sa.String(24),nullable=False,server_default="pending"),sa.Column("paid_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("order_id","installment_number",name="uq_payment_installment_order_number"))
    for n in ("organization_id","order_id"): op.create_index(f"ix_payment_installments_{n}","payment_installments",[n])
    op.create_index("ix_payment_installments_org_status_due","payment_installments",["organization_id","status","due_at"])

    op.create_table("school_payments",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("order_id",sa.Integer(),sa.ForeignKey("school_orders.id",ondelete="CASCADE"),nullable=False),sa.Column("installment_id",sa.Integer(),sa.ForeignKey("payment_installments.id",ondelete="SET NULL")),
        sa.Column("provider",sa.String(40),nullable=False,server_default="demo"),sa.Column("provider_reference",sa.String(180),nullable=False),sa.Column("provider_transaction_id",sa.String(180)),
        sa.Column("status",sa.String(24),nullable=False,server_default="pending"),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("currency",sa.String(3),nullable=False),
        sa.Column("checkout_url",sa.Text()),sa.Column("paid_at",sa.DateTime(timezone=True)),sa.Column("failure_reason",sa.String(500)),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("provider_reference",name="uq_school_payments_provider_reference"),sa.UniqueConstraint("provider_transaction_id",name="uq_school_payments_provider_transaction_id"))
    for n in ("organization_id","order_id","installment_id"): op.create_index(f"ix_school_payments_{n}","school_payments",[n])
    op.create_index("ix_school_payments_provider_reference","school_payments",["provider_reference"],unique=True);op.create_index("ix_school_payments_provider_transaction_id","school_payments",["provider_transaction_id"],unique=True)
    op.create_index("ix_school_payments_org_status","school_payments",["organization_id","status"])

    op.create_table("student_invoices",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("organization_id",sa.Integer(),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),
        sa.Column("order_id",sa.Integer(),sa.ForeignKey("school_orders.id",ondelete="RESTRICT"),nullable=False),sa.Column("payment_id",sa.Integer(),sa.ForeignKey("school_payments.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("invoice_number",sa.String(80),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="paid"),sa.Column("amount_cents",sa.Integer(),nullable=False),sa.Column("currency",sa.String(3),nullable=False),
        sa.Column("issued_at",sa.DateTime(timezone=True),nullable=False),sa.Column("paid_at",sa.DateTime(timezone=True)),sa.Column("brand_snapshot",sa.JSON(),nullable=False,server_default="{}"),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("invoice_number",name="uq_student_invoices_number"),sa.UniqueConstraint("payment_id",name="uq_student_invoices_payment"))
    for n in ("organization_id","order_id","payment_id"): op.create_index(f"ix_student_invoices_{n}","student_invoices",[n])
    op.create_index("ix_student_invoices_invoice_number","student_invoices",["invoice_number"],unique=True);op.create_index("ix_student_invoices_org_status","student_invoices",["organization_id","status"])

def downgrade() -> None:
    for table in ("student_invoices","school_payments","payment_installments","school_orders","promo_codes","promotions","organization_student_profiles","organization_public_sites"):
        op.drop_table(table)
    for name in ("price_override_cents","public_enrollment_enabled","enrollment_closes_at","enrollment_opens_at"):
        op.drop_column("formation_sessions",name)
    op.drop_index("ix_formations_featured_on_home",table_name="formations");op.drop_index("ix_formations_is_public",table_name="formations")
    for name in ("featured_order","featured_on_home","is_public","installment_grace_days","installment_count","allow_installments","currency","base_price_cents","public_program","prerequisites","objectives","cover_url","short_description"):
        op.drop_column("formations",name)
