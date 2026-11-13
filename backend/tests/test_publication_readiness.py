from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import EnrollmentRecord, OrganizationInvitationRecord, OrganizationMemberRecord, OrganizationRecord, SchoolNotificationRecord, UserRecord
from app.schemas.commerce import CheckoutCreate, SchoolIdentityPayload
from app.schemas.formations import FormationCreate, FormationUpdate, SessionCreate, SessionUpdate
from app.services.formations import create_formation, create_session, get_formation_detail, update_formation, update_session
from app.services.public_catalog import public_formation_detail, public_school_read
from app.services.publication import valid_cover_url
from app.services.school_branding import get_school_identity, update_school_identity
from app.services.school_commerce import price_preview
from app.services.school_commerce import confirm_demo_checkout, create_checkout
from app.core.config import settings
from app.services.tenancy import resolve_tenant_context


def owner_school():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    owner = UserRecord(email="owner@school.test", full_name="Owner", status="active")
    org = OrganizationRecord(name="School", slug="school", status="active", is_active=True, contact_email="contact@example.com", subdomain="school")
    db.add_all([owner, org])
    db.flush()
    db.add_all([
        OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active"),
        OrganizationInvitationRecord(organization_id=org.id, email="teacher@example.com", role="teacher", token_hash="x" * 64, status="pending", expires_at=datetime.now(UTC) + timedelta(days=7)),
    ])
    db.commit()
    return db, org, owner, resolve_tenant_context(db, user=owner, organization_id=org.id)


def publish_site(db, tenant):
    identity = get_school_identity(db, tenant)
    assert identity.public_site.is_published is False
    payload = SchoolIdentityPayload.model_validate(identity.model_dump())
    payload.public_site.is_published = True
    with pytest.raises(HTTPException) as exc:
        update_school_identity(db, tenant, payload)
    assert exc.value.status_code == 422

    payload.public_site.student_code_prefix_confirmed = True
    payload.public_site.legal_notice = "Mentions légales"
    payload.public_site.sales_terms = "Conditions de vente"
    payload.public_site.privacy_policy = "Politique de confidentialité"
    payload.public_site.refund_policy = "Politique de remboursement"
    with pytest.raises(HTTPException) as exc:
        update_school_identity(db, tenant, payload)
    assert exc.value.status_code == 422
    assert "factures" in exc.value.detail

    payload.legal.legal_name = "School SARL"
    payload.legal.legal_address = "12 rue des écoles, Paris"
    payload.legal.invoice_email = "factures@example.com"
    assert update_school_identity(db, tenant, payload).public_site.is_published is True


def test_school_announcement_is_editable_and_public_only_when_configured():
    db, org, _owner, tenant = owner_school()
    publish_site(db, tenant)

    initial = public_school_read(db, org)
    assert initial.announcement_enabled is False
    assert initial.announcement_text == ""
    assert initial.announcement_background_color == "#FFF4E7"
    assert initial.announcement_text_color == "#7C4200"

    payload = SchoolIdentityPayload.model_validate(get_school_identity(db, tenant).model_dump())
    payload.public_site.announcement_enabled = True
    with pytest.raises(HTTPException) as exc:
        update_school_identity(db, tenant, payload)
    assert exc.value.status_code == 422

    payload.public_site.announcement_text = "  Inscriptions ouvertes pour la prochaine session  "
    payload.public_site.announcement_background_color = "#fff4e7"
    payload.public_site.announcement_text_color = "#7c4200"
    updated = update_school_identity(db, tenant, payload)
    assert updated.public_site.announcement_text == "Inscriptions ouvertes pour la prochaine session"
    public = public_school_read(db, org)
    assert public.announcement_enabled is True
    assert public.announcement_text == updated.public_site.announcement_text
    assert public.announcement_background_color == "#FFF4E7"
    assert public.announcement_text_color == "#7C4200"

    other_org = OrganizationRecord(name="Other school", slug="other-school", status="active", is_active=True, contact_email="other@example.com", subdomain="other-school")
    db.add(other_org)
    db.flush()
    db.add(OrganizationMemberRecord(organization_id=other_org.id, user_id=_owner.id, role="owner", status="active"))
    db.commit()
    other_tenant = resolve_tenant_context(db, user=_owner, organization_id=other_org.id)
    publish_site(db, other_tenant)
    other_public = public_school_read(db, other_org)
    assert other_public.announcement_enabled is False
    assert other_public.announcement_text == ""


