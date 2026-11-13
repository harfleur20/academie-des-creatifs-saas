from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth_cookies import auth_cookie_secure_for_request
from app.core.security import create_access_token, decode_access_token
from app.db.session import get_db
from app.models.entities import OrganizationDomainRecord, UserRecord
from app.schemas.auth import AuthResponse, AuthSsoConfigRead, AuthSsoExchangePayload, AuthUser
from app.services.auth_handoff import (
    consume_auth_handoff,
    create_auth_handoff,
    validate_custom_domain_return_url,
)
from app.services.organization_domains import normalize_hostname


router = APIRouter(prefix="/auth/sso", tags=["auth-sso"])


def _request_hostname(request: Request) -> str | None:
    raw = request.url.hostname or ""
    try:
        return normalize_hostname(raw)
    except HTTPException:
        return None


def _verified_custom_domain(db: Session, hostname: str | None) -> OrganizationDomainRecord | None:
    if not hostname:
        return None
    if settings.saas_base_domain and (
        hostname == settings.saas_base_domain
        or hostname.endswith(f".{settings.saas_base_domain}")
    ):
        return None
    return db.scalar(
        select(OrganizationDomainRecord).where(
            OrganizationDomainRecord.hostname == hostname,
            OrganizationDomainRecord.status == "verified",
        )
    )


def _checked_redirect(return_url: str) -> RedirectResponse:
    clean_url, _ = return_url.split("#", 1) if "#" in return_url else (return_url, "")
    return RedirectResponse(f"{clean_url}#sso_checked=1", status_code=status.HTTP_302_FOUND)


@router.get("/config", response_model=AuthSsoConfigRead)
def sso_config(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthSsoConfigRead:
    hostname = _request_hostname(request)
    domain = _verified_custom_domain(db, hostname)
    if domain is None:
        return AuthSsoConfigRead(enabled=False)
    return AuthSsoConfigRead(
        enabled=True,
        start_url=f"{settings.backend_public_url}{settings.api_prefix}/auth/sso/start",
    )


@router.get("/start")
def start_custom_domain_sso(
    return_url: str,
    request: Request,
    db: Session = Depends(get_db),
):
    clean_url, domain = validate_custom_domain_return_url(
        db,
        return_url,
        require_https=settings.environment == "production",
    )
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if not cookie_token:
        return _checked_redirect(clean_url)

    claims = decode_access_token(cookie_token)
    if (
        claims is None
        or claims.get("support_session_id") is not None
        or claims.get("support_org_id") is not None
        or claims.get("demo_org") is not None
    ):
        return _checked_redirect(clean_url)

    try:
        user_id = int(str(claims["sub"]))
    except (KeyError, TypeError, ValueError):
        return _checked_redirect(clean_url)

    user = db.get(UserRecord, user_id)
    if (
        user is None
        or user.status != "active"
        or type(claims.get("session_version")) is not int
        or claims["session_version"] != user.session_version
    ):
        return _checked_redirect(clean_url)

    handoff = create_auth_handoff(db, user=user, domain=domain)
    return RedirectResponse(
        f"{clean_url}#sso_handoff={quote(handoff, safe='')}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/exchange", response_model=AuthResponse)
def exchange_custom_domain_sso(
    payload: AuthSsoExchangePayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    hostname = _request_hostname(request)
    domain = _verified_custom_domain(db, hostname)
    if domain is None or hostname is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le transfert SSO n'est disponible que sur un domaine personnalisé vérifié.",
        )

    user = consume_auth_handoff(db, token=payload.token, target_host=hostname)
    token = create_access_token(
        user.id,
        minutes=60,
        session_version=user.session_version,
    )
    # Host-only cookie: browsers cannot share the SaaS parent-domain cookie with
    # an unrelated custom domain. The one-time handoff safely creates its local
    # session without exposing the main SaaS cookie.
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=60 * 60,
        path="/",
        secure=auth_cookie_secure_for_request(request),
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
    return AuthResponse(
        message="Session synchronisée.",
        user=AuthUser.model_validate(user),
        access_token=token,
    )
