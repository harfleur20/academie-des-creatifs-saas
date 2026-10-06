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
    session_version: int | None = None,
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
    if session_version is not None:
        payload["session_version"] = session_version
    if additional_claims:
        protected = {"sub", "iss", "iat", "exp", "type", "session_version"}
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


def create_message_ws_ticket(user_id: int, organization_id: int, session_version: int) -> str:
    now = utc_now()
    return jwt.encode(
        {
            "sub": str(user_id), "organization_id": organization_id,
            "session_version": session_version, "type": "message_ws",
            "iss": settings.jwt_issuer, "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_message_ws_ticket(ticket: str) -> dict[str, object] | None:
    try:
        payload = jwt.decode(
            ticket, settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm], issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "message_ws":
        return None
    return payload


def create_password_reset_token(
    user_id: int,
    *,
    session_version: int,
    minutes: int = 30,
) -> str:
    now = utc_now()
    payload: dict[str, object] = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "type": "password_reset",
        "session_version": session_version,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_password_reset_token(token: str) -> dict[str, object] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "password_reset":
        return None
    return payload
