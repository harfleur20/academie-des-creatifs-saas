from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import OrganizationMemberRecord, OrganizationMemberRoleRecord


FUNCTIONAL_ROLES = {"teacher", "student"}
MANAGEMENT_ROLES = {"owner", "admin", "manager"}


def effective_member_roles(
    member: OrganizationMemberRecord,
) -> frozenset[str]:
    values = {member.role}
    values.update(item.role for item in getattr(member, "roles", []) or [])
    return frozenset(values)


def load_effective_member_roles(
    db: Session,
    member: OrganizationMemberRecord,
) -> frozenset[str]:
    values = {member.role}
    values.update(
        db.scalars(
            select(OrganizationMemberRoleRecord.role).where(
                OrganizationMemberRoleRecord.member_id == member.id,
                OrganizationMemberRoleRecord.organization_id == member.organization_id,
            )
        ).all()
    )
    return frozenset(values)


def member_has_role(
    db: Session,
    member: OrganizationMemberRecord,
    role: str,
) -> bool:
    if member.role == role:
        return True
    return (
        db.scalar(
            select(OrganizationMemberRoleRecord.id).where(
                OrganizationMemberRoleRecord.member_id == member.id,
                OrganizationMemberRoleRecord.organization_id == member.organization_id,
                OrganizationMemberRoleRecord.role == role,
            )
        )
        is not None
    )


def replace_effective_roles(
    db: Session,
    member: OrganizationMemberRecord,
    roles: set[str],
) -> None:
    target = set(roles)
    target.add(member.role)
    db.execute(
        delete(OrganizationMemberRoleRecord).where(
            OrganizationMemberRoleRecord.member_id == member.id,
            OrganizationMemberRoleRecord.organization_id == member.organization_id,
            OrganizationMemberRoleRecord.role.notin_(sorted(target)),
        )
    )
    current = set(
        db.scalars(
            select(OrganizationMemberRoleRecord.role).where(
                OrganizationMemberRoleRecord.member_id == member.id,
                OrganizationMemberRoleRecord.organization_id == member.organization_id,
            )
        ).all()
    )
    for role in sorted(target - current):
        db.add(
            OrganizationMemberRoleRecord(
                organization_id=member.organization_id,
                member_id=member.id,
                role=role,
            )
        )


def sync_primary_role(
    db: Session,
    member: OrganizationMemberRecord,
    *,
    previous_primary_role: str | None = None,
) -> None:
    existing = load_effective_member_roles(db, member)
    functional = {role for role in existing if role in FUNCTIONAL_ROLES}
    if previous_primary_role in FUNCTIONAL_ROLES and previous_primary_role != member.role:
        functional.add(previous_primary_role)
    replace_effective_roles(db, member, {member.role, *functional})


def replace_functional_roles(
    db: Session,
    member: OrganizationMemberRecord,
    functional_roles: set[str],
) -> None:
    invalid = set(functional_roles) - FUNCTIONAL_ROLES
    if invalid:
        raise ValueError("Unsupported functional roles: " + ", ".join(sorted(invalid)))
    replace_effective_roles(
        db,
        member,
        {member.role, *functional_roles},
    )
