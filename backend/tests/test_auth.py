from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_access_token
from app.db.base import Base
from app.schemas.auth import RegisterPayload
from app.services.auth import authenticate_user, create_user


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


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


def test_access_token_contains_user_subject() -> None:
    token = create_access_token(42)
    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "42"
