"""What each plan includes, what a school uses, and what it pays beyond its plan (docs/FORFAITS.md).

- A plan's entitlements say what is included: a quota (students, teachers, published
  formations) or a feature (live classes, custom domain). A plan without any entitlement
  is not configured yet and restricts nothing; a school without a plan neither.
- Beyond a quota, an active add-on lets the school go on, billed per unit on its next
  payment. Teachers and formations ask the school to accept the add-on first; students
  enrol by themselves, so they are never blocked: the school is warned instead.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AddonRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationDomainRecord,
    OrganizationInvitationRecord,
    OrganizationMemberRecord,
    OrganizationMemberRoleRecord,
    PlanRecord,
    SubscriptionRecord,
)
from app.services.subscriptions import configured_plan_price, get_effective_plan, list_public_plans

METERED = ("students", "teachers", "active_formations")
FEATURE_LABELS = {
    "students": "étudiants actifs",
    "teachers": "professeurs",
    "active_formations": "formations publiées",
    "live": "Les cours en live",
    "custom_domain": "Le domaine personnalisé",
}
DEFAULT_COMMISSION_BPS = 800
# An annual plan costs ten months; add-ons follow the same rule.
MONTHS_BILLED = {"monthly": 1, "annual": 10}
STUDENT_ALERT_SHARE = 0.8


@dataclass(frozen=True)
class Allowance:
    enabled: bool
    limit: int | None  # None: unlimited


@dataclass(frozen=True)
class Line:
    label: str
    quantity: int
    unit_amount_cents: int
    amount_cents: int

    def as_dict(self) -> dict:
        return {"label": self.label, "quantity": self.quantity,
                "unit_amount_cents": self.unit_amount_cents, "amount_cents": self.amount_cents}


@dataclass(frozen=True)
class Quote:
    currency: str
    lines: list[Line]

    @property
    def total_cents(self) -> int:
        return sum(line.amount_cents for line in self.lines)

    def line_dicts(self) -> list[dict]:
        return [line.as_dict() for line in self.lines]


def allowance(plan: PlanRecord | None, feature_key: str) -> Allowance:
    if plan is None or not plan.entitlements:
        return Allowance(enabled=True, limit=None)
    item = next((entry for entry in plan.entitlements if entry.feature_key == feature_key), None)
    if item is None or not item.enabled:
        return Allowance(enabled=False, limit=None)
    return Allowance(enabled=True, limit=item.limit_value)


def usage(db: Session, organization_id: int, *, today: date | None = None) -> dict[str, int]:
    """What the school uses now, as the plans count it."""
    today = today or datetime.now(UTC).date()
    students = db.scalar(
        select(func.count(distinct(EnrollmentRecord.student_id)))
        .join(FormationSessionRecord, FormationSessionRecord.id == EnrollmentRecord.session_id)
        .where(
            EnrollmentRecord.organization_id == organization_id,
            EnrollmentRecord.status == "active",
            FormationSessionRecord.end_date >= today,
        )
    ) or 0
    teacher_roles = select(OrganizationMemberRoleRecord.member_id).where(
        OrganizationMemberRoleRecord.organization_id == organization_id,
        OrganizationMemberRoleRecord.role == "teacher",
    )
    teachers = db.scalar(
        select(func.count(OrganizationMemberRecord.id)).where(
            OrganizationMemberRecord.organization_id == organization_id,
            OrganizationMemberRecord.status == "active",
            or_(OrganizationMemberRecord.role == "teacher", OrganizationMemberRecord.id.in_(teacher_roles)),
        )
    ) or 0
    invited = db.scalar(
        select(func.count(OrganizationInvitationRecord.id)).where(
            OrganizationInvitationRecord.organization_id == organization_id,
            OrganizationInvitationRecord.role == "teacher",
            OrganizationInvitationRecord.status == "pending",
            OrganizationInvitationRecord.expires_at > datetime.now(UTC),
        )
    ) or 0
    formations = db.scalar(
        select(func.count(FormationRecord.id)).where(
            FormationRecord.organization_id == organization_id,
            FormationRecord.status == "published",
        )
    ) or 0
    domains = db.scalar(
        select(func.count(OrganizationDomainRecord.id)).where(
            OrganizationDomainRecord.organization_id == organization_id,
            OrganizationDomainRecord.status == "verified",
        )
    ) or 0
    return {
        "students": int(students),
        "teachers": int(teachers) + int(invited),
        "active_formations": int(formations),
        "custom_domain": int(domains),
    }


def addon_for(db: Session, plan: PlanRecord | None, feature_key: str) -> AddonRecord | None:
    """The active add-on that extends this quota on this plan, if any."""
    if plan is None:
        return None
    for addon in db.scalars(select(AddonRecord).where(
        AddonRecord.feature_key == feature_key,
        AddonRecord.status == "active",
        AddonRecord.unit_price_cents.is_not(None),
    ).order_by(AddonRecord.sort_order)):
        if plan.code in (addon.plan_codes or []):
            return addon
    return None


def list_addons(db: Session) -> list[AddonRecord]:
    return list(db.scalars(select(AddonRecord).where(AddonRecord.status != "inactive").order_by(AddonRecord.sort_order)).all())


def extra_units(db: Session, organization_id: int, plan: PlanRecord, current: dict[str, int] | None = None) -> dict[str, int]:
    """Units beyond each quota, for the quotas an add-on extends."""
    current = current or usage(db, organization_id)
    extra = {}
    for feature_key in METERED:
        limit = allowance(plan, feature_key).limit
        if limit is not None and current[feature_key] > limit and addon_for(db, plan, feature_key) is not None:
            extra[feature_key] = current[feature_key] - limit
    return extra


def quote(db: Session, organization_id: int, plan: PlanRecord, billing_interval: str) -> Quote | None:
    """What the school pays for this plan now: the plan, then each add-on beyond its quotas."""
    price = configured_plan_price(plan, billing_interval)
    if price is None:
        return None
    months = MONTHS_BILLED.get(billing_interval, 1)
    lines = [Line(f"Forfait {plan.name} ({'annuel' if billing_interval == 'annual' else 'mensuel'})", 1, price, price)]
    for feature_key, units in extra_units(db, organization_id, plan).items():
        addon = addon_for(db, plan, feature_key)
        unit_amount = addon.unit_price_cents * months
        period = " pour 10 mois" if billing_interval == "annual" else ""
        lines.append(Line(f"{addon.name}{period}", units, unit_amount, unit_amount * units))
    return Quote(currency=plan.currency, lines=lines)


def _plan_offering(db: Session, feature_key: str) -> str | None:
    """The cheapest public plan that includes this feature."""
    plans = [plan for plan in list_public_plans(db) if allowance(plan, feature_key).enabled and plan.entitlements]
    plans.sort(key=lambda plan: plan.monthly_price_cents if plan.monthly_price_cents is not None else 10**12)
    return plans[0].name if plans else None


def require_feature(db: Session, organization_id: int, feature_key: str) -> None:
    """Live classes and custom domains come with some plans only."""
    plan = get_effective_plan(db, organization_id)
    if allowance(plan, feature_key).enabled:
        return
    offering = _plan_offering(db, feature_key)
    where = f"à partir du forfait {offering}" if offering else "dans un forfait supérieur"
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"{FEATURE_LABELS.get(feature_key, 'Cette fonctionnalité')} sont inclus {where}." if feature_key == "live"
        else f"{FEATURE_LABELS.get(feature_key, 'Cette fonctionnalité')} est inclus {where}.",
    )


def format_xaf(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " FCFA"


def require_capacity(
    db: Session,
    organization_id: int,
    feature_key: str,
    *,
    adding: int = 1,
    accept_addon: bool = False,
) -> None:
    """Room for one more teacher or formation, or the school accepts to pay it per unit."""
    plan = get_effective_plan(db, organization_id)
    rule = allowance(plan, feature_key)
    if not rule.enabled:
        require_feature(db, organization_id, feature_key)
    if rule.limit is None:
        return
    current = usage(db, organization_id)[feature_key]
    if current + adding <= rule.limit:
        return
    label = FEATURE_LABELS[feature_key]
    addon = addon_for(db, plan, feature_key)
    if addon is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Votre forfait {plan.name} inclut {rule.limit} {label}. Passez au forfait supérieur pour en ajouter.",
        )
    if accept_addon:
        return
    raise HTTPException(status.HTTP_409_CONFLICT, {
        "code": "addon_required",
        "message": (
            f"Votre forfait {plan.name} inclut {rule.limit} {label}. Chaque {addon.unit_label} en plus coûte "
            f"{format_xaf(addon.unit_price_cents)} par mois, ajouté à votre prochaine facture."
        ),
        "addon": {"code": addon.code, "name": addon.name, "unit_price_cents": addon.unit_price_cents, "currency": addon.currency},
    })


def commission_bps(db: Session, organization_id: int) -> int:
    plan = get_effective_plan(db, organization_id)
    return plan.sales_commission_bps if plan is not None else DEFAULT_COMMISSION_BPS


def notify_student_quotas(db: Session, *, now: datetime | None = None) -> int:
    """Warn a school at 80 % of its students quota, and when it goes beyond, once per period."""
    from app.services.school_notifications import notify_school_managers

    now = now or datetime.now(UTC)
    sent = 0
    subscriptions = db.scalars(select(SubscriptionRecord).where(SubscriptionRecord.status.in_(["trialing", "active", "past_due"]))).all()
    for subscription in subscriptions:
        plan = get_effective_plan(db, subscription.organization_id)
        limit = allowance(plan, "students").limit
        if plan is None or limit is None or limit <= 0:
            continue
        students = usage(db, subscription.organization_id)["students"]
        period = (subscription.current_period_start or subscription.started_at).strftime("%Y%m%d")
        addon = addon_for(db, plan, "students")
        if students > limit:
            extra = students - limit
            cost = f" : {extra} × {format_xaf(addon.unit_price_cents)} sur votre prochaine facture" if addon else ""
            title, message, key = (
                "Quota d'étudiants dépassé",
                f"Votre école compte {students} étudiants actifs pour {limit} inclus dans le forfait {plan.name}{cost}. "
                "Un forfait supérieur peut revenir moins cher.",
                f"quota.students.over:{subscription.organization_id}:{period}",
            )
        elif students >= limit * STUDENT_ALERT_SHARE:
            title, message, key = (
                "Bientôt au bout de votre quota d'étudiants",
                f"Votre école compte {students} étudiants actifs sur les {limit} inclus dans le forfait {plan.name}.",
                f"quota.students.80:{subscription.organization_id}:{period}",
            )
        else:
            continue
        notify_school_managers(
            db, organization_id=subscription.organization_id, event_key=key, title=title, message=message,
            category="billing", tone="warning", action_label="Voir mon abonnement", action_path="/app/manage/billing",
        )
        sent += 1
    db.commit()
    return sent


def billing_usage(db: Session, organization_id: int) -> dict:
    """The school's quotas against what it uses, and what its next payment would be."""
    from app.services.subscriptions import get_current_subscription

    plan = get_effective_plan(db, organization_id)
    subscription = get_current_subscription(db, organization_id)
    interval = subscription.billing_interval if subscription is not None else "monthly"
    current = usage(db, organization_id)
    metrics = []
    for feature_key in METERED:
        rule = allowance(plan, feature_key)
        addon = addon_for(db, plan, feature_key)
        extra = max(0, current[feature_key] - rule.limit) if rule.limit is not None else 0
        unit_price = addon.unit_price_cents if addon is not None else None
        metrics.append({
            "feature_key": feature_key,
            "label": FEATURE_LABELS[feature_key].capitalize(),
            "current": current[feature_key],
            "limit": rule.limit,
            "extra": extra,
            "unit_price_cents": unit_price,
            "extra_amount_cents": extra * (unit_price or 0),
        })
    next_payment = quote(db, organization_id, plan, interval) if plan is not None else None
    return {
        "plan_code": plan.code if plan is not None else None,
        "plan_name": plan.name if plan is not None else None,
        "billing_interval": interval,
        "commission_bps": commission_bps(db, organization_id),
        "live_included": allowance(plan, "live").enabled,
        "custom_domain_included": allowance(plan, "custom_domain").enabled,
        "metrics": metrics,
        "next_payment": (
            {"currency": next_payment.currency, "lines": next_payment.line_dicts(), "total_cents": next_payment.total_cents}
            if next_payment is not None else None
        ),
    }


def admin_update_addon(db: Session, *, actor, code: str, values: dict, reason: str) -> AddonRecord:
    from app.services.admin import _write_admin_audit

    addon = db.scalar(select(AddonRecord).where(AddonRecord.code == code))
    if addon is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Option introuvable.")
    previous = {"name": addon.name, "unit_price_cents": addon.unit_price_cents, "status": addon.status, "plan_codes": addon.plan_codes}
    for key, value in values.items():
        setattr(addon, key, value.strip() if isinstance(value, str) else value)
    if addon.status == "active" and addon.unit_price_cents is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Une option active doit avoir un prix.")
    _write_admin_audit(db, actor=actor, organization_id=None, action="addon.updated", reason=reason,
                       details={"addon": addon.code, "previous": previous,
                                "current": {"name": addon.name, "unit_price_cents": addon.unit_price_cents,
                                            "status": addon.status, "plan_codes": addon.plan_codes}})
    db.commit()
    db.refresh(addon)
    return addon
