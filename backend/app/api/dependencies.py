from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import PlatformSupportSessionRecord, UserRecord
from app.services.tenancy import TenantContext, resolve_tenant_context


bearer_scheme = HTTPBearer(auto_error=False)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True)
class AuthenticatedSession:
    user: UserRecord
    claims: dict[str, object]
    support_session: PlatformSupportSessionRecord | None = None

    @property
    def support_organization_id(self) -> int | None:
        if self.support_session is None:
            return None
        return self.support_session.organization_id


def get_authenticated_session(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré.",
        )

    try:
        user_id = int(str(payload["sub"]))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide.",
        )

    user = db.get(UserRecord, user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou inactif.",
        )
    if type(payload.get("session_version")) is not int or payload["session_version"] != user.session_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée ou révoquée.",
        )

    raw_support_session_id = payload.get("support_session_id")
    raw_support_org_id = payload.get("support_org_id")
    if raw_support_session_id is None and raw_support_org_id is None:
        return AuthenticatedSession(user=user, claims=payload)

    if user.platform_role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session support invalide.",
        )

    try:
        support_session_id = int(str(raw_support_session_id))
        support_org_id = int(str(raw_support_org_id))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session support invalide.",
        )

    support_session = db.get(PlatformSupportSessionRecord, support_session_id)
    now = datetime.now(UTC)
    if (
        support_session is None
        or support_session.actor_user_id != user.id
        or support_session.organization_id != support_org_id
        or support_session.ended_at is not None
        or _aware_utc(support_session.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session support expirée ou révoquée.",
        )

    return AuthenticatedSession(
        user=user,
        claims=payload,
        support_session=support_session,
    )


def get_current_user(
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> UserRecord:
    return session.user


def get_tenant_context(
    request: Request,
    session: AuthenticatedSession = Depends(get_authenticated_session),
    db: Session = Depends(get_db),
    organization_id: Annotated[int | None, Header(alias=settings.tenant_header)] = None,
) -> TenantContext:
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"En-tête {settings.tenant_header} requis.",
        )

    if session.user.platform_role == "super_admin":
        if session.support_session is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ouvrez d'abord une session de support pour cette école.",
            )
        if session.support_session.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cette session support est limitée à une autre école.",
            )
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Le mode support est en lecture seule.",
            )

    return resolve_tenant_context(
        db,
        user=session.user,
        organization_id=organization_id,
        support_mode=session.support_session is not None,
    )


def get_super_admin(
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> UserRecord:
    if (
        session.user.platform_role != "super_admin"
        or session.support_session is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès super-administrateur requis.",
        )
    return session.user


def get_support_session(
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> AuthenticatedSession:
    if session.support_session is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session support requise.",
        )
    return session



def get_non_support_user(
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> UserRecord:
    if session.support_session is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette action n'est pas disponible en mode support.",
        )
    return session.user
