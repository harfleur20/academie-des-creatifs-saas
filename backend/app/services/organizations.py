from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationMemberRoleRecord,
    OrganizationRecord,
    UserRecord,
)
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationCreationCapacityRead,
)
from app.services.membership_roles import replace_effective_roles
from app.services.subscriptions import get_effective_plan, start_default_trial


class OrganizationConflictError(ValueError):
    pass


class OrganizationLimitError(ValueError):
    pass


def _owned_organization_ids(db: Session, user_id: int) -> list[int]:
    effective_owner_role = select(OrganizationMemberRoleRecord.id).where(
        OrganizationMemberRoleRecord.member_id == OrganizationMemberRecord.id,
        OrganizationMemberRoleRecord.role == "owner",
    ).exists()
    return list(
        db.scalars(
            select(OrganizationMemberRecord.organization_id)
            .where(
                OrganizationMemberRecord.user_id == user_id,
                OrganizationMemberRecord.status == "active",
                or_(OrganizationMemberRecord.role == "owner", effective_owner_role),
                OrganizationMemberRecord.organization_id.in_(
                    select(OrganizationRecord.id).where(
                        OrganizationRecord.status != "deletion_pending"
                    )
                ),
            )
            .distinct()
        ).all()
    )


def get_organization_creation_capacity(
    db: Session,
    user: UserRecord,
) -> OrganizationCreationCapacityRead:
    owned_ids = _owned_organization_ids(db, user.id)
    if user.platform_role == "super_admin":
        return OrganizationCreationCapacityRead(
            owned_organizations=len(owned_ids),
            maximum_organizations=None,
            can_create=True,
        )

    maximum = 1
    maximum_is_unlimited = False
    best_plan_code: str | None = None
    best_plan_name: str | None = None
    has_owned_plan = False

    for organization_id in owned_ids:
        plan = get_effective_plan(db, organization_id)
        if plan is None:
            continue
        entitlement = next(
            (item for item in plan.entitlements if item.feature_key == "organizations"),
            None,
        )
        candidate = (
            entitlement.limit_value
            if entitlement is not None and entitlement.enabled
            else 1
        )
        candidate_is_unlimited = candidate is None
        if (
            not has_owned_plan
            or (candidate_is_unlimited and not maximum_is_unlimited)
            or (
                not candidate_is_unlimited
                and not maximum_is_unlimited
                and candidate > maximum
            )
        ):
            maximum = candidate if candidate is not None else 0
            maximum_is_unlimited = candidate_is_unlimited
            best_plan_code = plan.code
            best_plan_name = plan.name
            has_owned_plan = True

    maximum_value = None if maximum_is_unlimited else maximum
    return OrganizationCreationCapacityRead(
        owned_organizations=len(owned_ids),
        maximum_organizations=maximum_value,
        can_create=maximum_value is None or len(owned_ids) < maximum_value,
        plan_code=best_plan_code,
        plan_name=best_plan_name,
    )


def list_user_organizations(
    db: Session,
    user: UserRecord,
) -> list[OrganizationRecord]:
    if user.platform_role == "super_admin":
        return list(
            db.scalars(
                select(OrganizationRecord).order_by(OrganizationRecord.name)
            ).all()
        )

    return list(
        db.scalars(
            select(OrganizationRecord)
            .join(
                OrganizationMemberRecord,
                OrganizationMemberRecord.organization_id == OrganizationRecord.id,
            )
            .where(
                OrganizationMemberRecord.user_id == user.id,
                OrganizationMemberRecord.status == "active",
                OrganizationRecord.is_active.is_(True),
                or_(
                    OrganizationRecord.status == "active",
                    and_(
                        OrganizationRecord.status == "deletion_pending",
                        or_(
                            OrganizationMemberRecord.role == "owner",
                            select(OrganizationMemberRoleRecord.id)
                            .where(
                                OrganizationMemberRoleRecord.member_id
                                == OrganizationMemberRecord.id,
                                OrganizationMemberRoleRecord.role == "owner",
                            )
                            .exists(),
                        ),
                    ),
                ),
            )
            .order_by(OrganizationRecord.name)
        ).all()
    )


def create_organization(
    db: Session,
    *,
    user: UserRecord,
    payload: OrganizationCreate,
) -> OrganizationRecord:
    capacity = get_organization_creation_capacity(db, user)
    if not capacity.can_create:
        plan_label = f" du forfait {capacity.plan_name}" if capacity.plan_name else ""
        raise OrganizationLimitError(
            f"Votre forfait{plan_label} autorise jusqu’à "
            f"{capacity.maximum_organizations} école(s). Passez au forfait supérieur "
            "pour en créer une autre."
        )

    # Serialize simultaneous creates for the same account before the final count.
    db.scalar(select(UserRecord.id).where(UserRecord.id == user.id).with_for_update())
    owned_count = len(_owned_organization_ids(db, user.id))
    if (
        capacity.maximum_organizations is not None
        and owned_count >= capacity.maximum_organizations
    ):
        plan_label = f" du forfait {capacity.plan_name}" if capacity.plan_name else ""
        raise OrganizationLimitError(
            f"Votre forfait{plan_label} autorise jusqu’à "
            f"{capacity.maximum_organizations} école(s). Passez au forfait supérieur "
            "pour en créer une autre."
        )

    organization = OrganizationRecord(
        name=payload.name.strip(),
        slug=payload.slug.strip().lower(),
        timezone=payload.timezone or "UTC",
    )
    db.add(organization)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise OrganizationConflictError(
            "Ce slug d'organisation est déjà utilisé."
        ) from exc

    member = OrganizationMemberRecord(
        organization_id=organization.id,
        user_id=user.id,
        role="owner",
        status="active",
    )
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"owner"})
    start_default_trial(
        db,
        organization_id=organization.id,
        chosen_plan_code=payload.plan_code,
        chosen_billing_interval=payload.billing_interval,
    )
    db.commit()
    db.refresh(organization)
    return organization
