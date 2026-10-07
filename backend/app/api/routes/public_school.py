from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.entities import UserRecord
from app.schemas.commerce import (
    PublicFormationCardRead,
    PublicFormationDetailRead,
    PublicHomeRead,
    PublicSchoolRead,
)
from app.services.public_catalog import (
    list_public_formations,
    public_formation_detail,
    public_home,
    public_school_read,
)
from app.services.public_school_slug import (
    ensure_canonical_public_slug,
    resolve_public_organization,
)
from app.services.school_branding import get_or_create_identity_records
from app.services.school_favorites import add_school_favorite, list_school_favorites, remove_school_favorite


router = APIRouter(prefix="/public/schools", tags=["public-school"])


def _public_org(db: Session, school_key: str):
    org = resolve_public_organization(db, school_key)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "École introuvable.")

    # Repair older schools whose public name was changed without updating the
    # canonical public slug. The previous slug is preserved as an alias by
    # ensure_canonical_public_slug(), so already-shared links keep working.
    site, _legal, _communications, _certification = get_or_create_identity_records(db, org)
    previous_slug = org.slug
    canonical_slug = ensure_canonical_public_slug(
        db,
        org,
        site.site_name or org.name,
    )
    if canonical_slug != previous_slug:
        db.commit()
        db.refresh(org)

    return org


@router.get("/{school_key}", response_model=PublicHomeRead)
def get_school_home(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = _public_org(db, school_key)
    return public_home(db, org.slug)


@router.get("/{school_key}/identity", response_model=PublicSchoolRead)
def get_school_identity_public(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = _public_org(db, school_key)
    return public_school_read(db, org)


@router.get("/{school_key}/contact-channels")
def get_school_contact_channels(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = _public_org(db, school_key)
    public_school_read(db, org)
    _site, _legal, communications, _certification = get_or_create_identity_records(db, org)
    return {"whatsapp_phone": communications.whatsapp_phone}


@router.get("/{school_key}/formations", response_model=list[PublicFormationCardRead])
def get_school_formations(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = _public_org(db, school_key)
    public_school_read(db, org)
    return list_public_formations(db, org)


@router.get(
    "/{school_key}/formations/{formation_slug}",
    response_model=PublicFormationDetailRead,
)
def get_school_formation(
    school_key: str,
    formation_slug: str,
    db: Session = Depends(get_db),
):
    org = _public_org(db, school_key)
    return public_formation_detail(db, org.slug, formation_slug)


@router.get("/{school_key}/favorites", response_model=list[PublicFormationCardRead])
def get_school_favorites(
    school_key: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = _public_org(db, school_key)
    public_school_read(db, org)
    return list_school_favorites(db, org, user)


@router.post("/{school_key}/favorites/{formation_slug}", response_model=list[PublicFormationCardRead])
def add_favorite(
    school_key: str,
    formation_slug: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = _public_org(db, school_key)
    public_school_read(db, org)
    return add_school_favorite(db, org, user, formation_slug)


@router.delete("/{school_key}/favorites/{formation_slug}", response_model=list[PublicFormationCardRead])
def remove_favorite(
    school_key: str,
    formation_slug: str,
    db: Session = Depends(get_db),
    user: UserRecord = Depends(get_current_user),
):
    org = _public_org(db, school_key)
    public_school_read(db, org)
    return remove_school_favorite(db, org, user, formation_slug)
