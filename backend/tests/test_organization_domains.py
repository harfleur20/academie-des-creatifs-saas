import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.entities import OrganizationMemberRecord, OrganizationRecord, UserRecord
from app.services import organization_domains
from app.services.organization_domains import (
    create_domain,
    resolve_organization_for_hostname,
    set_primary_domain,
    update_subdomain,
    verify_domain,
)
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session):
    owner = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([owner, org])
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
    )
    db.commit()
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    return org, tenant


def test_unique_subdomain_can_be_configured() -> None:
    db = build_db()
    org, tenant = seed(db)

    updated = update_subdomain(db, tenant, subdomain="studio-creatif")
    assert updated.id == org.id
    assert updated.subdomain == "studio-creatif"


def test_reserved_subdomain_is_rejected() -> None:
    db = build_db()
    _, tenant = seed(db)

    with pytest.raises(HTTPException) as exc:
        update_subdomain(db, tenant, subdomain="admin")

    assert exc.value.status_code == 409


def test_custom_domain_verification_uses_txt(monkeypatch) -> None:
    db = build_db()
    _, tenant = seed(db)
    domain = create_domain(db, tenant, hostname="formation.example.com")

    monkeypatch.setattr(
        organization_domains,
        "_txt_values",
        lambda record_name: {domain.verification_token},
    )

    verified = verify_domain(db, tenant, domain_id=domain.id)
    assert verified.status == "verified"
    assert verified.verified_at is not None

    primary = set_primary_domain(db, tenant, domain_id=domain.id)
    assert primary.is_primary is True


def test_verified_custom_domain_resolves_brand() -> None:
    db = build_db()
    org, tenant = seed(db)
    org.logo_url = "https://cdn.example.test/logo.png"
    org.primary_color = "#1122AA"
    domain = create_domain(db, tenant, hostname="school.example.com")
    domain.status = "verified"
    db.commit()

    resolved = resolve_organization_for_hostname(
        db,
        hostname="school.example.com",
    )
    assert resolved is not None
    resolved_org, hostname = resolved
    assert resolved_org.id == org.id
    assert hostname == "school.example.com"


def test_platform_subdomain_resolves_brand(monkeypatch) -> None:
    db = build_db()
    org, tenant = seed(db)
    monkeypatch.setattr(settings, "saas_base_domain", "schools.example.test")

    update_subdomain(db, tenant, subdomain="creatifs")

    resolved = resolve_organization_for_hostname(
        db,
        hostname="creatifs.schools.example.test",
    )
    assert resolved is not None
    assert resolved[0].id == org.id
