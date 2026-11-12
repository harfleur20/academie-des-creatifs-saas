"""Plans, add-ons billed per unit, and the platform's commission on school sales (docs/FORFAITS.md)."""
import importlib.util
import itertools
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_academic_suite import build_db, ctx

from app.models.entities import (
    AddonRecord,
    BillingInvoiceRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrderInstallmentRecord,
    OrganizationInvitationRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    PlanEntitlementRecord,
    PlanRecord,
    SchoolNotificationRecord,
    StudentOrderRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.services.membership_roles import replace_effective_roles
from app.services.plan_limits import billing_usage, notify_student_quotas, quote, require_capacity, require_feature
from app.services.school_revenue import cancel_payout, process_payout, record_sale, request_payout, revenue_summary
from app.services.subscriptions import apply_subscription_lifecycle, start_default_trial

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261112_0060_plans_addons_revenue.py"
_spec = importlib.util.spec_from_file_location("plans_migration", MIGRATION)
grid = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grid)
NOW = datetime.now(UTC)
_unique = itertools.count()


def plans(db) -> dict[str, PlanRecord]:
    """The grid the migration puts in production."""
    out = {}
    for code, (description, monthly, annual, commission, entitlements) in grid.PLANS.items():
        plan = PlanRecord(code=code, name=code.capitalize(), description=description, currency="XAF",
                          monthly_price_cents=monthly, annual_price_cents=annual, trial_days=14,
                          is_public=True, is_active=True, sales_commission_bps=commission)
        plan.entitlements = [PlanEntitlementRecord(feature_key=key, enabled=enabled, limit_value=limit)
                             for key, enabled, limit in entitlements]
        db.add(plan)
        out[code] = plan
    for code, name, description, feature_key, unit, price, status, plan_codes, order in grid.ADDONS:
        db.add(AddonRecord(code=code, name=name, description=description, feature_key=feature_key, unit_label=unit,
                           unit_price_cents=price, currency="XAF", status=status, plan_codes=plan_codes, sort_order=order))
    db.commit()
    return out


def school(db, plan: PlanRecord, *, interval="monthly", status="active"):
    org = OrganizationRecord(name="École", slug=f"ecole-{plan.code}-{interval}")
    owner = UserRecord(email=f"owner-{org.slug}@test.dev", full_name="Owner", status="active")
    db.add_all([org, owner])
    db.flush()
    member = OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active")
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"owner"})
    db.add(SubscriptionRecord(organization_id=org.id, plan_id=plan.id, status=status, billing_interval=interval,
                              started_at=NOW - timedelta(days=40), current_period_start=NOW - timedelta(days=30),
                              current_period_end=NOW + timedelta(days=1)))
    db.commit()
    return org, owner


def add_students(db, org, count: int, *, ended=False):
    batch = next(_unique)
    formation = FormationRecord(organization_id=org.id, slug=f"f-{batch}", title="Formation", status="published")
    db.add(formation)
    db.flush()
    today = date.today()
    session = FormationSessionRecord(organization_id=org.id, formation_id=formation.id, label="Cohorte",
                                     start_date=today - timedelta(days=60),
                                     end_date=today - timedelta(days=1) if ended else today + timedelta(days=60), status="open")
    db.add(session)
    db.flush()
    for index in range(count):
        user = UserRecord(email=f"s{index}-{batch}@test.dev", full_name=f"Étudiant {index}", status="active")
        db.add(user)
        db.flush()
        db.add(EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=user.id, status="active"))
    db.commit()
    return formation, session


def add_teachers(db, org, count: int):
    for index in range(count):
        user = UserRecord(email=f"t{index}-{org.id}@test.dev", full_name=f"Prof {index}", status="active")
        db.add(user)
        db.flush()
        member = OrganizationMemberRecord(organization_id=org.id, user_id=user.id, role="teacher", status="active")
        db.add(member)
        db.flush()
        replace_effective_roles(db, member, {"teacher"})
    db.commit()


