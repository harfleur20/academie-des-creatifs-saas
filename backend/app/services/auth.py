from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.entities import UserRecord
from app.schemas.auth import RegisterPayload


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
