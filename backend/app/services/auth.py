from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.entities import UserRecord
from app.schemas.auth import ProfileUpdatePayload, RegisterPayload


class EmailAlreadyUsedError(ValueError):
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
    if user is None or user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
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
