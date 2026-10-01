from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    FormationRecord,
    OrganizationMemberRecord,
    OrganizationPlanOverrideRecord,
    OrganizationRecord,
    PlanEntitlementRecord,
    PlanRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.services.admin import get_admin_organization


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_admin_usage_uses_real_counts_and_effective_plan_limits() -> None:
    db = build_db()
    owner = UserRecord(email="owner@example.test", full_name="Owner", status="active")
    student_a = UserRecord(email="a@example.test", full_name="A", status="active")
    student_b = UserRecord(email="b@example.test", full_name="B", status="active")
    teacher = UserRecord(email="teacher@example.test", full_name="Teacher", status="active")
    org = OrganizationRecord(name="School", slug="school")
    starter = PlanRecord(code="starter", name="Starter", currency="XAF", trial_days=14, is_public=True, is_active=True)
    pro = PlanRecord(code="pro", name="Pro", currency="XAF", trial_days=14, is_public=True, is_active=True)
    db.add_all([owner, student_a, student_b, teacher, org, starter, pro])
    db.flush()

    db.add_all([
        OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=student_a.id, role="student", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=student_b.id, role="student", status="active"),
        OrganizationMemberRecord(organization_id=org.id, user_id=teacher.id, role="teacher", status="active"),
        FormationRecord(organization_id=org.id, slug="one", title="One", description="", status="draft"),
        FormationRecord(organization_id=org.id, slug="two", title="Two", description="", status="archived"),
        PlanEntitlementRecord(plan_id=starter.id, feature_key="students", enabled=True, limit_value=2),
        PlanEntitlementRecord(plan_id=starter.id, feature_key="teachers", enabled=True, limit_value=1),
        PlanEntitlementRecord(plan_id=starter.id, feature_key="active_formations", enabled=True, limit_value=1),
        PlanEntitlementRecord(plan_id=pro.id, feature_key="students", enabled=True, limit_value=50),
        PlanEntitlementRecord(plan_id=pro.id, feature_key="teachers", enabled=True, limit_value=10),
        PlanEntitlementRecord(plan_id=pro.id, feature_key="active_formations", enabled=True, limit_value=20),
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

    starter_detail = get_admin_organization(db, org.id)
    starter_usage = {item.feature_key: item for item in starter_detail.usage_metrics}
    assert starter_detail.student_count == 2
    assert starter_detail.teacher_count == 1
    assert starter_detail.formation_count == 1
    assert starter_detail.effective_plan_name == "Starter"
    assert starter_usage["students"].current_value == 2
    assert starter_usage["students"].limit_value == 2
    assert starter_usage["active_formations"].current_value == 1

    db.add(
        OrganizationPlanOverrideRecord(
            organization_id=org.id,
            plan_id=pro.id,
            status="active",
            reason="Essai Pro",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=30),
        )
    )
    db.commit()

    pro_detail = get_admin_organization(db, org.id)
    pro_usage = {item.feature_key: item for item in pro_detail.usage_metrics}
    assert pro_detail.effective_plan_name == "Pro"
    assert pro_detail.effective_plan_source == "commercial_access"
    assert pro_usage["students"].limit_value == 50
    assert pro_usage["teachers"].limit_value == 10
