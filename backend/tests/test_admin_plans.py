from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import PlanRecord, PlatformAdminAuditRecord, UserRecord
from app.services.admin import (
    list_admin_plans,
    replace_admin_plan_entitlements,
    update_admin_plan,
)


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    admin = UserRecord(
        email="admin@example.test",
        full_name="Admin",
        status="active",
        platform_role="super_admin",
    )
    plan = PlanRecord(
        code="starter",
        name="Starter",
        description="Initial",
        currency="EUR",
        monthly_price_cents=None,
        annual_price_cents=None,
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    db.add_all([admin, plan])
    db.commit()
    return admin, plan


def test_admin_can_update_plan_configuration() -> None:
    db = build_db()
    admin, plan = seed(db)

    updated = update_admin_plan(
        db,
        actor=admin,
        plan_id=plan.id,
        values={
            "currency": "xaf",
            "monthly_price_cents": 25000,
            "annual_price_cents": 250000,
            "trial_days": 21,
        },
        reason="Nouvelle grille commerciale.",
    )

    assert updated.currency == "XAF"
    assert updated.monthly_price_cents == 25000
    assert updated.annual_price_cents == 250000
    assert updated.trial_days == 21

    log = db.query(PlatformAdminAuditRecord).filter_by(
        action="plan.updated"
    ).one()
    assert log.organization_id is None


def test_admin_can_replace_plan_entitlements() -> None:
    db = build_db()
    admin, plan = seed(db)

    updated = replace_admin_plan_entitlements(
        db,
        actor=admin,
        plan_id=plan.id,
        entitlements=[
            {
                "feature_key": "students",
                "enabled": True,
                "limit_value": 50,
            },
            {
                "feature_key": "custom_domain",
                "enabled": False,
                "limit_value": None,
            },
        ],
        reason="Configuration du forfait.",
    )

    by_key = {
        item.feature_key: item
        for item in updated.entitlements
    }
    assert by_key["students"].limit_value == 50
    assert by_key["custom_domain"].enabled is False

    second = replace_admin_plan_entitlements(
        db,
        actor=admin,
        plan_id=plan.id,
        entitlements=[
            {
                "feature_key": "students",
                "enabled": True,
                "limit_value": 100,
            }
        ],
        reason="Mise à jour du quota.",
    )

    assert len(second.entitlements) == 1
    assert second.entitlements[0].feature_key == "students"
    assert second.entitlements[0].limit_value == 100