def test_a_school_beyond_its_students_quota_pays_each_extra_student():
    db = build_db()
    grid_plans = plans(db)
    org, _owner = school(db, grid_plans["starter"])
    add_students(db, org, 52)
    add_students(db, org, 30, ended=True)  # a finished cohort no longer counts

    monthly = quote(db, org.id, grid_plans["starter"], "monthly")
    assert [(line.label, line.quantity, line.amount_cents) for line in monthly.lines] == [
        ("Forfait Starter (mensuel)", 1, 15_000),
        ("Étudiant supplémentaire", 2, 600),
    ]
    assert monthly.total_cents == 15_600
    # Annual: ten months of the plan, and of each extra student.
    assert quote(db, org.id, grid_plans["starter"], "annual").total_cents == 150_000 + 2 * 3_000
    # On Pro, the same school fits in its plan.
    assert quote(db, org.id, grid_plans["pro"], "monthly").total_cents == 35_000

    usage = billing_usage(db, org.id)
    students = next(item for item in usage["metrics"] if item["feature_key"] == "students")
    assert (students["current"], students["limit"], students["extra"], students["extra_amount_cents"]) == (52, 50, 2, 600)
    assert usage["commission_bps"] == 800 and usage["live_included"] is True


def test_the_renewal_invoice_lists_the_plan_and_the_add_ons():
    db = build_db()
    grid_plans = plans(db)
    org, _owner = school(db, grid_plans["starter"])
    add_students(db, org, 51)
    subscription = db.scalar(select(SubscriptionRecord).where(SubscriptionRecord.organization_id == org.id))
    apply_subscription_lifecycle(db, subscription, now=NOW + timedelta(days=2))
    db.commit()
    invoice = db.scalar(select(BillingInvoiceRecord).where(BillingInvoiceRecord.organization_id == org.id))
    assert invoice.amount_cents == 15_300
    assert [line["label"] for line in invoice.lines] == ["Forfait Starter (mensuel)", "Étudiant supplémentaire"]


def test_one_teacher_too_many_asks_the_school_to_accept_the_add_on():
    db = build_db()
    grid_plans = plans(db)
    org, _owner = school(db, grid_plans["starter"])
    add_teachers(db, org, 2)
    with pytest.raises(HTTPException) as asked:
        require_capacity(db, org.id, "teachers")
    assert asked.value.status_code == 409
    assert asked.value.detail["code"] == "addon_required"
    assert "2 500 FCFA par mois" in asked.value.detail["message"]
    require_capacity(db, org.id, "teachers", accept_addon=True)

    # A pending invitation already holds a seat.
    db.add(OrganizationInvitationRecord(organization_id=org.id, email="new@test.dev", role="teacher", status="pending",
                                        token_hash="x", expires_at=NOW + timedelta(days=3)))
    db.commit()
    assert billing_usage(db, org.id)["metrics"][1]["current"] == 3


def test_without_an_add_on_the_school_moves_up_a_plan():
    db = build_db()
    grid_plans = plans(db)
    addon = db.scalar(select(AddonRecord).where(AddonRecord.code == "extra_teacher"))
    addon.status = "inactive"
    db.commit()
    org, _owner = school(db, grid_plans["starter"])
    add_teachers(db, org, 2)
    with pytest.raises(HTTPException) as refused:
        require_capacity(db, org.id, "teachers", accept_addon=True)
    assert refused.value.status_code == 403
    assert "Passez au forfait supérieur" in refused.value.detail


