from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord, OrganizationMemberRecord, OrganizationRecord, SchoolFavoriteRecord, UserRecord
from app.schemas.commerce import PublicFormationCardRead
from app.services.demo import is_demo_organization
from app.services.public_catalog import list_public_formations


def _require_school_membership(db: Session, org: OrganizationRecord, user: UserRecord) -> None:
    if is_demo_organization(org):
        return
    membership_id = db.scalar(select(OrganizationMemberRecord.id).where(
        OrganizationMemberRecord.organization_id == org.id,
        OrganizationMemberRecord.user_id == user.id,
        OrganizationMemberRecord.status == "active",
    ))
    if membership_id is None:
        raise HTTPException(403, "Votre compte n’est pas encore inscrit à cette école.")


def list_school_favorites(db: Session, org: OrganizationRecord, user: UserRecord) -> list[PublicFormationCardRead]:
    _require_school_membership(db, org, user)
    rows = db.scalars(
        select(SchoolFavoriteRecord)
        .where(SchoolFavoriteRecord.organization_id == org.id, SchoolFavoriteRecord.user_id == user.id)
        .order_by(SchoolFavoriteRecord.created_at.desc(), SchoolFavoriteRecord.id.desc())
    ).all()
    cards = {card.id: card for card in list_public_formations(db, org)}
    return [cards[row.formation_id] for row in rows if row.formation_id in cards]


def add_school_favorite(db: Session, org: OrganizationRecord, user: UserRecord, slug: str) -> list[PublicFormationCardRead]:
    from app.services.demo import require_not_demo

    _require_school_membership(db, org, user)
    require_not_demo(org)
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
    _require_school_membership(db, org, user)
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
