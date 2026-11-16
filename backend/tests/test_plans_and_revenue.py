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
from app.services.plan_limits import billing_usage, quote, require_capacity, require_feature
from app.services.public_catalog import school_white_label
from app.services.school_revenue import cancel_payout, process_payout, record_sale, request_payout, revenue_summary
from app.services.subscriptions import apply_subscription_lifecycle, get_effective_plan, list_public_plans, start_default_trial

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _migration(name: str):
    spec = importlib.util.spec_from_file_location(name, VERSIONS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The grid in production: 0066's plans, 0062's add-ons (0066 stops the extra formation).
grid = _migration("20261114_0066_live_for_every_plan")
addons = _migration("20261112_0062_free_plan_annual_discount")
current_limits = _migration("20261115_0070_adjust_live_plan_limits").LIMITS
organization_limits = _migration("20261116_0074_organization_creation_quotas").PLAN_LIMITS
NOW = datetime.now(UTC)
_unique = itertools.count()


def plans(db) -> dict[str, PlanRecord]:
    """The grid the migration puts in production."""
    out = {}
    for code, (name, description, monthly, annual, commission, trial_days, entitlements) in grid.PLANS.items():
        entitlements = [*entitlements, ("organizations", True, organization_limits[code])]
        plan = PlanRecord(code=code, name=name, description=description, currency="XAF",
                          monthly_price_cents=monthly, annual_price_cents=annual, trial_days=trial_days,
                          is_public=True, is_active=True, sales_commission_bps=commission)
        plan.entitlements = [PlanEntitlementRecord(feature_key=key, enabled=enabled, limit_value=limit)
                             for key, enabled, limit in entitlements]
        limits = current_limits.get(code, {})
        for entitlement in plan.entitlements:
            if entitlement.feature_key in limits:
                entitlement.limit_value = limits[entitlement.feature_key]
        db.add(plan)
        out[code] = plan
    for code, name, description, feature_key, unit, price, status, plan_codes, order in addons.ADDONS:
        status = "inactive" if code == "extra_formation" else status
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


def test_the_grid_is_free_then_paid_with_twenty_percent_off_a_year():
    db = build_db()
    grid_plans = plans(db)
    assert [plan.code for plan in list_public_plans(db)] == ["decouverte", "starter", "pro", "business"]
    commissions = {code: plan.sales_commission_bps for code, plan in grid_plans.items()}
    assert commissions == {"decouverte": 1_000, "starter": 800, "pro": 600, "business": 400}
    for code, plan in grid_plans.items():
        assert plan.annual_price_cents == plan.monthly_price_cents * 12 * 80 // 100, code
        students = next(item for item in plan.entitlements if item.feature_key == "students")
        assert (students.enabled, students.limit_value) == (True, None), code
    assert (grid_plans["starter"].annual_price_cents, grid_plans["pro"].annual_price_cents,
            grid_plans["business"].annual_price_cents) == (144_000, 288_000, 624_000)
    # Formations without limit in every paid plan.
    for code in ("starter", "pro", "business"):
        formations = next(item for item in grid_plans[code].entitlements if item.feature_key == "active_formations")
        assert (formations.enabled, formations.limit_value) == (True, None), code


def test_students_are_never_limited_and_extra_teachers_are_billed_per_unit():
    db = build_db()
    grid_plans = plans(db)
    org, _owner = school(db, grid_plans["starter"])
    add_students(db, org, 120)
    add_teachers(db, org, 3)

    monthly = quote(db, org.id, grid_plans["starter"], "monthly")
    assert [(line.label, line.quantity, line.amount_cents) for line in monthly.lines] == [
        ("Forfait Starter (mensuel)", 1, 15_000),
        ("Professeur supplémentaire", 1, 2_500),
    ]
    # Annual: twelve months minus 20 %, for the plan and for each extra teacher.
    annual = quote(db, org.id, grid_plans["starter"], "annual")
    assert [(line.label, line.amount_cents) for line in annual.lines] == [
        ("Forfait Starter (annuel)", 144_000),
        ("Professeur supplémentaire (12 mois, −20 %)", 24_000),
    ]
    # On Pro, the same school fits in its plan.
    assert quote(db, org.id, grid_plans["pro"], "monthly").total_cents == 30_000

    usage = billing_usage(db, org.id)
    students = next(item for item in usage["metrics"] if item["feature_key"] == "students")
    assert (students["current"], students["limit"], students["extra"]) == (120, None, 0)
    teachers = next(item for item in usage["metrics"] if item["feature_key"] == "teachers")
    assert (teachers["current"], teachers["limit"], teachers["extra"], teachers["extra_amount_cents"]) == (3, 2, 1, 2_500)
    assert usage["commission_bps"] == 800 and usage["live_included"] is True
    assert usage["next_payment"]["total_cents"] == 17_500


def test_the_renewal_invoice_lists_the_plan_and_the_add_ons():
    db = build_db()
    grid_plans = plans(db)
    org, _owner = school(db, grid_plans["starter"])
    add_teachers(db, org, 3)
    subscription = db.scalar(select(SubscriptionRecord).where(SubscriptionRecord.organization_id == org.id))
    apply_subscription_lifecycle(db, subscription, now=NOW + timedelta(days=2))
    db.commit()
    invoice = db.scalar(select(BillingInvoiceRecord).where(BillingInvoiceRecord.organization_id == org.id))
    assert invoice.amount_cents == 17_500
    assert [line["label"] for line in invoice.lines] == ["Forfait Starter (mensuel)", "Professeur supplémentaire"]


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


def test_every_plan_includes_live_classes_sized_per_class_and_at_once():
    db = build_db()
    grid_plans = plans(db)
    organizations = {}
    sizes_by_plan = {"decouverte": (10, 1, 6), "starter": (15, 2, None), "pro": (25, 5, None), "business": (30, 10, None)}
    duration_by_plan = {"decouverte": 2, "starter": 3, "pro": 4, "business": 4}
    for code, (per_class, at_once, monthly_hours) in sizes_by_plan.items():
        org, _ = school(db, grid_plans[code])
        organizations[code] = org
        sizes = {item.feature_key: item.limit_value for item in grid_plans[code].entitlements if item.enabled}
        assert (sizes["live"], sizes["live_rooms"], sizes.get("live_hours")) == (per_class, at_once, monthly_hours)
        assert sizes["live_class_hours"] == duration_by_plan[code]
        require_feature(db, org.id, "live")

    starter = organizations["starter"]
    pro = organizations["pro"]
    with pytest.raises(HTTPException) as domain:
        require_feature(db, starter.id, "custom_domain")
    assert domain.value.detail == "Le domaine personnalisé est inclus à partir du forfait Pro."
    require_feature(db, pro.id, "live")
    require_feature(db, pro.id, "custom_domain")


def test_without_a_free_plan_in_the_grid_a_school_without_a_plan_is_not_restricted():
    db = build_db()
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


def test_after_the_trial_a_school_goes_on_with_the_free_plan():
    db = build_db()
    grid_plans = plans(db)
    org, owner = school(db, grid_plans["pro"], status="trialing")
    subscription = db.scalar(select(SubscriptionRecord).where(SubscriptionRecord.organization_id == org.id))
    subscription.trial_ends_at = NOW - timedelta(minutes=1)
    db.commit()

    assert get_effective_plan(db, org.id).code == "decouverte"
    # Découverte keeps live classes, smaller: 10 students, one at a time, 6 hours a month.
    require_feature(db, org.id, "live")
    assert billing_usage(db, org.id)["live_included"] is True
    add_teachers(db, org, 1)
    with pytest.raises(HTTPException) as one_teacher:
        require_capacity(db, org.id, "teachers", accept_addon=True)
    assert "Passez au forfait supérieur" in one_teacher.value.detail
    usage = billing_usage(db, org.id)
    assert (usage["plan_code"], usage["commission_bps"], usage["next_payment"]) == ("decouverte", 1_000, None)
    order, installment = paid_installment(db, org, owner, amount=100_000)
    assert record_sale(db, org, order, installment, NOW).commission_cents == 10_000


def test_a_school_late_on_its_payment_keeps_its_plan_during_the_grace_period():
    db = build_db()
    grid_plans = plans(db)
    org, _owner = school(db, grid_plans["pro"], status="past_due")
    subscription = db.scalar(select(SubscriptionRecord).where(SubscriptionRecord.organization_id == org.id))
    subscription.grace_period_ends_at = NOW + timedelta(days=3)
    db.commit()
    assert get_effective_plan(db, org.id).code == "pro"
    subscription.grace_period_ends_at = NOW - timedelta(minutes=1)
    db.commit()
    assert get_effective_plan(db, org.id).code == "decouverte"


def test_only_business_hides_the_platform_signature():
    db = build_db()
    grid_plans = plans(db)
    assert school_white_label(db, school(db, grid_plans["business"])[0].id) is True
    assert school_white_label(db, school(db, grid_plans["pro"])[0].id) is False
    bare = build_db()
    org = OrganizationRecord(name="Sans forfait", slug="sans-forfait")
    bare.add(org)
    bare.commit()
    assert school_white_label(bare, org.id) is False


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
    assert record_sale(db, pro, pro_order, pro_installment, NOW).commission_cents == 6_000


def test_a_school_asks_for_its_payout_and_the_platform_transfers_it():
    db = build_db()
    grid_plans = plans(db)
    org, owner = school(db, grid_plans["business"])
    order, installment = paid_installment(db, org, owner, amount=50_000)
    record_sale(db, org, order, installment, NOW)  # 4 % on Business: 48 000 owed
    db.commit()
    tenant = ctx(db, org, owner)

    with pytest.raises(HTTPException) as too_small:
        request_payout(db, tenant, amount_cents=5_000, method="mobile_money", destination="+237 600 000 000", account_name="École")
    assert "10 000 FCFA" in too_small.value.detail
    with pytest.raises(HTTPException) as too_much:
        request_payout(db, tenant, amount_cents=60_000, method="mobile_money", destination="+237 600 000 000", account_name="École")
    assert "48 000 FCFA" in too_much.value.detail

    payout = request_payout(db, tenant, amount_cents=40_000, method="mobile_money", destination="+237 600 000 000", account_name="École")
    assert revenue_summary(db, org.id).available_cents == 8_000
    with pytest.raises(HTTPException) as one_at_a_time:
        request_payout(db, tenant, amount_cents=10_000, method="bank", destination="CM21 0000", account_name="École")
    assert one_at_a_time.value.status_code == 409

    with pytest.raises(HTTPException):
        process_payout(db, owner, payout.id, paid=True)  # a transfer reference is required
    process_payout(db, owner, payout.id, paid=True, transfer_reference="OM-123456")
    summary = revenue_summary(db, org.id)
    assert (summary.paid_out_cents, summary.pending_payout_cents, summary.available_cents) == (40_000, 0, 8_000)
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
    assert revenue_summary(db, org.id).available_cents == 96_000


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


def test_a_plan_runs_so_many_live_classes_at_once(monkeypatch):
    from test_academic_suite import seed

    from app.models.entities import SessionCourseDayRecord
    from app.services.live_classes import start_live_class

    # Teacher readiness has its own tests; this fixture's teacher predates onboarding.
    monkeypatch.setattr("app.services.live_classes.require_teacher_ready", lambda db, tenant: None)
    db = build_db()
    grid_plans = plans(db)
    org, teacher, _student, _classmate, session, _enrollment, _other, _lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    # Découverte runs one live class at a time.
    db.add(SubscriptionRecord(organization_id=org.id, plan_id=grid_plans["decouverte"].id, status="active",
                              billing_interval="monthly", started_at=NOW, current_period_start=NOW,
                              current_period_end=NOW + timedelta(days=30)))
    second = SessionCourseDayRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Cours 2",
                                    scheduled_at=day.scheduled_at, duration_minutes=120, status="planned")
    db.add(second)
    db.commit()
    tenant = ctx(db, org, teacher)
    nine = datetime(2025, 1, 10, 9, 0, tzinfo=UTC)

    start_live_class(db, tenant, day.id, now=nine)
    with pytest.raises(HTTPException) as busy:
        start_live_class(db, tenant, second.id, now=nine + timedelta(minutes=5))
    assert busy.value.status_code == 409
    assert "un seul cours en live à la fois" in busy.value.detail
    assert "Découverte" in busy.value.detail
    # Once the first class is over (its time and a quarter of an hour after), the room is free.
    assert start_live_class(db, tenant, second.id, now=nine + timedelta(minutes=136))["started_at"]