def test_every_plan_includes_live_classes_with_a_per_class_student_limit():
    db = build_db()
    grid_plans = plans(db)
    organizations = {}
    for code, limit in {"starter": 10, "pro": 50, "business": 100}.items():
        org, _ = school(db, grid_plans[code])
        organizations[code] = org
        entitlement = next(item for item in grid_plans[code].entitlements if item.feature_key == "live")
        assert entitlement.enabled is True
        assert entitlement.limit_value == limit
        require_feature(db, org.id, "live")

    starter = organizations["starter"]
    pro = organizations["pro"]
    with pytest.raises(HTTPException) as domain:
        require_feature(db, starter.id, "custom_domain")
    assert domain.value.detail == "Le domaine personnalisé est inclus à partir du forfait Pro."
    require_feature(db, pro.id, "live")
    require_feature(db, pro.id, "custom_domain")


def test_a_school_without_a_plan_is_not_restricted():
    db = build_db()
    plans(db)
    org = OrganizationRecord(name="Ancienne", slug="ancienne")
    db.add(org)
    db.commit()
    add_teachers(db, org, 15)
    require_capacity(db, org.id, "teachers")
    require_feature(db, org.id, "live")


def test_the_trial_lets_a_new_school_try_pro():
    db = build_db()
    plans(db)
    org = OrganizationRecord(name="Nouvelle", slug="nouvelle")
    db.add(org)
    db.commit()
    subscription = start_default_trial(db, organization_id=org.id)
    assert subscription.status == "trialing"
    assert subscription.plan.code == "pro"


def paid_installment(db, org, owner, amount=150_000):
    formation = FormationRecord(organization_id=org.id, slug=f"vente-{amount}", title="Design", status="published")
    db.add(formation)
    db.flush()
    session = FormationSessionRecord(organization_id=org.id, formation_id=formation.id, label="Cohorte",
                                     start_date=date.today(), end_date=date.today() + timedelta(days=30), status="open")
    db.add(session)
    db.flush()
    order = StudentOrderRecord(organization_id=org.id, order_number=f"CMD-{amount}", user_id=owner.id,
                               formation_id=formation.id, session_id=session.id, base_price_cents=amount,
                               final_price_cents=amount, currency="XAF", branding_snapshot={})
    db.add(order)
    db.flush()
    installment = OrderInstallmentRecord(organization_id=org.id, order_id=order.id, sequence=1, amount_cents=amount,
                                         due_at=NOW, grace_until=NOW, status="paid", paid_at=NOW)
    db.add(installment)
    db.flush()
    return order, installment


def test_each_paid_instalment_credits_the_school_net_of_its_plans_commission():
    db = build_db()
    grid_plans = plans(db)
    org, owner = school(db, grid_plans["starter"])
    order, installment = paid_installment(db, org, owner)
    entry = record_sale(db, org, order, installment, NOW)
    assert (entry.commission_bps, entry.commission_cents, entry.amount_cents) == (800, 12_000, 138_000)
    assert record_sale(db, org, order, installment, NOW).id == entry.id  # once only
    db.commit()

    summary = revenue_summary(db, org.id)
    assert (summary.gross_cents, summary.commission_cents, summary.available_cents) == (150_000, 12_000, 138_000)

    pro, pro_owner = school(db, grid_plans["pro"])
    pro_order, pro_installment = paid_installment(db, pro, pro_owner, amount=100_000)
    assert record_sale(db, pro, pro_order, pro_installment, NOW).commission_cents == 5_000


