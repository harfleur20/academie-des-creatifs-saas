from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.commerce import (
    PublicFormationCardRead,
    PublicFormationDetailRead,
    PublicHomeRead,
    PublicSchoolRead,
)
from app.services.public_catalog import (
    get_public_organization,
    list_public_formations,
    public_formation_detail,
    public_home,
    public_school_read,
)
from app.services.school_branding import get_or_create_identity_records


router = APIRouter(prefix="/public/schools", tags=["public-school"])


@router.get("/{school_key}", response_model=PublicHomeRead)
def get_school_home(
    school_key: str,
    db: Session = Depends(get_db),
):
    return public_home(db, school_key)


@router.get("/{school_key}/identity", response_model=PublicSchoolRead)
def get_school_identity_public(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = get_public_organization(db, school_key)
    return public_school_read(db, org)


@router.get("/{school_key}/contact-channels")
def get_school_contact_channels(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = get_public_organization(db, school_key)
    public_school_read(db, org)
    _site, _legal, communications, _certification = get_or_create_identity_records(db, org)
    return {"whatsapp_phone": communications.whatsapp_phone}


@router.get("/{school_key}/formations", response_model=list[PublicFormationCardRead])
def get_school_formations(
    school_key: str,
    db: Session = Depends(get_db),
):
    org = get_public_organization(db, school_key)
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
    return public_formation_detail(db, school_key, formation_slug)
