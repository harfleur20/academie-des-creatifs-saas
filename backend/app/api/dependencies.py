from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import UserRecord
from app.services.tenancy import TenantContext, resolve_tenant_context


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserRecord:
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
    return user


def get_tenant_context(
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
    organization_id: Annotated[int | None, Header(alias=settings.tenant_header)] = None,
) -> TenantContext:
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"En-tête {settings.tenant_header} requis.",
        )

    return resolve_tenant_context(
        db,
        user=current_user,
        organization_id=organization_id,
    )



def get_super_admin(
    current_user: UserRecord = Depends(get_current_user),
) -> UserRecord:
    if current_user.platform_role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès super-administrateur requis.",
        )
    return current_user
