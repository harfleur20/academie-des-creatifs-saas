from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord
from app.schemas.formations import FormationCreate
from app.services.tenancy import TenantContext, scoped_select


class FormationConflictError(ValueError):
    pass


def list_formations(
    db: Session,
    tenant: TenantContext,
) -> list[FormationRecord]:
    query = scoped_select(FormationRecord, tenant).order_by(
        FormationRecord.created_at.desc()
    )
    return list(db.scalars(query).all())


def get_formation(
    db: Session,
    tenant: TenantContext,
    formation_id: int,
) -> FormationRecord | None:
    return db.scalar(
        scoped_select(FormationRecord, tenant).where(
            FormationRecord.id == formation_id,
        )
    )


def create_formation(
    db: Session,
    tenant: TenantContext,
    payload: FormationCreate,
) -> FormationRecord:
    formation = FormationRecord(
        organization_id=tenant.organization_id,
        slug=payload.slug.strip().lower(),
        title=payload.title.strip(),
        description=payload.description.strip(),
    )
    db.add(formation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise FormationConflictError(
            "Une formation avec ce slug existe déjà dans cette organisation."
        ) from exc
    db.refresh(formation)
    return formation
