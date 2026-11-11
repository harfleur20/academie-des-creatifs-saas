"""Make an existing account the platform's super admin, on a fresh deployment.

The person first signs up on the site with a dedicated email, then from the backend
folder (on Coolify: the application's terminal):

    python -m scripts.promote_super_admin admin@example.com
"""
from __future__ import annotations

import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import UserRecord


def promote_super_admin(db: Session, email: str) -> UserRecord:
    user = db.scalar(select(UserRecord).where(func.lower(UserRecord.email) == email.strip().lower()))
    if user is None:
        raise SystemExit(f"Aucun compte pour {email} : inscrivez-vous d'abord sur le site avec cet email.")
    if user.status != "active":
        raise SystemExit(f"Le compte {email} n'est pas actif.")
    user.platform_role = "super_admin"
    db.commit()
    return user


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage : python -m scripts.promote_super_admin email@exemple.com")
    with SessionLocal() as db:
        user = promote_super_admin(db, sys.argv[1])
    print(f"{user.email} est maintenant super-administrateur de la plateforme.")


if __name__ == "__main__":
    main()
