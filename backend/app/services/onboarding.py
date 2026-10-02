from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    FormationRecord,
    OrganizationInvitationRecord,
    OrganizationMemberRecord,
)
from app.schemas.onboarding import OnboardingStatusRead, OnboardingStepRead
from app.services.tenancy import TenantContext


TEAM_ROLES = {"admin", "manager", "teacher"}


def get_onboarding_status(
    db: Session,
    tenant: TenantContext,
) -> OnboardingStatusRead:
    organization = tenant.organization

    active_team_count = int(
        db.scalar(
            select(func.count(OrganizationMemberRecord.id)).where(
                OrganizationMemberRecord.organization_id == tenant.organization_id,
                OrganizationMemberRecord.status == "active",
                OrganizationMemberRecord.role.in_(TEAM_ROLES),
            )
        )
        or 0
    )
    pending_team_invites = int(
        db.scalar(
            select(func.count(OrganizationInvitationRecord.id)).where(
                OrganizationInvitationRecord.organization_id == tenant.organization_id,
                OrganizationInvitationRecord.status == "pending",
                OrganizationInvitationRecord.role.in_(TEAM_ROLES),
            )
        )
        or 0
    )
    formation_count = int(
        db.scalar(
            select(func.count(FormationRecord.id)).where(
                FormationRecord.organization_id == tenant.organization_id,
            )
        )
        or 0
    )

    steps = [
        OnboardingStepRead(
            key="school",
            label="École créée",
            description="Votre espace école est actif et isolé.",
            completed=True,
            path="/app",
        ),
        OnboardingStepRead(
            key="identity",
            label="Compléter l’identité",
            description="Ajoutez au minimum l’email de contact de votre école.",
            completed=bool(organization.contact_email),
            path="/app/settings",
        ),
        OnboardingStepRead(
            key="address",
            label="Configurer l’adresse",
            description="Choisissez le sous-domaine utilisé par votre école.",
            completed=bool(organization.subdomain),
            path="/app/settings",
        ),
        OnboardingStepRead(
            key="team",
            label="Construire l’équipe",
            description="Ajoutez ou invitez un administrateur, manager ou professeur.",
            completed=(active_team_count + pending_team_invites) > 0,
            path="/app/team",
        ),
        OnboardingStepRead(
            key="formation",
            label="Créer la première formation",
            description="Créez le premier espace pédagogique de votre école.",
            completed=formation_count > 0,
            path="/app/onboarding",
        ),
    ]

    completed_steps = sum(1 for step in steps if step.completed)
    total_steps = len(steps)
    next_step = next((step for step in steps if not step.completed), None)

    return OnboardingStatusRead(
        completed_steps=completed_steps,
        total_steps=total_steps,
        progress_percent=round((completed_steps / total_steps) * 100),
        is_complete=completed_steps == total_steps,
        next_step=next_step,
        steps=steps,
    )
