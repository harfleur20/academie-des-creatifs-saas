from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: int, *, minutes: int = 60) -> str:
    now = utc_now()
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "type": "access",
    }
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