def test_the_plan_picked_on_the_landing_is_kept_on_the_trial_and_reminded_before_it_ends():
    from app.schemas.organizations import OrganizationCreate
    from app.services.organizations import create_organization
    from app.services.subscriptions import notify_trial_endings

    db = build_db()
    plans(db)
    owner = UserRecord(email="fondatrice@test.dev", full_name="Fondatrice", status="active")
    db.add(owner)
    db.commit()
    org = create_organization(db, user=owner, payload=OrganizationCreate(
        name="Studio Neuf", slug="studio-neuf", plan_code="starter", billing_interval="annual",
    ))
    trial = db.scalar(select(SubscriptionRecord).where(SubscriptionRecord.organization_id == org.id))
    # Whatever the school clicked, it tries Pro first; its choice is kept for later.
    assert (trial.status, trial.plan.code, trial.chosen_plan_code, trial.chosen_billing_interval) == (
        "trialing", "pro", "starter", "annual")

    ends = trial.trial_ends_at.replace(tzinfo=UTC) if trial.trial_ends_at.tzinfo is None else trial.trial_ends_at
    assert notify_trial_endings(db, now=ends - timedelta(days=10)) == 0
    assert notify_trial_endings(db, now=ends - timedelta(days=2)) == 1
    notify_trial_endings(db, now=ends - timedelta(days=2, hours=-1))  # once only
    reminders = list(db.scalars(select(SchoolNotificationRecord).where(SchoolNotificationRecord.organization_id == org.id)))
    assert [row.event_key for row in reminders] == [f"trial.ending.3:{trial.id}"]
    assert reminders[0].action_path == "/app/manage/billing?plan=starter&interval=annual"
    assert "Activez le forfait Starter" in reminders[0].message and "Découverte" in reminders[0].message
    notify_trial_endings(db, now=ends - timedelta(hours=20))
    keys = [row.event_key for row in db.scalars(select(SchoolNotificationRecord).where(SchoolNotificationRecord.organization_id == org.id))]
    assert keys == [f"trial.ending.3:{trial.id}", f"trial.ending.1:{trial.id}"]

    other = create_organization(db, user=owner, payload=OrganizationCreate(name="Sans choix", slug="sans-choix", plan_code="inconnu"))
    assert db.scalar(select(SubscriptionRecord).where(SubscriptionRecord.organization_id == other.id)).chosen_plan_code is None
