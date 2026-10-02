from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.models.entities import UserRecord
from app.schemas.auth import ProfileUpdatePayload
from app.services.auth import change_password, update_avatar, update_profile


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_profile_and_password_updates_keep_email_immutable() -> None:
    db = build_db()
    user = UserRecord(
        email="teacher@test.dev",
        full_name="Old Name",
        password_hash=hash_password("password-old"),
        status="active",
    )
    db.add(user)
    db.commit()

    updated = update_profile(
        db,
        user,
        ProfileUpdatePayload(
            full_name="New Name",
            phone="+33 6 12 34 56 78",
        ),
    )
    assert updated.full_name == "New Name"
    assert updated.phone == "+33 6 12 34 56 78"
    assert updated.email == "teacher@test.dev"

    change_password(
        db,
        updated,
        current_password="password-old",
        new_password="password-new",
    )
    assert verify_password("password-new", updated.password_hash)

    update_avatar(db, updated, "https://files.test/avatar.webp")
    assert updated.avatar_url == "https://files.test/avatar.webp"
