import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import UserRecord
from scripts.promote_super_admin import promote_super_admin


def build_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_an_existing_account_becomes_super_admin_whatever_the_email_case() -> None:
    db = build_db()
    db.add(UserRecord(email="admin@ecoles.example", full_name="Admin"))
    db.commit()
    assert promote_super_admin(db, " Admin@Ecoles.example ").platform_role == "super_admin"


@pytest.mark.parametrize("status", [None, "suspended"])
def test_a_missing_or_inactive_account_is_refused(status) -> None:
    db = build_db()
    if status:
        db.add(UserRecord(email="admin@ecoles.example", full_name="Admin", status=status))
        db.commit()
    with pytest.raises(SystemExit):
        promote_super_admin(db, "admin@ecoles.example")
