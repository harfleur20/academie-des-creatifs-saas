import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.dependencies import get_super_admin
from app.db.base import Base
from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.services.admin import get_admin_dashboard, list_admin_organizations


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_super_admin_dependency_rejects_regular_user() -> None:
    user = UserRecord(
        email="user@example.test",
        full_name="User",
        status="active",
        platform_role="user",
    )

    with pytest.raises(HTTPException) as exc:
        get_super_admin(user)

    assert exc.value.status_code == 403


def test_dashboard_and_organization_listing() -> None:
    db = build_db()

    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    admin = UserRecord(
        email="admin@example.test",
        full_name="Platform Admin",
        status="active",
        platform_role="super_admin",
    )
    org = OrganizationRecord(
        name="Studio Academy",
        slug="studio-academy",
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
    db.add_all([owner, admin, org, plan])
    db.flush()

    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
    )
    db.add(
        SubscriptionRecord(
            organization_id=org.id,
            plan_id=plan.id,
            status="trialing",
            billing_interval="monthly",
            started_at=org.created_at,
        )
    )
    db.commit()

    dashboard = get_admin_dashboard(db)
    organizations = list_admin_organizations(db)

    assert dashboard.organizations_total == 1
    assert dashboard.organizations_active == 1
    assert dashboard.users_total == 2
    assert dashboard.subscriptions_trialing == 1

    assert len(organizations) == 1
    assert organizations[0].name == "Studio Academy"
    assert organizations[0].owner_email == "owner@example.test"
    assert organizations[0].subscription is not None
    assert organizations[0].subscription.plan_code == "starter"
