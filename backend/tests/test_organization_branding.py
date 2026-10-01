from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import OrganizationMemberRecord, OrganizationRecord, UserRecord
from app.schemas.organizations import OrganizationUpdate
from app.services.organization_management import update_organization_settings
from app.services.tenancy import resolve_tenant_context


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed_owner(db: Session):
    user = UserRecord(
        email="owner@example.test",
        full_name="Owner",
        status="active",
    )
    org = OrganizationRecord(name="School", slug="school")
    db.add_all([user, org])
    db.flush()
    db.add(
        OrganizationMemberRecord(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            status="active",
        )
    )
    db.commit()
    tenant = resolve_tenant_context(db, user=user, organization_id=org.id)
    return org, tenant


def test_owner_can_update_white_label_branding() -> None:
    db = build_db()
    org, tenant = seed_owner(db)

    updated = update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(
            logo_url="https://cdn.example.test/school-logo.png",
            primary_color="#1122AA",
            secondary_color="#11AA77",
            accent_color="#101828",
        ),
    )

    assert updated.id == org.id
    assert updated.logo_url == "https://cdn.example.test/school-logo.png"
    assert updated.primary_color == "#1122AA"
    assert updated.secondary_color == "#11AA77"
    assert updated.accent_color == "#101828"


def test_brand_colors_are_normalized_to_uppercase() -> None:
    db = build_db()
    _, tenant = seed_owner(db)

    updated = update_organization_settings(
        db,
        tenant,
        OrganizationUpdate(
            primary_color="#abcdef",
            secondary_color="#123abc",
            accent_color="#0a0b0c",
        ),
    )

    assert updated.primary_color == "#ABCDEF"
    assert updated.secondary_color == "#123ABC"
    assert updated.accent_color == "#0A0B0C"
