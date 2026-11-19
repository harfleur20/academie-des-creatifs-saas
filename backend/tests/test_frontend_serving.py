from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.main import serve_frontend
from app.models.entities import (
    CertificateRecord,
    OrganizationInvitationRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
)
from app.services.class_certificates import _verification_token
from app.services.organization_management import _token_hash


def empty_database():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def built_frontend(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (dist / "assets" / "main-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "logo.png").write_bytes(b"png")
    (tmp_path / "secret.txt").write_text("hors du build", encoding="utf-8")
    return dist


def client_for(dist: Path, session_factory=None) -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    assert serve_frontend(app, str(dist), session_factory or empty_database())
    return TestClient(app)


def test_app_routes_load_the_frontend(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    for path in ("/", "/login", "/app/teacher/live/3"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.text == "<div id=root></div>"
        assert response.headers["cache-control"] == "no-cache"


def test_built_files_are_served_with_long_cache_for_assets(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    asset = client.get("/assets/main-abc123.js")
    assert asset.text == "console.log(1)"
    assert "immutable" in asset.headers["cache-control"]
    assert client.get("/logo.png").content == b"png"
    assert client.head("/assets/main-abc123.js").status_code == 200
    assert client.head("/login").status_code == 200


def test_api_and_uploads_keep_their_own_404(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    assert client.get("/api/v1/ping").json() == {"pong": "ok"}
    assert client.get("/api/v1/missing").status_code == 404
    assert client.get("/uploads/missing.png").status_code == 404


def test_paths_cannot_leave_the_build(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        assert "hors du build" not in client.get(path).text


def test_nothing_is_served_without_a_build(tmp_path) -> None:
    assert serve_frontend(FastAPI(), "") is False
    assert serve_frontend(FastAPI(), str(tmp_path / "absent")) is False


# The page as Vite builds it: the platform's name, icon and description.
BUILT_INDEX = """<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/png" href="/logo-academie-icone.png" />
    <meta
      name="description"
      content="Créez et administrez votre école digitale."
    />
    <title>Académie des Créatifs - Votre école digitale</title>
    <script type="module" crossorigin src="/assets/index-abc.js"></script>
  </head>
  <body><div id="root"></div></body>
</html>"""
PLATFORM = "ecoles.academiecreatif.com"
SCHOOL_HOST = "millenium.academiecreatif.com"
INVITE_TOKEN = "jeton-invitation-de-test"


def built_index(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(BUILT_INDEX, encoding="utf-8")
    return dist


@pytest.fixture
def school_site(tmp_path, monkeypatch):
    """A client, its database, and a certificate's verification token."""
    monkeypatch.setattr(settings, "saas_base_domain", "academiecreatif.com")
    monkeypatch.setattr(settings, "frontend_url", f"https://{PLATFORM}")
    factory = empty_database()
    with factory() as db:
        org = OrganizationRecord(name="Millenium", slug="millenium-school", subdomain="millenium", locale="en-US",
                                 logo_url="https://cdn.test/logo.png", status="active", is_active=True)
        db.add(org)
        db.flush()
        db.add(OrganizationPublicSiteRecord(organization_id=org.id, site_name="Millenium school",
                                            favicon_url="https://cdn.test/favicon.png", seo_description="Formez-vous."))
        db.add(OrganizationInvitationRecord(organization_id=org.id, email="prof@ecole.test", role="teacher",
                                            token_hash=_token_hash(INVITE_TOKEN), status="pending",
                                            expires_at=datetime.now(UTC) + timedelta(days=7)))
        certificate = CertificateRecord(
            organization_id=org.id, enrollment_id=1, certificate_number="MS-1", student_name="Awa",
            formation_title="Design", issued_at=datetime.now(UTC), status="valid",
            branding_snapshot={"school_name": "Millenium (2026)", "logo_url": "https://cdn.test/old.png"},
        )
        db.add(certificate)
        db.commit()
        certificate_token = _verification_token(certificate)
    return client_for(built_index(tmp_path), factory), factory, certificate_token


def page(client: TestClient, path: str, host: str = PLATFORM) -> str:
    response = client.get(path, headers={"host": host})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    return response.text


def test_a_school_page_names_its_school_before_any_script_runs(school_site) -> None:
    client, _factory, _token = school_site
    for path in ("/", "/formations/design", "/login"):
        html = page(client, path, SCHOOL_HOST)
        assert "<title>Millenium school</title>" in html
        assert '<link rel="icon" href="https://cdn.test/favicon.png" />' in html
        assert '<meta name="description" content="Formez-vous." />' in html
        assert '<html lang="en-US"' in html
        assert '<meta name="academie-school" content="millenium-school" />' in html
        # Where Google sign-in happens for this school's address.
        assert f'<meta name="academie-platform" content="https://{PLATFORM}" />' in html
        # Link previews (WhatsApp, Facebook…) show the school too.
        assert '<meta property="og:image" content="https://cdn.test/logo.png" />' in html
        assert "Académie des Créatifs" not in html and "logo-academie" not in html
    assert "<title>Millenium school - Enseignant</title>" in page(client, "/app/teacher/live/3", SCHOOL_HOST)
    assert "<title>Millenium school - Gestion</title>" in page(client, "/app/manage", SCHOOL_HOST)


def test_school_pages_on_the_platform_address_name_their_school(school_site) -> None:
    client, _factory, certificate_token = school_site
    for path in ("/school/millenium-school/formations", "/login?school=millenium-school&mode=register",
                 f"/invite/{INVITE_TOKEN}", f"/login?mode=register&return=%2Finvite%2F{INVITE_TOKEN}"):
        assert "<title>Millenium school</title>" in page(client, path), path
    # A certificate shows the school as it was when issued, as its verification page does.
    html = page(client, f"/certificates/verify/{certificate_token}")
    assert "<title>Millenium (2026)</title>" in html and 'href="https://cdn.test/old.png"' in html


def test_school_pages_of_an_unknown_school_show_no_platform_name(school_site) -> None:
    client, _factory, certificate_token = school_site
    for path in ("/app/manage", "/invite/inconnu", "/certificates/verify/1.faux", f"/certificates/verify/{certificate_token}x"):
        html = page(client, path)
        assert "<title></title>" in html, path
        assert '<link rel="icon" href="data:," />' in html
        assert "academie-school" not in html


def test_the_platform_pages_keep_the_platform(school_site) -> None:
    client, _factory, _token = school_site
    for path in ("/", "/login", "/cgu", "/admin/schools", "/school/inconnue"):
        assert page(client, path) == BUILT_INDEX, path
    assert page(client, "/", "localhost") == BUILT_INDEX


def test_a_school_name_is_written_as_text(school_site) -> None:
    client, factory, _token = school_site
    with factory() as db:
        db.query(OrganizationPublicSiteRecord).one().site_name = '</title><script>alert("x")</script> \1 & Cie'
        db.commit()
    html = page(client, "/", SCHOOL_HOST)
    assert "<script>alert" not in html
    assert "<title>&lt;/title&gt;&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; \1 &amp; Cie</title>" in html


def test_a_failing_database_still_serves_the_page(tmp_path) -> None:
    def broken():
        raise RuntimeError("base indisponible")

    client = client_for(built_index(tmp_path), broken)
    assert page(client, "/", SCHOOL_HOST) == BUILT_INDEX
