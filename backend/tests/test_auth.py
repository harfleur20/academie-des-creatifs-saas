from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, decode_access_token, hash_password
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import UserRecord
from app.schemas.auth import LoginPayload, RegisterPayload
from app.services.auth import authenticate_user, create_user


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_production_requires_unique_jwt_secret() -> None:
    config = Settings(environment="production", jwt_secret_key="academie-saas-development-secret-change-me")
    with pytest.raises(RuntimeError):
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


def test_access_token_contains_user_subject() -> None:
    token = create_access_token(42)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"


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
