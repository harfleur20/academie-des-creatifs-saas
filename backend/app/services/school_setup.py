from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import OrganizationPublicSiteRecord, OrganizationRecord


def confirmed_matricule_prefix(
    db: Session,
    organization_id: int,
) -> OrganizationPublicSiteRecord | None:
    site = db.scalar(
        select(OrganizationPublicSiteRecord).where(
            OrganizationPublicSiteRecord.organization_id == organization_id,
        )
    )
    if site and site.student_code_prefix.strip() and site.student_code_prefix_confirmed_at:
        return site
    return None


def require_confirmed_matricule_prefix(db: Session, organization_id: int) -> OrganizationPublicSiteRecord:
    site = confirmed_matricule_prefix(db, organization_id)
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Confirmez d'abord le préfixe des matricules dans "
                "Gestion > Site public avant de créer des comptes enseignant ou étudiant."
            ),
        )
    return site


def require_team_setup(db: Session, organization: OrganizationRecord) -> None:
    missing: list[str] = []
    if not (organization.contact_email or "").strip():
        missing.append("l'email de contact (Paramètres)")
    if not (organization.subdomain or "").strip():
        missing.append("l'adresse de l'école (Paramètres)")
    if confirmed_matricule_prefix(db, organization.id) is None:
        missing.append("le préfixe des matricules (Site public)")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Avant d'inviter l'équipe, configurez " + ", ".join(missing) + ".",
        )


def require_teacher_invitation_readiness(db: Session, organization: OrganizationRecord) -> None:
    from app.services.onboarding import get_organization_onboarding_status

    onboarding = get_organization_onboarding_status(db, organization)
    if onboarding.is_complete:
        return

    next_step = onboarding.next_step
    pending_step = f" Étape en attente : {next_step.label}." if next_step else ""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Terminez les 7 étapes de mise en route de l’école avant d’inviter "
            f"un enseignant.{pending_step}"
        ),
    )


def require_identity_address(organization: OrganizationRecord) -> None:
    if not (organization.contact_email or "").strip() or not (organization.subdomain or "").strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configurez l'email de contact et l'adresse de l'école dans Paramètres avant de confirmer les matricules.",
        )
