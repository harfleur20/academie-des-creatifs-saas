from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_handoff import AuthHandoffRecord
from app.models.entities import OrganizationDomainRecord, UserRecord
from app.services.organization_domains import normalize_hostname


HANDOFF_TTL_SECONDS = 45


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_custom_domain_return_url(
    db: Session,
    return_url: str,
    *,
    require_https: bool,
) -> tuple[str, OrganizationDomainRecord]:
    parsed = urlsplit(return_url.strip())
    if parsed.scheme not in ({"https"} if require_https else {"http", "https"}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL de retour SSO invalide.",
        )
    if parsed.username or parsed.password or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL de retour SSO invalide.",
        )

    hostname = normalize_hostname(parsed.hostname)
    domain = db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.hostname == hostname,
            OrganizationDomainRecord.status == "verified",
        )
    )
    if domain is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce domaine personnalisé n'est pas vérifié.",
        )

    clean_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    return clean_url, domain


def create_auth_handoff(
    db: Session,
    *,
    user: UserRecord,
    domain: OrganizationDomainRecord,
) -> str:
    raw_token = secrets.token_urlsafe(32)
    row = AuthHandoffRecord(
        token_hash=_hash_token(raw_token),
        user_id=user.id,
        organization_id=domain.organization_id,
        target_host=domain.hostname,
        session_version=user.session_version,
        expires_at=_utc_now() + timedelta(seconds=HANDOFF_TTL_SECONDS),
    )
    db.add(row)
    db.commit()
    return raw_token


def consume_auth_handoff(
    db: Session,
    *,
    token: str,
    target_host: str,
) -> UserRecord:
    token_hash = _hash_token(token)
    hostname = normalize_hostname(target_host)
    row = db.scalar(
        select(AuthHandoffRecord)
        .where(AuthHandoffRecord.token_hash == token_hash)
        .with_for_update()
    )
    now = _utc_now()
    if (
        row is None
        or row.used_at is not None
        or row.target_host != hostname
        or _aware_utc(row.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce transfert de session est invalide ou expiré.",
        )

    user = db.get(UserRecord, row.user_id)
    if (
        user is None
        or user.status != "active"
        or user.session_version != row.session_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cette session n'est plus valide.",
        )

    row.used_at = now
    db.add(row)
    db.commit()
    return user
