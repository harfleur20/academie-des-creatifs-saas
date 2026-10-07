from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import OrganizationRecord
from app.models.organization_slug_alias import OrganizationSlugAliasRecord


def public_slug_from_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:120]


def _slug_conflicts(
    db: Session,
    *,
    slug: str,
    organization_id: int,
) -> bool:
    current = db.scalar(
        select(OrganizationRecord.id).where(
            func.lower(OrganizationRecord.slug) == slug.lower(),
            OrganizationRecord.id != organization_id,
        )
    )
    if current is not None:
        return True
    alias = db.scalar(
        select(OrganizationSlugAliasRecord.organization_id).where(
            func.lower(OrganizationSlugAliasRecord.slug) == slug.lower(),
            OrganizationSlugAliasRecord.organization_id != organization_id,
        )
    )
    return alias is not None


def ensure_canonical_public_slug(
    db: Session,
    org: OrganizationRecord,
    public_name: str,
) -> str:
    base = public_slug_from_name(public_name)
    if not base:
        return org.slug

    candidate = base
    suffix = 1
    while _slug_conflicts(db, slug=candidate, organization_id=org.id):
        suffix += 1
        marker = f"-{suffix}"
        candidate = f"{base[:120-len(marker)]}{marker}"

    if candidate == org.slug:
        return org.slug

    old_slug = org.slug
    existing_old_alias = db.scalar(
        select(OrganizationSlugAliasRecord).where(
            OrganizationSlugAliasRecord.organization_id == org.id,
            func.lower(OrganizationSlugAliasRecord.slug) == old_slug.lower(),
        )
    )
    if existing_old_alias is None:
        db.add(
            OrganizationSlugAliasRecord(
                organization_id=org.id,
                slug=old_slug,
            )
        )

    own_candidate_alias = db.scalar(
        select(OrganizationSlugAliasRecord).where(
            OrganizationSlugAliasRecord.organization_id == org.id,
            func.lower(OrganizationSlugAliasRecord.slug) == candidate.lower(),
        )
    )
    if own_candidate_alias is not None:
        db.delete(own_candidate_alias)
        db.flush()

    org.slug = candidate
    db.flush()
    return candidate


def resolve_public_organization(
    db: Session,
    school_key: str,
) -> OrganizationRecord | None:
    key = school_key.strip().lower()
    org = db.scalar(
        select(OrganizationRecord).where(
            or_(
                func.lower(OrganizationRecord.slug) == key,
                func.lower(OrganizationRecord.subdomain) == key,
            ),
            OrganizationRecord.is_active.is_(True),
            OrganizationRecord.status == "active",
        )
    )
    if org is not None:
        return org

    alias = db.scalar(
        select(OrganizationSlugAliasRecord).where(
            func.lower(OrganizationSlugAliasRecord.slug) == key,
        )
    )
    if alias is None:
        return None

    return db.scalar(
        select(OrganizationRecord).where(
            OrganizationRecord.id == alias.organization_id,
            OrganizationRecord.is_active.is_(True),
            OrganizationRecord.status == "active",
        )
    )
