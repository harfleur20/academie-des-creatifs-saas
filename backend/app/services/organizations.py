from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)
from app.schemas.organizations import OrganizationCreate
from app.services.subscriptions import start_default_trial


class OrganizationConflictError(ValueError):
    pass


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
                OrganizationRecord.status == "active",
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
    organization = OrganizationRecord(
        name=payload.name.strip(),
        slug=payload.slug.strip().lower(),
    )
    db.add(organization)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise OrganizationConflictError(
            "Ce slug d'organisation est déjà utilisé."
        ) from exc

    db.add(
        OrganizationMemberRecord(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
            status="active",
        )
    )
    start_default_trial(
        db,
        organization_id=organization.id,
    )
    db.commit()
    db.refresh(organization)
    return organization
