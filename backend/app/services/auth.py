import os

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.models.entities import UserRecord
from app.schemas.auth import ProfileUpdatePayload, RegisterPayload


class EmailAlreadyUsedError(ValueError):
    pass


class GoogleAuthenticationError(ValueError):
    pass


class GoogleAuthNotConfiguredError(GoogleAuthenticationError):
    pass


def get_user_by_email(db: Session, email: str) -> UserRecord | None:
    normalized = email.strip().lower()
    return db.scalar(
        select(UserRecord).where(func.lower(UserRecord.email) == normalized)
    )


def create_user(db: Session, payload: RegisterPayload) -> UserRecord:
    email = str(payload.email).strip().lower()
    if get_user_by_email(db, email) is not None:
        raise EmailAlreadyUsedError(email)

    user = UserRecord(
        full_name=payload.full_name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        status="active",
        platform_role="user",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyUsedError(email) from exc
    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> UserRecord | None:
    user = get_user_by_email(db, email)
    if user is None or user.status != "active" or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def authenticate_google_user(
    db: Session,
    *,
    credential: str,
) -> UserRecord:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise GoogleAuthNotConfiguredError("Connexion Google non configurée.")

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential},
            )
    except httpx.HTTPError as exc:
        raise GoogleAuthenticationError("Impossible de vérifier la connexion Google.") from exc

    if response.status_code != 200:
        raise GoogleAuthenticationError("Jeton Google invalide ou expiré.")

    try:
        claims = response.json()
    except ValueError as exc:
        raise GoogleAuthenticationError("Réponse Google invalide.") from exc

    if claims.get("aud") != client_id:
        raise GoogleAuthenticationError("Ce compte Google n’est pas autorisé pour cette application.")
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise GoogleAuthenticationError("Émetteur Google invalide.")
    if claims.get("email_verified") not in {True, "true", "True", "1"}:
        raise GoogleAuthenticationError("L’adresse email Google n’est pas vérifiée.")

    email = str(claims.get("email") or "").strip().lower()
    if not email or len(email) > 180:
        raise GoogleAuthenticationError("Adresse email Google invalide.")

    full_name = str(claims.get("name") or email.split("@", 1)[0]).strip()[:180]
    if len(full_name) < 2:
        full_name = email.split("@", 1)[0][:180]
    picture = str(claims.get("picture") or "").strip()
    avatar_url = picture if picture and len(picture) <= 1024 else None

    user = get_user_by_email(db, email)
    if user is not None:
        if user.status != "active":
            raise GoogleAuthenticationError("Ce compte est désactivé.")
        changed = False
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user

    user = UserRecord(
        full_name=full_name,
        email=email,
        password_hash=None,
        avatar_url=avatar_url,
        status="active",
        platform_role="user",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = get_user_by_email(db, email)
        if existing is None or existing.status != "active":
            raise GoogleAuthenticationError("Impossible de créer le compte Google.") from exc
        return existing
    db.refresh(user)
    return user


def update_profile(
    db: Session,
    user: UserRecord,
    payload: ProfileUpdatePayload,
) -> UserRecord:
    user.full_name = payload.full_name.strip()
    user.phone = payload.phone
    db.commit()
    db.refresh(user)
    return user


def change_password(
    db: Session,
    user: UserRecord,
    *,
    current_password: str,
    new_password: str,
) -> UserRecord:
    if not user.password_hash:
        raise ValueError("Ce compte utilise Google et n’a pas encore de mot de passe local.")
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Mot de passe actuel incorrect.")
    db.execute(
        update(UserRecord)
        .where(UserRecord.id == user.id)
        .values(
            password_hash=hash_password(new_password),
            session_version=UserRecord.session_version + 1,
        )
    )
    db.commit()
    db.refresh(user)
    return user


def reset_password_with_token(
    db: Session,
    *,
    token: str,
    new_password: str,
) -> UserRecord:
    payload = decode_password_reset_token(token)
    if payload is None:
        raise ValueError("Lien de réinitialisation invalide ou expiré.")

    try:
        user_id = int(str(payload.get("sub") or ""))
        token_session_version = int(payload.get("session_version"))
    except (TypeError, ValueError):
        raise ValueError("Lien de réinitialisation invalide ou expiré.") from None

    user = db.get(UserRecord, user_id)
    if (
        user is None
        or user.status != "active"
        or user.session_version != token_session_version
    ):
        raise ValueError("Lien de réinitialisation invalide ou déjà utilisé.")

    updated = db.execute(
        update(UserRecord)
        .where(
            UserRecord.id == user.id,
            UserRecord.session_version == token_session_version,
        )
        .values(
            password_hash=hash_password(new_password),
            session_version=UserRecord.session_version + 1,
        )
    )
    if updated.rowcount != 1:
        db.rollback()
        raise ValueError("Lien de réinitialisation invalide ou déjà utilisé.")

    db.commit()
    db.refresh(user)
    return user


def revoke_user_sessions(db: Session, user: UserRecord) -> None:
    db.execute(
        update(UserRecord)
        .where(UserRecord.id == user.id)
        .values(session_version=UserRecord.session_version + 1)
    )
    db.commit()


def update_avatar(
    db: Session,
    user: UserRecord,
    avatar_url: str,
) -> UserRecord:
    user.avatar_url = avatar_url
    db.commit()
    db.refresh(user)
    return user
