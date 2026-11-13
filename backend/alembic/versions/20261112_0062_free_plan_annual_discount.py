"""The plans grid: a free plan, students without limit, -20 % on the annual price (docs/FORFAITS.md).

- Découverte: free, no live classes; the platform earns its commission on sales only.
  A school without a running paid plan (trial over, cancelled, unpaid) is on it.
- Students are no longer counted against a quota, and the extra-student add-on stops.
- Live classes are capped per class and in how many run at once (live_rooms).
- Replays, their retention after the session, transcription and advanced statistics are
  part of the plans already, shown as coming soon until they work.
- Commissions take the payment fees into account, with a gateway around 3 %.

Revision ID: 20261112_0062
Revises: 20261112_0061
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20261112_0062"
down_revision = "20261112_0061"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

FREE_PLAN_CODE = "decouverte"

PLANS = {
    # code: (name, description, monthly, annual, commission in basis points, trial days, entitlements)
    "decouverte": (
        "Découverte",
        "Pour lancer votre école sans abonnement : vous ne payez que lorsque vous vendez.",
        0, 0, 1_000, 0,
        [("students", True, None), ("teachers", True, 1), ("active_formations", True, 1),
         ("live", False, None), ("custom_domain", False, None)],
    ),
    "starter": (
        "Starter",
        "Pour les formateurs et les petites écoles qui lancent leurs cours en live.",
        15_000, 144_000, 800, 14,
        [("students", True, None), ("teachers", True, 2), ("active_formations", True, 3),
         ("live", True, 10), ("live_rooms", True, 1), ("replays", True, 2), ("replay_retention_days", True, 0),
         ("custom_domain", False, None)],
    ),
    "pro": (
        "Pro",
        "Pour les écoles qui grandissent : plus de live, des replays et des statistiques.",
        35_000, 336_000, 600, 14,
        [("students", True, None), ("teachers", True, 10), ("active_formations", True, None),
         ("live", True, 50), ("live_rooms", True, 2), ("replays", True, 15), ("replay_retention_days", True, 30),
         ("transcription", True, 5), ("advanced_stats", True, None), ("custom_domain", True, None),
         ("whatsapp_support", True, None)],
    ),
    "business": (
        "Business",
        "Pour les grandes écoles, avec plus de lives et leur seule marque.",
        75_000, 720_000, 400, 14,
        [("students", True, None), ("teachers", True, None), ("active_formations", True, None),
         ("live", True, 100), ("live_rooms", True, 5), ("replays", True, 50), ("replay_retention_days", True, 180),
         ("transcription", True, 50), ("advanced_stats", True, None), ("custom_domain", True, None),
         ("white_label", True, None), ("whatsapp_support", True, None), ("priority_support", True, None)],
    ),
}

ADDONS = [
    # code, name, description, feature_key, unit_label, price, status, plans, order
    ("extra_student", "Étudiant supplémentaire", "Chaque étudiant actif au-delà de votre forfait.",
     "students", "étudiant", 300, "inactive", ["starter", "pro"], 10),
    ("extra_teacher", "Professeur supplémentaire", "Chaque professeur au-delà de votre forfait.",
     "teachers", "professeur", 2_500, "active", ["starter", "pro"], 20),
    ("extra_formation", "Formation supplémentaire", "Chaque formation publiée au-delà de votre forfait.",
     "active_formations", "formation", 2_000, "active", ["starter"], 30),
    ("live_replays", "10 h de replay en plus", "Dix heures de cours en live enregistrées en plus, gardées comme celles du forfait.",
     None, "pack de 10 h", 3_000, "coming_soon", ["starter", "pro", "business"], 40),
    ("live_transcription", "10 h de transcription en plus", "Dix heures de cours en live transcrites en plus.",
     None, "pack de 10 h", 3_000, "coming_soon", ["pro", "business"], 50),
]

# What 0060 and 0061 left, to go back to.
PREVIOUS_PLANS = {
    "starter": (
        "Starter", "Pour les formateurs et les petites écoles, avec des lives jusqu’à 10 étudiants.",
        15_000, 150_000, 800, 14,
        [("students", True, 50), ("teachers", True, 2), ("active_formations", True, 3),
         ("live", True, 10), ("custom_domain", False, None)],
    ),
    "pro": (
        "Pro", "Pour les écoles qui accueillent jusqu’à 50 étudiants par live.",
        35_000, 350_000, 500, 14,
        [("students", True, 300), ("teachers", True, 10), ("active_formations", True, None),
         ("live", True, 50), ("custom_domain", True, None)],
    ),
    "business": (
        "Business", "Pour les écoles avec plusieurs équipes et des lives jusqu’à 100 étudiants.",
        75_000, 750_000, 300, 14,
        [("students", True, None), ("teachers", True, None), ("active_formations", True, None),
         ("live", True, 100), ("custom_domain", True, None), ("priority_support", True, None)],
    ),
}
PREVIOUS_ADDONS = {
    "extra_student": ("Étudiant supplémentaire", "Chaque étudiant actif au-delà de votre forfait.", "étudiant", 300, "active",
                      ["starter", "pro"]),
    "live_replays": ("Replays des lives", "Les cours en live enregistrés et revus par vos étudiants.", "mois", None,
                     "coming_soon", ["pro", "business"]),
    "live_transcription": ("Transcription des lives", "Le texte de chaque cours en live, consultable et cherchable.", "mois",
                           None, "coming_soon", ["pro", "business"]),
}


def _write_plans(grid: dict) -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    for code, (name, description, monthly, annual, commission, trial_days, entitlements) in grid.items():
        values = {"code": code, "name": name, "description": description, "monthly": monthly, "annual": annual,
                  "commission": commission, "trial_days": trial_days, "now": now}
        plan = bind.execute(sa.text("SELECT id FROM plans WHERE code = :code"), {"code": code}).first()
        if plan is None:
            bind.execute(sa.text(
                "INSERT INTO plans (code, name, description, currency, monthly_price_cents, annual_price_cents, "
                "trial_days, is_public, is_active, sales_commission_bps, created_at, updated_at) "
                "VALUES (:code, :name, :description, 'XAF', :monthly, :annual, :trial_days, :public, :active, "
                ":commission, :now, :now)"
            ), {**values, "public": True, "active": True})
            plan = bind.execute(sa.text("SELECT id FROM plans WHERE code = :code"), {"code": code}).first()
        else:
            bind.execute(sa.text(
                "UPDATE plans SET name = :name, description = :description, currency = 'XAF', "
                "monthly_price_cents = :monthly, annual_price_cents = :annual, sales_commission_bps = :commission, "
                "trial_days = :trial_days, is_public = :public, is_active = :active, updated_at = :now WHERE id = :id"
            ), {**values, "public": True, "active": True, "id": plan.id})
        bind.execute(sa.text("DELETE FROM plan_entitlements WHERE plan_id = :id"), {"id": plan.id})
        for feature_key, enabled, limit in entitlements:
            bind.execute(sa.text(
                "INSERT INTO plan_entitlements (plan_id, feature_key, enabled, limit_value, created_at, updated_at) "
                "VALUES (:plan_id, :feature_key, :enabled, :limit, :now, :now)"
            ), {"plan_id": plan.id, "feature_key": feature_key, "enabled": enabled, "limit": limit, "now": now})


def _write_addon(code: str, name: str, description: str, unit: str, price: int | None, status: str, plans: list[str]) -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE addons SET name = :name, description = :description, unit_label = :unit, unit_price_cents = :price, "
            "status = :status, plan_codes = :plans, updated_at = :now WHERE code = :code"
        ).bindparams(sa.bindparam("plans", type_=sa.JSON)),
        {"code": code, "name": name, "description": description, "unit": unit, "price": price, "status": status,
         "plans": plans, "now": datetime.now(UTC)},
    )


def upgrade() -> None:
    _write_plans(PLANS)
    for code, name, description, _feature_key, unit, price, status, plans, _order in ADDONS:
        _write_addon(code, name, description, unit, price, status, plans)


def downgrade() -> None:
    _write_plans(PREVIOUS_PLANS)
    # Schools may be on the free plan: it stays, hidden and closed to new ones.
    op.get_bind().execute(sa.text("UPDATE plans SET is_public = :no, is_active = :no WHERE code = :code"),
                          {"no": False, "code": FREE_PLAN_CODE})
    for code, (name, description, unit, price, status, plans) in PREVIOUS_ADDONS.items():
        _write_addon(code, name, description, unit, price, status, plans)
