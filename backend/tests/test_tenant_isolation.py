from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    FormationRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.formations import get_formation, list_formations
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed_two_organizations(db: Session):
    alice = UserRecord(email="alice@example.test", full_name="Alice", status="active")
    bob = UserRecord(email="bob@example.test", full_name="Bob", status="active")
    org_a = OrganizationRecord(name="École A", slug="ecole-a")
    org_b = OrganizationRecord(name="École B", slug="ecole-b")
    db.add_all([alice, bob, org_a, org_b])
    db.flush()

    db.add_all(
        [
            OrganizationMemberRecord(
                organization_id=org_a.id,
                user_id=alice.id,
                role="owner",
                status="active",
            ),
            OrganizationMemberRecord(
                organization_id=org_b.id,
                user_id=bob.id,
                role="owner",
                status="active",
            ),
        ]
    )
    formation_a = FormationRecord(
        organization_id=org_a.id,
        slug="design-a",
        title="Formation A",
    )
    formation_b = FormationRecord(
        organization_id=org_b.id,
        slug="design-b",
        title="Formation B",
    )
    db.add_all([formation_a, formation_b])
    db.commit()
    return alice, bob, org_a, org_b, formation_a, formation_b


def test_member_cannot_resolve_another_organization() -> None:
    db = build_db()
    alice, _, _, org_b, _, _ = seed_two_organizations(db)

    try:
        resolve_tenant_context(db, user=alice, organization_id=org_b.id)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Cross-tenant access should have been rejected")


def test_formation_listing_is_scoped_to_active_organization() -> None:
    db = build_db()
    alice, _, org_a, _, formation_a, formation_b = seed_two_organizations(db)

    tenant = resolve_tenant_context(db, user=alice, organization_id=org_a.id)
    formations = list_formations(db, tenant)

    assert [item.id for item in formations] == [formation_a.id]
    assert formation_b.id not in [item.id for item in formations]


def test_direct_object_lookup_cannot_cross_tenant_boundary() -> None:
    db = build_db()
    alice, _, org_a, _, _, formation_b = seed_two_organizations(db)

    tenant = resolve_tenant_context(db, user=alice, organization_id=org_a.id)

    assert get_formation(db, tenant, formation_b.id) is None


def test_super_admin_can_resolve_any_organization() -> None:
    db = build_db()
    _, _, _, org_b, _, _ = seed_two_organizations(db)
    root = UserRecord(
        email="root@example.test",
        full_name="Root",
        status="active",
        platform_role="super_admin",
    )
    db.add(root)
    db.commit()

    tenant = resolve_tenant_context(db, user=root, organization_id=org_b.id)

    assert tenant.organization_id == org_b.id
    assert tenant.organization_role == "super_admin"
