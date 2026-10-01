from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import AuthenticatedSession
from app.core.security import decode_access_token
from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationPlanOverrideRecord,
    OrganizationRecord,
    PlanEntitlementRecord,
    PlanRecord,
    PlatformAdminAuditRecord,
    PlatformSupportSessionRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.services.admin import (
    cancel_commercial_access,
    end_support_session,
    grant_commercial_access,
    start_support_session,
)
from app.services.subscriptions import check_entitlement


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
    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    org = OrganizationRecord(
        name="School",
        slug="school",
        status="active",
        is_active=True,
    )
    starter = PlanRecord(
        code="starter",
        name="Starter",
        currency="XAF",
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    pro = PlanRecord(
        code="pro",
        name="Pro",
        currency="XAF",
        trial_days=14,
        is_public=True,
        is_active=True,
    )
    db.add_all([admin, owner, org, starter, pro])
    db.flush()
    db.add_all([
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        ),
        PlanEntitlementRecord(
            plan_id=starter.id,
            feature_key="students",
            enabled=True,
            limit_value=20,
        ),
        PlanEntitlementRecord(
            plan_id=pro.id,
            feature_key="students",
            enabled=True,
            limit_value=100,
        ),
    ])
    now = datetime.now(UTC)
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=starter.id,
            status="active",
            billing_interval="monthly",
            started_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
    )
    db.commit()
    return admin, org, starter, pro


def test_commercial_access_overrides_entitlements_without_touching_subscription() -> None:
    db = build_db()
    admin, org, starter, pro = seed(db)

    before = check_entitlement(
        db,
        organization_id=org.id,
        feature_key="students",
    )
    assert before.limit_value == 20

    detail = grant_commercial_access(
        db,
        actor=admin,
        organization_id=org.id,
        plan_id=pro.id,
        days=30,
        reason="Essai commercial Pro.",
    )
    assert detail.commercial_access is not None
    assert detail.commercial_access.plan_code == "pro"

    during = check_entitlement(
        db,
        organization_id=org.id,
        feature_key="students",
    )
    assert during.limit_value == 100

    subscription = db.query(SubscriptionRecord).filter_by(
        organization_id=org.id
    ).one()
    assert subscription.plan_id == starter.id

    cancel_commercial_access(
        db,
        actor=admin,
        organization_id=org.id,
        reason="Fin anticipée du geste commercial.",
    )
    after = check_entitlement(
        db,
        organization_id=org.id,
        feature_key="students",
    )
    assert after.limit_value == 20


def test_support_session_is_short_lived_and_audited() -> None:
    db = build_db()
    admin, org, _, _ = seed(db)

    result = start_support_session(
        db,
        actor=admin,
        organization_id=org.id,
        reason="Diagnostic demandé par le client.",
        minutes=30,
    )

    claims = decode_access_token(result.access_token)
    assert claims is not None
    assert int(str(claims["support_org_id"])) == org.id
    assert int(str(claims["support_session_id"])) == result.session_id

    record = db.get(PlatformSupportSessionRecord, result.session_id)
    assert record is not None
    assert record.ended_at is None

    end_support_session(
        db,
        actor=admin,
        support_session=record,
    )
    assert record.ended_at is not None

    actions = [
        item.action
        for item in db.query(PlatformAdminAuditRecord)
        .filter_by(organization_id=org.id)
        .order_by(PlatformAdminAuditRecord.id)
        .all()
    ]
    assert "support.started" in actions
    assert "support.ended" in actions
