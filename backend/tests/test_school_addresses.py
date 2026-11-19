"""A school's links open on its own address, and its emails and documents carry its name."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    CertificateRecord,
    CommunicationOutboxRecord,
    OrganizationLegalProfileRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    UserRecord,
)
from app.schemas.organizations import OrganizationInvitationCreate
from app.services import school_documents
from app.services.communication_delivery import _email_html
from app.services.membership_roles import replace_effective_roles
from app.services.organization_domains import school_base_url
from app.services.organization_management import create_invitation, get_invitation_preview
from app.services.password_reset_mail import _password_reset_html
from app.services.tenancy import resolve_tenant_context


@pytest.fixture
def production_addresses(monkeypatch):
    monkeypatch.setattr(settings, "saas_base_domain", "academiecreatif.com")
    monkeypatch.setattr(settings, "frontend_url", "https://ecoles.academiecreatif.com")


def build_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine, autoflush=False, expire_on_commit=False)


def school(db: Session, *, subdomain: str | None = "millenium") -> OrganizationRecord:
    org = OrganizationRecord(name="Millenium", slug="millenium-school", subdomain=subdomain, contact_email="contact@ecole.dev",
                             logo_url="https://cdn.test/logo.png", primary_color="#123456", status="active", is_active=True)
    db.add(org)
    db.flush()
    db.add(OrganizationPublicSiteRecord(organization_id=org.id, site_name="Millenium school", favicon_url="https://cdn.test/favicon.png",
                                        student_code_prefix="MS", student_code_prefix_confirmed_at=datetime.now(UTC)))
    db.add(OrganizationLegalProfileRecord(organization_id=org.id, legal_name="Millenium SARL", legal_address="Douala",
                                          invoice_email="factures@ecole.dev", default_currency="XAF"))
    db.commit()
    return org


def test_a_school_address_is_its_subdomain_in_production_only(production_addresses, monkeypatch) -> None:
    db = build_db()
    assert school_base_url(school(db)) == "https://millenium.academiecreatif.com"
    other = OrganizationRecord(name="Sans", slug="sans", status="active", is_active=True)
    assert school_base_url(other) == "https://ecoles.academiecreatif.com"
    # A local app naming the production domain serves no subdomain: the platform's address.
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")
    assert school_base_url(school(build_db())) == "http://localhost:3000"


def test_an_invitation_opens_on_the_school_and_names_it(production_addresses, monkeypatch) -> None:
    db = build_db()
    org = school(db)
    owner = UserRecord(email="owner@ecole.dev", full_name="Owner", status="active")
    db.add(owner)
    db.flush()
    member = OrganizationMemberRecord(organization_id=org.id, user_id=owner.id, role="owner", status="active")
    db.add(member)
    db.flush()
    replace_effective_roles(db, member, {"owner"})
    db.commit()
    monkeypatch.setattr("app.services.organization_management.require_teacher_invitation_readiness", lambda *args, **kwargs: None)
    tenant = resolve_tenant_context(db, user=owner, organization_id=org.id)
    _invitation, token = create_invitation(db, tenant, OrganizationInvitationCreate(email="prof@ecole.dev", role="teacher"))

    message = db.scalar(select(CommunicationOutboxRecord).where(CommunicationOutboxRecord.event_key == "school.team.invitation"))
    assert f"https://millenium.academiecreatif.com/invite/{token}" in message.body

    preview = get_invitation_preview(db, token=token)
    assert (preview["organization_slug"], preview["favicon_url"], preview["white_label"]) == (
        "millenium-school", "https://cdn.test/favicon.png", False,
    )


def test_a_password_reset_asked_on_a_school_page_comes_from_the_school(production_addresses, monkeypatch) -> None:
    db = build_db()
    school(db)
    db.add(UserRecord(email="awa@ecole.dev", full_name="Awa", status="active", password_hash=hash_password("ancien-mot-de-passe")))
    db.commit()
    sent: list[tuple[str, str, dict | None]] = []
    monkeypatch.setattr("app.api.routes.auth.send_password_reset_email",
                        lambda recipient, url, school=None: sent.append((recipient, url, school)))
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            for key in ("millenium-school", None):
                response = client.post("/api/v1/auth/forgot-password", json={"email": "awa@ecole.dev", "school": key})
                assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    (_to, school_url, branding), (_to2, platform_url, no_branding) = sent
    assert school_url.startswith("https://millenium.academiecreatif.com/login?reset_token=")
    assert "school=millenium-school" in school_url
    assert branding["school_name"] == "Millenium school" and branding["logo_url"] == "https://cdn.test/logo.png"
    assert platform_url.startswith("https://ecoles.academiecreatif.com/login?reset_token=") and no_branding is None


def test_the_reset_email_carries_the_school_or_the_platform() -> None:
    url = "https://millenium.academiecreatif.com/login?reset_token=x"
    branded = _password_reset_html(url, {"school_name": "Millenium <school>", "logo_url": "https://cdn.test/logo.png",
                                         "primary_color": "#123456", "white_label": False})
    assert "Millenium &lt;school&gt;" in branded and 'src="https://cdn.test/logo.png"' in branded
    assert "background:#123456" in branded and "Powered by Académie des Créatifs" in branded
    white = _password_reset_html(url, {"school_name": "Millenium", "white_label": True})
    assert "Académie des Créatifs" not in white
    assert "Académie des Créatifs SaaS" in _password_reset_html(url)


def test_a_white_label_school_email_has_no_platform_signature() -> None:
    row = CommunicationOutboxRecord(body="Bonjour", branding_snapshot={"school_name": "Millenium", "white_label": True})
    assert "Académie des Créatifs" not in _email_html(row)
    row.branding_snapshot = {"school_name": "Millenium"}
    assert "Powered by Académie des Créatifs" in _email_html(row)


def test_a_certificate_qr_code_opens_on_the_school(monkeypatch) -> None:
    encoded: list[str] = []
    original = school_documents.qr.QrCodeWidget

    class RecordingQr(original):
        def __init__(self, value, *args, **kwargs):
            encoded.append(value)
            super().__init__(value, *args, **kwargs)

    monkeypatch.setattr(school_documents.qr, "QrCodeWidget", RecordingQr)
    certificate = CertificateRecord(id=7, organization_id=1, enrollment_id=1, certificate_number="MS-7", student_name="Awa",
                                    formation_title="Design", issued_at=datetime.now(UTC), status="valid",
                                    branding_snapshot={"school_name": "Millenium", "white_label": True})
    school_documents.build_certificate_pdf(certificate, site_url="https://millenium.academiecreatif.com")
    assert encoded[-1].startswith("https://millenium.academiecreatif.com/certificates/verify/7.")


def test_google_signs_in_on_the_platform_then_returns_to_the_school(monkeypatch) -> None:
    # Google accepts the platform's address only; a school subdomain shares its session cookie.
    monkeypatch.setattr(settings, "auth_cookie_domain", ".academiecreatif.com")
    monkeypatch.setattr(settings, "environment", "development")
    db = build_db()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            back = client.get("/api/v1/auth/sso/start", params={"return_url": "https://millenium.academiecreatif.com/checkout?x=1"},
                              follow_redirects=False)
            assert back.status_code == 302
            assert back.headers["location"] == "https://millenium.academiecreatif.com/checkout?x=1"
            for elsewhere in ("https://pirate.example/", "https://academiecreatif.com.pirate.example/", "javascript:alert(1)"):
                refused = client.get("/api/v1/auth/sso/start", params={"return_url": elsewhere}, follow_redirects=False)
                assert refused.status_code == 400, elsewhere
    finally:
        app.dependency_overrides.clear()
