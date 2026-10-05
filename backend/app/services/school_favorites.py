from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord, OrganizationRecord, SchoolFavoriteRecord, UserRecord
from app.schemas.commerce import PublicFormationCardRead
from app.services.public_catalog import list_public_formations


def list_school_favorites(db: Session, org: OrganizationRecord, user: UserRecord) -> list[PublicFormationCardRead]:
    rows = db.scalars(
        select(SchoolFavoriteRecord)
        .where(SchoolFavoriteRecord.organization_id == org.id, SchoolFavoriteRecord.user_id == user.id)
        .order_by(SchoolFavoriteRecord.created_at.desc(), SchoolFavoriteRecord.id.desc())
    ).all()
    cards = {card.id: card for card in list_public_formations(db, org)}
    return [cards[row.formation_id] for row in rows if row.formation_id in cards]


def add_school_favorite(db: Session, org: OrganizationRecord, user: UserRecord, slug: str) -> list[PublicFormationCardRead]:
    card = next((item for item in list_public_formations(db, org) if item.slug == slug), None)
    if card is None:
        raise HTTPException(404, "Formation introuvable.")
    existing = db.scalar(select(SchoolFavoriteRecord).where(
        SchoolFavoriteRecord.organization_id == org.id,
        SchoolFavoriteRecord.user_id == user.id,
        SchoolFavoriteRecord.formation_id == card.id,
    ))
    if existing is None:
        db.add(SchoolFavoriteRecord(organization_id=org.id, user_id=user.id, formation_id=card.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return list_school_favorites(db, org, user)


def remove_school_favorite(db: Session, org: OrganizationRecord, user: UserRecord, slug: str) -> list[PublicFormationCardRead]:
    favorite = db.scalar(
        select(SchoolFavoriteRecord)
        .join(FormationRecord, FormationRecord.id == SchoolFavoriteRecord.formation_id)
        .where(
            SchoolFavoriteRecord.organization_id == org.id,
            SchoolFavoriteRecord.user_id == user.id,
            FormationRecord.organization_id == org.id,
            FormationRecord.slug == slug,
        )
    )
    if favorite is None:
        raise HTTPException(404, "Formation absente des favoris.")
    db.delete(favorite)
    db.commit()
    return list_school_favorites(db, org, user)
