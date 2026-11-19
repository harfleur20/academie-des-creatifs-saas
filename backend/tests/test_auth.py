from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_access_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import OrganizationDomainRecord, OrganizationRecord, UserRecord
from app.schemas.auth import LoginPayload, RegisterPayload
from app.services.auth import authenticate_user, create_user, reset_password_with_token


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_production_requires_unique_jwt_secret() -> None:
    config = Settings(
        environment="production",
        jwt_secret_key="academie-saas-development-secret-change-me",
        live_provider="jaas",
        jaas_recording_enabled=False,
        # Production also requires its private B2 bucket and Cloudinary.
        storage_provider="b2",
        b2_endpoint_url="https://s3.eu-central-003.backblazeb2.com",
        b2_region="eu-central-003",
        b2_private_bucket_name="private",
        b2_access_key_id="test-id",
        b2_secret_access_key="test-secret",
        public_asset_provider="cloudinary",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        config.validate_production_security()
    config.jwt_secret_key = "a-unique-generated-secret-for-test-only-123456"
    config.validate_production_security()


def test_create_and_authenticate_user() -> None:
    db = build_db()
    user = create_user(
        db,
        RegisterPayload(
            full_name="Marie Test",
            email="Marie@Example.com",
            password="secret-pass-123",
        ),
    )

    assert user.email == "marie@example.com"
    assert user.password_hash
    assert user.password_hash != "secret-pass-123"

    authenticated = authenticate_user(
        db,
        email="marie@example.com",
        password="secret-pass-123",
    )
    assert authenticated is not None
    assert authenticated.id == user.id


def test_wrong_password_is_rejected() -> None:
    db = build_db()
    create_user(
        db,
        RegisterPayload(
            full_name="Marie Test",
            email="marie@example.com",
            password="secret-pass-123",
        ),
    )

    assert authenticate_user(
        db,
        email="marie@example.com",
        password="wrong-password",
    ) is None


def test_local_demo_address_can_be_used_to_log_in() -> None:
    payload = LoginPayload(
        email="etudiant.demo@academie.local",
        password="Demo2026!",
    )

    assert payload.email == "etudiant.demo@academie.local"


def test_local_demo_address_authenticates_through_api() -> None:
    db = build_db()
    db.add(UserRecord(
        full_name="Étudiant Démo",
        email="etudiant.demo@academie.local",
        password_hash=hash_password("Demo2026!"),
        status="active",
        platform_role="user",
    ))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/auth/login", json={
                "email": "etudiant.demo@academie.local",
                "password": "Demo2026!",
            })
            assert response.status_code == 200
            token = response.json()["access_token"]
            me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 200
            assert me.json()["email"] == "etudiant.demo@academie.local"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_login_cookie_authenticates_other_tab_without_bearer_token() -> None:
    db = build_db()
    create_user(
        db,
        RegisterPayload(
            full_name="Marie Test",
            email="marie@example.com",
            password="secret-pass-123",
        ),
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "marie@example.com",
                    "password": "secret-pass-123",
                },
            )
            assert login_response.status_code == 200
            assert login_response.cookies.get("academie_saas_session")
            assert "httponly" in login_response.headers["set-cookie"].lower()

            # A new browser tab does not have the tab-local bearer token, but it
            # shares the browser cookie and must still recover the logged-in user.
            me = client.get("/api/v1/auth/me")
            assert me.status_code == 200
            assert me.json()["email"] == "marie@example.com"

            logout = client.post("/api/v1/auth/logout")
            assert logout.status_code == 204
            assert client.get("/api/v1/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_access_token_contains_user_subject() -> None:
    token = create_access_token(42)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"


def test_password_reset_token_is_typed_and_single_use() -> None:
    db = build_db()
    user = create_user(
        db,
        RegisterPayload(
            full_name="Marie Test",
            email="marie@example.com",
            password="secret-pass-123",
        ),
    )
    token = create_password_reset_token(
        user.id,
        session_version=user.session_version,
        minutes=30,
    )

    payload = decode_password_reset_token(token)
    assert payload is not None
    assert payload["sub"] == str(user.id)
    assert payload["type"] == "password_reset"

    reset = reset_password_with_token(
        db,
        token=token,
        new_password="new-secret-pass-456",
    )
    assert reset.password_hash is not None
    assert verify_password("new-secret-pass-456", reset.password_hash)
    assert not verify_password("secret-pass-123", reset.password_hash)

    with pytest.raises(ValueError, match="déjà utilisé"):
        reset_password_with_token(
            db,
            token=token,
            new_password="another-secret-789",
        )
    db.close()


def test_access_token_cannot_be_used_as_password_reset_token() -> None:
    db = build_db()
    user = create_user(
        db,
        RegisterPayload(
            full_name="Marie Test",
            email="marie@example.com",
            password="secret-pass-123",
        ),
    )
    access_token = create_access_token(
        user.id,
        session_version=user.session_version,
    )

    with pytest.raises(ValueError, match="invalide ou expiré"):
        reset_password_with_token(
            db,
            token=access_token,
            new_password="new-secret-pass-456",
        )
    db.close()


def test_password_change_and_logout_revoke_existing_tokens() -> None:
    db = build_db()
    create_user(db, RegisterPayload(full_name="Marie Test", email="marie@example.com", password="secret-pass-123"))
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            first = client.post("/api/v1/auth/login", json={"email": "marie@example.com", "password": "secret-pass-123"})
            assert first.status_code == 200
            old_token = first.json()["access_token"]
            old_headers = {"Authorization": f"Bearer {old_token}"}
            changed = client.post("/api/v1/auth/me/change-password", json={
                "current_password": "secret-pass-123", "new_password": "new-secret-pass-456",
            }, headers=old_headers)
            assert changed.status_code == 204
            assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401

            second = client.post("/api/v1/auth/login", json={"email": "marie@example.com", "password": "new-secret-pass-456"})
            assert second.status_code == 200
            new_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
            assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200
            assert client.post("/api/v1/auth/logout", headers=new_headers).status_code == 204
            assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 401
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_custom_domain_sso_handoff_is_single_use() -> None:
    db = build_db()
    create_user(
        db,
        RegisterPayload(
            full_name="Marie Test",
            email="marie@example.com",
            password="secret-pass-123",
        ),
    )
    organization = OrganizationRecord(
        name="École Test",
        slug="ecole-test",
        status="active",
        is_active=True,
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    db.add(
        OrganizationDomainRecord(
            organization_id=organization.id,
            hostname="school.example.com",
            status="verified",
            verification_token="verified-token",
            is_primary=True,
        )
    )
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": "marie@example.com", "password": "secret-pass-123"},
            )
            assert login.status_code == 200

            config = client.get(
                "/api/v1/auth/sso/config",
                headers={"host": "school.example.com"},
            )
            assert config.status_code == 200
            assert config.json()["enabled"] is True

            started = client.get(
                "/api/v1/auth/sso/start",
                params={"return_url": "http://school.example.com/espace?from=dashboard"},
                follow_redirects=False,
            )
            assert started.status_code == 302
            fragment = parse_qs(urlsplit(started.headers["location"]).fragment)
            handoff = fragment["sso_handoff"][0]

            exchanged = client.post(
                "/api/v1/auth/sso/exchange",
                json={"token": handoff},
                headers={"host": "school.example.com"},
            )
            assert exchanged.status_code == 200
            assert exchanged.json()["user"]["email"] == "marie@example.com"

            reused = client.post(
                "/api/v1/auth/sso/exchange",
                json={"token": handoff},
                headers={"host": "school.example.com"},
            )
            assert reused.status_code == 400
    finally:
        app.dependency_overrides.clear()
        db.close()