def test_a_school_asks_for_its_payout_and_the_platform_transfers_it():
    db = build_db()
    grid_plans = plans(db)
    org, owner = school(db, grid_plans["business"])
    order, installment = paid_installment(db, org, owner, amount=50_000)
    record_sale(db, org, order, installment, NOW)  # 3 % on Business: 48 500 owed
    db.commit()
    tenant = ctx(db, org, owner)

    with pytest.raises(HTTPException) as too_small:
        request_payout(db, tenant, amount_cents=5_000, method="mobile_money", destination="+237 600 000 000", account_name="École")
    assert "10 000 FCFA" in too_small.value.detail
    with pytest.raises(HTTPException) as too_much:
        request_payout(db, tenant, amount_cents=60_000, method="mobile_money", destination="+237 600 000 000", account_name="École")
    assert "48 500 FCFA" in too_much.value.detail

    payout = request_payout(db, tenant, amount_cents=40_000, method="mobile_money", destination="+237 600 000 000", account_name="École")
    assert revenue_summary(db, org.id).available_cents == 8_500
    with pytest.raises(HTTPException) as one_at_a_time:
        request_payout(db, tenant, amount_cents=10_000, method="bank", destination="CM21 0000", account_name="École")
    assert one_at_a_time.value.status_code == 409

    with pytest.raises(HTTPException):
        process_payout(db, owner, payout.id, paid=True)  # a transfer reference is required
    process_payout(db, owner, payout.id, paid=True, transfer_reference="OM-123456")
    summary = revenue_summary(db, org.id)
    assert (summary.paid_out_cents, summary.pending_payout_cents, summary.available_cents) == (40_000, 0, 8_500)
    assert db.scalar(select(SchoolNotificationRecord).where(SchoolNotificationRecord.event_key == f"payout.paid:{payout.id}"))


def test_a_cancelled_or_rejected_payout_frees_the_balance():
    db = build_db()
    grid_plans = plans(db)
    org, owner = school(db, grid_plans["business"])
    order, installment = paid_installment(db, org, owner, amount=100_000)
    record_sale(db, org, order, installment, NOW)
    db.commit()
    tenant = ctx(db, org, owner)
    first = request_payout(db, tenant, amount_cents=50_000, method="bank", destination="CM21 0000", account_name="École")
    cancel_payout(db, tenant, first.id)
    second = request_payout(db, tenant, amount_cents=50_000, method="bank", destination="CM21 0000", account_name="École")
    with pytest.raises(HTTPException):
        process_payout(db, owner, second.id, paid=False)  # a reason is required
    process_payout(db, owner, second.id, paid=False, note="RIB illisible")
    assert revenue_summary(db, org.id).available_cents == 97_000


def test_a_school_is_told_when_its_students_near_or_pass_the_quota():
    db = build_db()
    grid_plans = plans(db)
    org, owner = school(db, grid_plans["starter"])
    add_students(db, org, 41)
    assert notify_student_quotas(db) == 1
    keys = [row.event_key for row in db.scalars(select(SchoolNotificationRecord))]
    assert keys == [f"quota.students.80:{org.id}:{(NOW - timedelta(days=30)).strftime('%Y%m%d')}"]
    notify_student_quotas(db)  # once per period
    assert db.scalar(select(SchoolNotificationRecord).where(SchoolNotificationRecord.event_key.like("quota.students.80:%"))).id
    assert len(list(db.scalars(select(SchoolNotificationRecord)))) == 1

    add_students(db, org, 12)
    notify_student_quotas(db)
    over = db.scalar(select(SchoolNotificationRecord).where(SchoolNotificationRecord.event_key.like("quota.students.over:%")))
    assert "53 étudiants actifs pour 50" in over.message and "3 × 300 FCFA" in over.message


def test_a_student_payment_through_the_shop_credits_the_school():
    from test_school_commerce import build_db as commerce_db
    from test_school_commerce import seed as commerce_seed

    from app.models.entities import SchoolLedgerEntryRecord
    from app.schemas.commerce import CheckoutCreate
    from app.services.school_commerce import confirm_demo_checkout, create_checkout

    db = commerce_db()
    org, user, _formation, session = commerce_seed(db)
    checkout = create_checkout(db, org, user, CheckoutCreate(session_id=session.id, payment_mode="full"))
    confirm_demo_checkout(db, org, user, checkout.order_id)
    entry = db.scalar(select(SchoolLedgerEntryRecord).where(SchoolLedgerEntryRecord.organization_id == org.id))
    # No plan on this school: the Starter rate applies.
    assert (entry.gross_cents, entry.commission_cents, entry.amount_cents) == (300_000, 24_000, 276_000)
    assert revenue_summary(db, org.id).available_cents == 276_000
