from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    OrganizationRecord,
    PlanEntitlementRecord,
    PlanRecord,
    SubscriptionRecord,
)
from app.services.subscriptions import (
    check_entitlement,
    get_current_subscription,
    set_usage,
    start_default_trial,
)


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_default_trial_is_created_for_new_organization() -> None:
    db = build_db()
    starter = PlanRecord(
        code="starter",
        name="Starter",
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([starter, org])
    db.flush()

    subscription = start_default_trial(db, organization_id=org.id)
    db.commit()

    assert subscription is not None
    assert subscription.status == "trialing"
    assert subscription.plan_id == starter.id
    assert subscription.trial_ends_at is not None


def test_feature_is_denied_without_entitlement() -> None:
    db = build_db()
    plan = PlanRecord(code="starter", name="Starter", trial_days=14)
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([plan, org])
    db.flush()
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=plan.id,
            status="active",
            billing_interval="monthly",
            started_at=datetime.now(UTC),
        )
    )
    db.commit()

    decision = check_entitlement(
        db,
        organization_id=org.id,
        feature_key="custom_domain",
    )

    assert decision.enabled is False
    assert decision.allowed is False


def test_feature_flag_is_allowed_when_enabled() -> None:
    db = build_db()
    plan = PlanRecord(code="pro", name="Pro", trial_days=14)
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([plan, org])
    db.flush()
    db.add(
        PlanEntitlementRecord(
            plan_id=plan.id,
            feature_key="custom_domain",
            enabled=True,
        )
    )
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=plan.id,
            status="active",
            billing_interval="monthly",
            started_at=datetime.now(UTC),
        )
    )
    db.commit()

    decision = check_entitlement(
        db,
        organization_id=org.id,
        feature_key="custom_domain",
    )

    assert decision.enabled is True
    assert decision.allowed is True


def test_quota_is_blocked_at_limit() -> None:
    db = build_db()
    plan = PlanRecord(code="starter", name="Starter", trial_days=14)
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([plan, org])
    db.flush()
    db.add(
        PlanEntitlementRecord(
            plan_id=plan.id,
            feature_key="students",
            enabled=True,
            limit_value=20,
        )
    )
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=plan.id,
            status="active",
            billing_interval="monthly",
            started_at=datetime.now(UTC),
        )
    )
    set_usage(
        db,
        organization_id=org.id,
        metric_key="students_count",
        current_value=20,
    )
    db.commit()

    decision = check_entitlement(
        db,
        organization_id=org.id,
        feature_key="students",
        usage_metric_key="students_count",
    )

    assert decision.current_value == 20
    assert decision.limit_value == 20
    assert decision.allowed is False


def test_expired_trial_is_not_active() -> None:
    db = build_db()
    plan = PlanRecord(code="starter", name="Starter")
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([plan, org])
    db.flush()
    subscription = SubscriptionRecord(
        organization_id=org.id,
        plan_id=plan.id,
        status="trialing",
        billing_interval="monthly",
        started_at=datetime.now(UTC) - timedelta(days=20),
        trial_ends_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add(subscription)
    db.commit()

    current = get_current_subscription(db, org.id)

    assert current is None
    assert subscription.status == "suspended"
