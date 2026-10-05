import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import AuthenticatedSession, get_current_user, get_support_session
from app.core.config import settings
from app.core.security import create_access_token, create_password_reset_token
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.auth import (
    AuthResponse,
    AuthUser,
    GoogleAuthPayload,
    LoginPayload,
    MessageResponse,
    PasswordChangePayload,
    PasswordResetConfirmPayload,
    PasswordResetRequestPayload,
    ProfileUpdatePayload,
    RegisterPayload,
)
from app.services.admin import end_support_session
from app.services.assets import store_profile_avatar
from app.services.auth import (
    EmailAlreadyUsedError,
    GoogleAuthenticationError,
    GoogleAuthNotConfiguredError,
    authenticate_google_user,
    authenticate_user,
    change_password,
    create_user,
    get_user_by_email,
    reset_password_with_token,
    revoke_user_sessions,
    update_avatar,
    update_profile,
)
from app.services.password_reset_mail import send_password_reset_email


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


RESET_REQUEST_MESSAGE = (
    "Si un compte correspond à cette adresse, un email de réinitialisation vient d’être envoyé."
)


def _response(user: UserRecord, message: str) -> AuthResponse:
    return AuthResponse(
        message=message,
        user=AuthUser.model_validate(user),
        access_token=create_access_token(user.id, minutes=60, session_version=user.session_version),
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


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: PasswordResetRequestPayload,
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = get_user_by_email(db, str(payload.email))
    if user is None or user.status != "active":
        return MessageResponse(message=RESET_REQUEST_MESSAGE)

    reset_token = create_password_reset_token(
        user.id,
        session_version=user.session_version,
        minutes=30,
    )
    query: dict[str, str] = {"reset_token": reset_token}
    if payload.school:
        query["school"] = payload.school.strip()
    reset_url = f"{settings.frontend_url}/login?{urlencode(query)}"

    try:
        send_password_reset_email(user.email, reset_url)
    except Exception:
        # The public response must not disclose whether an account or email provider exists.
        logger.exception("Unable to deliver password reset email for user_id=%s", user.id)

    return MessageResponse(message=RESET_REQUEST_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: PasswordResetConfirmPayload,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        reset_password_with_token(
            db,
            token=payload.token,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return MessageResponse(
        message="Votre mot de passe a été réinitialisé. Vous pouvez maintenant vous connecter."
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(
    payload: GoogleAuthPayload,
    db: Session = Depends(get_db),
) -> AuthResponse:
    try:
        user = await authenticate_google_user(db, credential=payload.credential)
    except GoogleAuthNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except GoogleAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return _response(user, "Connexion Google réussie.")


@router.get("/me", response_model=AuthUser)
def me(
    current_user: UserRecord = Depends(get_current_user),
) -> AuthUser:
    return AuthUser.model_validate(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
):
    revoke_user_sessions(db, current_user)
    return None


@router.patch("/me", response_model=AuthUser)
def update_me(
    payload: ProfileUpdatePayload,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> AuthUser:
    return AuthUser.model_validate(update_profile(db, current_user, payload))


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def update_my_password(
    payload: PasswordChangePayload,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
):
    try:
        change_password(
            db,
            current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return None


@router.post("/me/avatar", response_model=AuthUser)
async def update_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> AuthUser:
    asset = await store_profile_avatar(file, current_user.id)
    return AuthUser.model_validate(
        update_avatar(db, current_user, asset["public_url"])
    )


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
