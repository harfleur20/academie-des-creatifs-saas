from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings


password_hasher = PasswordHasher()


def utc_now() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(
    user_id: int,
    *,
    minutes: int = 60,
    additional_claims: dict[str, object] | None = None,
) -> str:
    now = utc_now()
    payload: dict[str, object] = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "type": "access",
    }
    if additional_claims:
        protected = {"sub", "iss", "iat", "exp", "type"}
        if protected.intersection(additional_claims):
            raise ValueError("additional_claims cannot override protected JWT claims")
        payload.update(additional_claims)
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, object] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "access":
        return None
    return payload
