"""The plans schools pay for, per-unit add-ons, and the platform's share of their sales.

- Plans get their FCFA prices, quotas and the commission taken on student payments
  (only plans still without a price, so a grid set by hand is kept).
- Add-ons: what a school pays per unit beyond its plan, plus the ones coming later.
- Invoices and payment attempts keep their lines (plan, then add-ons).
- Each school has a ledger of what it is owed, and asks for its payouts.

Revision ID: 20261112_0060
Revises: 20261112_0059
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20261112_0060"
down_revision = "20261112_0059"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

PLANS = {
    # code: (description, monthly, annual, commission in basis points, entitlements)
    "starter": (
        "Pour les formateurs et les petites écoles, en ligne et en présentiel.",
        15_000, 150_000, 800,
        [("students", True, 50), ("teachers", True, 2), ("active_formations", True, 3),
         ("live", False, None), ("custom_domain", False, None)],
    ),
    "pro": (
        "Pour les écoles qui donnent des cours en live, avec leur propre domaine.",
        35_000, 350_000, 500,
        [("students", True, 300), ("teachers", True, 10), ("active_formations", True, None),
         ("live", True, None), ("custom_domain", True, None)],
    ),
    "business": (
        "Pour les écoles avec plusieurs équipes et beaucoup d'étudiants.",
        75_000, 750_000, 300,
        [("students", True, None), ("teachers", True, None), ("active_formations", True, None),
         ("live", True, None), ("custom_domain", True, None), ("priority_support", True, None)],
    ),
}

ADDONS = [
    # code, name, description, feature_key, unit_label, price, status, plans, order
    ("extra_student", "Étudiant supplémentaire", "Chaque étudiant actif au-delà de votre forfait.",
     "students", "étudiant", 300, "active", ["starter", "pro"], 10),
    ("extra_teacher", "Professeur supplémentaire", "Chaque professeur au-delà de votre forfait.",
     "teachers", "professeur", 2_500, "active", ["starter", "pro"], 20),
    ("extra_formation", "Formation supplémentaire", "Chaque formation publiée au-delà de votre forfait.",
     "active_formations", "formation", 2_000, "active", ["starter"], 30),
    ("live_replays", "Replays des lives", "Les cours en live enregistrés et revus par vos étudiants.",
     None, "mois", None, "coming_soon", ["pro", "business"], 40),
    ("live_transcription", "Transcription des lives", "Le texte de chaque cours en live, consultable et cherchable.",
     None, "mois", None, "coming_soon", ["pro", "business"], 50),
]


def upgrade() -> None:
    with op.batch_alter_table("plans") as batch_op:
        batch_op.add_column(sa.Column("sales_commission_bps", sa.Integer(), nullable=False, server_default="800"))
    for table in ("billing_invoices", "billing_payment_attempts"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("lines", sa.JSON(), nullable=True))

    op.create_table(
        "addons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("feature_key", sa.String(120), nullable=True),
        sa.Column("unit_label", sa.String(40), nullable=False, server_default="unité"),
        sa.Column("unit_price_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="XAF"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("plan_codes", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "school_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("gross_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commission_bps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commission_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("student_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("installment_id", sa.Integer(), sa.ForeignKey("order_installments.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("description", sa.String(255), nullable=False, server_default=""),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "school_payouts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("method", sa.String(24), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("account_name", sa.String(180), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="requested"),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transfer_reference", sa.String(180), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    bind = op.get_bind()
    now = datetime.now(UTC)
    for code, (description, monthly, annual, commission, entitlements) in PLANS.items():
        # The commission column is new here: every plan of the grid gets its rate.
        bind.execute(sa.text("UPDATE plans SET sales_commission_bps = :commission WHERE code = :code"),
                     {"commission": commission, "code": code})
        plan = bind.execute(sa.text("SELECT id, monthly_price_cents FROM plans WHERE code = :code"), {"code": code}).first()
        if plan is None or plan.monthly_price_cents is not None:
            continue
        bind.execute(sa.text(
            "UPDATE plans SET description = :description, currency = 'XAF', monthly_price_cents = :monthly, "
            "annual_price_cents = :annual, sales_commission_bps = :commission, trial_days = 14, updated_at = :now "
            "WHERE id = :id"
        ), {"description": description, "monthly": monthly, "annual": annual, "commission": commission, "now": now, "id": plan.id})
        has_entitlements = bind.execute(sa.text("SELECT 1 FROM plan_entitlements WHERE plan_id = :id"), {"id": plan.id}).first()
        if has_entitlements is None:
            for feature_key, enabled, limit in entitlements:
                bind.execute(sa.text(
                    "INSERT INTO plan_entitlements (plan_id, feature_key, enabled, limit_value, created_at, updated_at) "
                    "VALUES (:plan_id, :feature_key, :enabled, :limit, :now, :now)"
                ), {"plan_id": plan.id, "feature_key": feature_key, "enabled": enabled, "limit": limit, "now": now})

    addons = sa.table(
        "addons",
        sa.column("code", sa.String), sa.column("name", sa.String), sa.column("description", sa.Text),
        sa.column("feature_key", sa.String), sa.column("unit_label", sa.String), sa.column("unit_price_cents", sa.Integer),
        sa.column("currency", sa.String), sa.column("status", sa.String), sa.column("plan_codes", sa.JSON),
        sa.column("sort_order", sa.Integer), sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(addons, [
        {"code": code, "name": name, "description": description, "feature_key": feature_key, "unit_label": unit,
         "unit_price_cents": price, "currency": "XAF", "status": status, "plan_codes": plans, "sort_order": order,
         "created_at": now, "updated_at": now}
        for code, name, description, feature_key, unit, price, status, plans, order in ADDONS
    ])


def downgrade() -> None:
    op.drop_table("school_payouts")
    op.drop_table("school_ledger_entries")
    op.drop_table("addons")
    for table in ("billing_payment_attempts", "billing_invoices"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("lines")
    with op.batch_alter_table("plans") as batch_op:
        batch_op.drop_column("sales_commission_bps")
