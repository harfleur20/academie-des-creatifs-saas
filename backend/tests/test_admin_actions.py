from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanRecord,
    PlatformAdminAuditRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.services.admin import (
    extend_trial,
    reactivate_organization,
    suspend_organization,
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
        full_name="Platform Admin",
        status="active",
        platform_role="super_admin",
    )
    owner = UserRecord(
        email="owner@example.test",
        full_name="School Owner",
        status="active",
    )
    org = OrganizationRecord(
        name="School",
        slug="school",
        status="active",
        is_active=True,
    )
    plan = PlanRecord(
        code="starter",
        name="Starter",
        currency="EUR",
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    db.add_all([admin, owner, org, plan])
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
    )
    trial_end = datetime.now(UTC) + timedelta(days=5)
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=plan.id,
            status="trialing",
            billing_interval="monthly",
            started_at=datetime.now(UTC),
            trial_ends_at=trial_end,
            current_period_start=datetime.now(UTC),
            current_period_end=trial_end,
        )
    )
    db.commit()
    return admin, org


def test_suspend_and_reactivate_are_audited() -> None:
    db = build_db()
    admin, org = seed(db)

    suspended = suspend_organization(
        db,
        actor=admin,
        organization_id=org.id,
        reason="Impayé confirmé par le support.",
    )
    assert suspended.is_active is False
    assert suspended.status == "suspended"

    reactivated = reactivate_organization(
        db,
        actor=admin,
        organization_id=org.id,
        reason="Situation régularisée.",
    )
    assert reactivated.is_active is True
    assert reactivated.status == "active"

    logs = db.query(PlatformAdminAuditRecord).order_by(
        PlatformAdminAuditRecord.id
    ).all()
    assert [log.action for log in logs] == [
        "organization.suspended",
        "organization.reactivated",
    ]
    assert all(log.actor_user_id == admin.id for log in logs)


def test_extend_trial_updates_subscription_and_audits() -> None:
    db = build_db()
    admin, org = seed(db)

    before = db.query(SubscriptionRecord).filter_by(
        organization_id=org.id
    ).one().trial_ends_at

    result = extend_trial(
        db,
        actor=admin,
        organization_id=org.id,
        days=10,
        reason="Geste commercial.",
    )

    subscription = db.query(SubscriptionRecord).filter_by(
        organization_id=org.id
    ).one()
    assert subscription.trial_ends_at > before
    assert result.subscription is not None
    assert result.subscription.status == "trialing"

    log = db.query(PlatformAdminAuditRecord).filter_by(
        action="subscription.trial_extended"
    ).one()
    assert log.reason == "Geste commercial."
