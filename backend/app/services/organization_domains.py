from __future__ import annotations

from datetime import UTC, datetime
import re
import secrets
from urllib.parse import urlsplit

import dns.exception
import dns.resolver
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import OrganizationDomainRecord, OrganizationRecord
from app.services.tenancy import TenantContext


RESERVED_SUBDOMAINS = {
    "www",
    "api",
    "app",
    "admin",
    "cdn",
    "static",
    "mail",
    "status",
    "help",
    "support",
    # The SaaS itself and the self-hosted live (infra/live) share the base domain with the schools.
    "ecoles",
    "live",
    "turn",
}
SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_brand_admin(tenant: TenantContext) -> None:
    if tenant.user.platform_role == "super_admin":
        return
    if tenant.organization_role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission insuffisante pour gérer les domaines.",
        )


def normalize_hostname(value: str) -> str:
    raw = value.strip().lower()
    if "://" in raw:
        parsed = urlsplit(raw)
        raw = parsed.hostname or ""
    raw = raw.rstrip(".")
    if ":" in raw and raw.count(":") == 1:
        host, port = raw.rsplit(":", 1)
        if port.isdigit():
            raw = host
    if not raw or "/" in raw or " " in raw or len(raw) > 253:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nom de domaine invalide.",
        )
    labels = raw.split(".")
    if len(labels) < 2 or any(
        not SUBDOMAIN_RE.fullmatch(label) for label in labels
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nom de domaine invalide.",
        )
    return raw


def update_subdomain(
    db: Session,
    tenant: TenantContext,
    *,
    subdomain: str | None,
) -> OrganizationRecord:
    _require_brand_admin(tenant)

    normalized = subdomain.strip().lower() if subdomain else None
    if normalized:
        if not SUBDOMAIN_RE.fullmatch(normalized):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Sous-domaine invalide.",
            )
        if normalized in RESERVED_SUBDOMAINS or normalized in settings.saas_reserved_subdomains:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce sous-domaine est réservé.",
            )
        conflict = db.scalar(
            select(OrganizationRecord).where(
                OrganizationRecord.subdomain == normalized,
                OrganizationRecord.id != tenant.organization_id,
            )
        )
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ce sous-domaine est déjà utilisé.",
            )

    tenant.organization.subdomain = normalized
    db.commit()
    db.refresh(tenant.organization)
    return tenant.organization


def list_domains(
    db: Session,
    tenant: TenantContext,
) -> list[OrganizationDomainRecord]:
    _require_brand_admin(tenant)
    return list(
        db.scalars(
            select(OrganizationDomainRecord)
            .where(
                OrganizationDomainRecord.organization_id
                == tenant.organization_id
            )
            .order_by(
                OrganizationDomainRecord.is_primary.desc(),
                OrganizationDomainRecord.created_at.desc(),
            )
        ).all()
    )


def create_domain(
    db: Session,
    tenant: TenantContext,
    *,
    hostname: str,
) -> OrganizationDomainRecord:
    _require_brand_admin(tenant)
    normalized = normalize_hostname(hostname)

    if settings.saas_base_domain and (
        normalized == settings.saas_base_domain
        or normalized.endswith(f".{settings.saas_base_domain}")
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Utilisez le champ sous-domaine pour le domaine SaaS.",
        )

    existing = db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.hostname == normalized
        )
    )
    if existing is not None:
        if existing.organization_id == tenant.organization_id:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce domaine est déjà rattaché à une autre école.",
        )

    domain = OrganizationDomainRecord(
        organization_id=tenant.organization_id,
        hostname=normalized,
        status="pending",
        verification_token=secrets.token_urlsafe(32),
        is_primary=False,
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


def _txt_values(record_name: str) -> set[str]:
    try:
        answers = dns.resolver.resolve(record_name, "TXT", lifetime=5)
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return set()

    values: set[str] = set()
    for answer in answers:
        strings = getattr(answer, "strings", None)
        if strings:
            joined = b"".join(strings).decode("utf-8", errors="ignore")
        else:
            joined = str(answer).strip('"')
        values.add(joined.strip())
    return values


def verify_domain(
    db: Session,
    tenant: TenantContext,
    *,
    domain_id: int,
) -> OrganizationDomainRecord:
    _require_brand_admin(tenant)
    domain = db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.id == domain_id,
            OrganizationDomainRecord.organization_id == tenant.organization_id,
        )
    )
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domaine introuvable.",
        )

    record_name = f"_academie-verification.{domain.hostname}"
    values = _txt_values(record_name)
    if domain.verification_token not in values:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Le TXT de vérification n'est pas encore visible. "
                "Vérifiez le DNS puis réessayez."
            ),
        )

    domain.status = "verified"
    domain.verified_at = _utc_now()
    db.commit()
    db.refresh(domain)
    return domain


def set_primary_domain(
    db: Session,
    tenant: TenantContext,
    *,
    domain_id: int,
) -> OrganizationDomainRecord:
    _require_brand_admin(tenant)
    domain = db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.id == domain_id,
            OrganizationDomainRecord.organization_id == tenant.organization_id,
        )
    )
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domaine introuvable.",
        )
    if domain.status != "verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vérifiez d'abord ce domaine.",
        )

    domains = list(
        db.scalars(
            select(OrganizationDomainRecord).where(
                OrganizationDomainRecord.organization_id == tenant.organization_id
            )
        ).all()
    )
    for item in domains:
        item.is_primary = item.id == domain.id
        db.add(item)
    db.commit()
    db.refresh(domain)
    return domain


def delete_domain(
    db: Session,
    tenant: TenantContext,
    *,
    domain_id: int,
) -> None:
    _require_brand_admin(tenant)
    domain = db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.id == domain_id,
            OrganizationDomainRecord.organization_id == tenant.organization_id,
        )
    )
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domaine introuvable.",
        )
    db.delete(domain)
    db.commit()


def resolve_organization_for_hostname(
    db: Session,
    *,
    hostname: str,
) -> tuple[OrganizationRecord, str] | None:
    normalized = normalize_hostname(hostname)

    if settings.saas_base_domain and normalized.endswith(
        f".{settings.saas_base_domain}"
    ):
        prefix = normalized[: -(len(settings.saas_base_domain) + 1)]
        if "." not in prefix and prefix:
            organization = db.scalar(
                select(OrganizationRecord).where(
                    OrganizationRecord.subdomain == prefix,
                    OrganizationRecord.is_active.is_(True),
                    OrganizationRecord.status == "active",
                )
            )
            if organization is not None:
                return organization, normalized

    domain = db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.hostname == normalized,
            OrganizationDomainRecord.status == "verified",
        )
    )
    if domain is None:
        return None

    organization = db.scalar(
        select(OrganizationRecord).where(
            OrganizationRecord.id == domain.organization_id,
            OrganizationRecord.is_active.is_(True),
            OrganizationRecord.status == "active",
        )
    )
    if organization is None:
        return None
    return organization, normalized