def test_publication_requires_presentation_price_and_session_then_opens_enrollment():
    db, org, owner, tenant = owner_school()
    publish_site(db, tenant)
    formation = create_formation(db, tenant, FormationCreate(
        slug="motion-design", title="Motion Design", description="Apprendre le motion design", format_type="live",
    ))
    assert len(formation.publication_issues) == 4
    with pytest.raises(HTTPException) as exc:
        update_formation(db, tenant, formation.id, FormationUpdate(status="published"))
    assert exc.value.status_code == 422

    today = datetime.now(UTC).date()
    detail = create_session(db, tenant, formation.id, SessionCreate(
        label="Cohorte automne", start_date=today + timedelta(days=10), end_date=today + timedelta(days=40), seat_capacity=10,
    ))
    session = detail.sessions[0]
    assert session.status == "planned"
    with pytest.raises(HTTPException) as exc:
        update_session(db, tenant, formation.id, session.id, SessionUpdate(status="open"))
    assert exc.value.status_code == 422

    video = f"{settings.backend_public_url}/uploads/schools/{org.id}/presentations/{'a' * 32}.mp4"
    update_formation(db, tenant, formation.id, FormationUpdate(
        cover_image_url="https://example.test/cover.jpg", price_cents=150_000,
        presentation_video_url=video,
        public_program="Module 1 : les bases du mouvement",
    ))
    published = update_formation(db, tenant, formation.id, FormationUpdate(status="published"))
    assert published.publication_issues == []
    with pytest.raises(HTTPException) as exc:
        update_formation(db, tenant, formation.id, FormationUpdate(price_cents=0))
    assert exc.value.status_code == 422
    public = public_formation_detail(db, org.slug, formation.slug)
    assert public.presentation_video_url == video
    assert len(public.sessions) == 1
    assert public.sessions[0].can_purchase is False
    assert public.sessions[0].unavailable_reason

    update_session(db, tenant, formation.id, session.id, SessionUpdate(status="open"))
    public = public_formation_detail(db, org.slug, formation.slug)
    assert public.sessions[0].can_purchase is True
    assert price_preview(db, org, user_id=owner.id, session_id=session.id).base_price_cents == 150_000

    with pytest.raises(HTTPException) as exc:
        update_session(db, tenant, formation.id, session.id, SessionUpdate(price_override_cents=0))
    assert exc.value.status_code == 422
    update_session(db, tenant, formation.id, session.id, SessionUpdate(status="planned"))
    assert public_formation_detail(db, org.slug, formation.slug).sessions[0].can_purchase is False


def test_legacy_zero_price_publication_is_not_sold():
    db, org, owner, tenant = owner_school()
    publish_site(db, tenant)
    formation = create_formation(db, tenant, FormationCreate(
        slug="legacy", title="Legacy", description="Programme historique", format_type="live",
    ))
    today = datetime.now(UTC).date()
    detail = create_session(db, tenant, formation.id, SessionCreate(
        label="Cohorte historique", start_date=today + timedelta(days=1), end_date=today + timedelta(days=30), seat_capacity=10,
    ))
    # Simulate a record published before the validation rules existed.
    from app.models.entities import FormationRecord, FormationSessionRecord
    db.get(FormationRecord, formation.id).status = "published"
    db.get(FormationSessionRecord, detail.sessions[0].id).status = "open"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        public_formation_detail(db, org.slug, formation.slug)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        price_preview(db, org, user_id=owner.id, session_id=detail.sessions[0].id)
    assert exc.value.status_code == 409


def test_cover_requires_an_image_url():
    assert valid_cover_url("https://example.test/cover.webp?size=large")
    assert not valid_cover_url("https://example.test/brochure.pdf")
    assert not valid_cover_url("http://[invalid/cover.jpg")


def test_online_formation_sells_without_a_public_session(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)
    db, org, owner, tenant = owner_school()
    publish_site(db, tenant)
    formation = create_formation(db, tenant, FormationCreate(
        slug="design-en-ligne", title="Design en ligne", format_type="ligne",
        description="Formation à votre rythme", cover_image_url="https://example.test/design.jpg",
        public_program="Modules de design", price_cents=100_000,
    ))
    assert formation.session_count == 0
    assert formation.publication_issues == []
    assert [session.label for session in get_formation_detail(db, tenant, formation.id).sessions] == ["Accès en ligne"]
    update_formation(db, tenant, formation.id, FormationUpdate(status="published"))
    detail = public_formation_detail(db, org.slug, formation.slug)
    assert detail.sessions == []
    assert detail.can_purchase is True
    assert detail.next_session is not None
    session_id = detail.next_session.id
    assert price_preview(db, org, user_id=owner.id, session_id=session_id).base_price_cents == 100_000

    order = create_checkout(db, org, owner, CheckoutCreate(session_id=session_id))
    assert order.status == "pending"
    paid = confirm_demo_checkout(db, org, owner, order.order_id)
    assert paid.status == "paid"
    titles = [row.title for row in db.query(SchoolNotificationRecord).filter_by(organization_id=org.id, user_id=owner.id).all()]
    assert "Paiement confirmé" in titles
    assert "Nouvelle inscription" in titles
    assert db.query(EnrollmentRecord).filter_by(organization_id=org.id, session_id=session_id, student_id=owner.id).one().status == "active"
    update_session(db, tenant, formation.id, session_id, SessionUpdate(status="cancelled"))
    assert public_formation_detail(db, org.slug, formation.slug).can_purchase is False
    with pytest.raises(HTTPException) as exc:
        price_preview(db, org, user_id=owner.id, session_id=session_id)
    assert exc.value.status_code == 409
