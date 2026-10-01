from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import AuthenticatedSession, get_current_user, get_support_session
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.auth import AuthResponse, AuthUser, LoginPayload, RegisterPayload
from app.services.admin import end_support_session
from app.services.auth import (
    EmailAlreadyUsedError,
    authenticate_user,
    create_user,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _response(user: UserRecord, message: str) -> AuthResponse:
    return AuthResponse(
        message=message,
        user=AuthUser.model_validate(user),
        access_token=create_access_token(user.id, minutes=24 * 60),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterPayload,
    db: Session = Depends(get_db),
) -> AuthResponse:
    try:
        user = create_user(db, payload)
    except EmailAlreadyUsedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà utilisée.",
        ) from exc
    return _response(user, "Compte créé avec succès.")


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginPayload,
    db: Session = Depends(get_db),
) -> AuthResponse:
    user = authenticate_user(
        db,
        email=str(payload.email),
        password=payload.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Adresse email ou mot de passe incorrect.",
        )
    return _response(user, "Connexion réussie.")


@router.get("/me", response_model=AuthUser)
def me(
    current_user: UserRecord = Depends(get_current_user),
) -> AuthUser:
    return AuthUser.model_validate(current_user)



@router.post("/support/end", status_code=status.HTTP_204_NO_CONTENT)
def end_support(
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_support_session),
):
    end_support_session(
        db,
        actor=session.user,
        support_session=session.support_session,
    )
    return None
