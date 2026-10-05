from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    FormationRecord,
    OrganizationInvitationRecord,
    OrganizationLegalProfileRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
)
from app.schemas.onboarding import OnboardingStatusRead, OnboardingStepRead
from app.services.membership_roles import effective_member_roles
from app.services.publication import billing_readiness_issues
from app.services.tenancy import TenantContext


TEAM_ROLES = {"admin", "manager", "teacher"}


def get_onboarding_status(
    db: Session,
    tenant: TenantContext,
) -> OnboardingStatusRead:
    organization = tenant.organization

    active_members = list(
        db.scalars(
            select(OrganizationMemberRecord)
            .options(selectinload(OrganizationMemberRecord.roles))
            .where(
                OrganizationMemberRecord.organization_id == tenant.organization_id,
                OrganizationMemberRecord.status == "active",
            )
        ).all()
    )
    active_team_count = sum(
        1
        for member in active_members
        if effective_member_roles(member).intersection(TEAM_ROLES)
    )
    pending_team_invites = int(
        db.scalar(
            select(func.count(OrganizationInvitationRecord.id)).where(
                OrganizationInvitationRecord.organization_id == tenant.organization_id,
                OrganizationInvitationRecord.status == "pending",
                OrganizationInvitationRecord.expires_at > datetime.now(UTC),
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
    site = db.scalar(
        select(OrganizationPublicSiteRecord).where(
            OrganizationPublicSiteRecord.organization_id == tenant.organization_id,
        )
    )
    legal = db.scalar(select(OrganizationLegalProfileRecord).where(
        OrganizationLegalProfileRecord.organization_id == tenant.organization_id,
    ))

    steps = [
        OnboardingStepRead(
            key="school",
            label="École créée",
            description="Votre espace école est actif et isolé.",
            completed=True,
            path="/app/manage",
        ),
        OnboardingStepRead(
            key="identity",
            label="Compléter l’identité",
            description="Ajoutez au minimum l’email de contact de votre école.",
            completed=bool((organization.contact_email or "").strip()),
            path="/app/manage/settings",
        ),
        OnboardingStepRead(
            key="address",
            label="Configurer l’adresse",
            description="Choisissez le sous-domaine utilisé par votre école.",
            completed=bool((organization.subdomain or "").strip()),
            path="/app/manage/settings",
        ),
        OnboardingStepRead(
            key="matricule",
            label="Confirmer les matricules",
            description="Validez le préfixe proposé avant d'inviter l'équipe ou d'inscrire des étudiants.",
            completed=bool(site and site.student_code_prefix.strip() and site.student_code_prefix_confirmed_at),
            path="/app/manage/site-public",
        ),
        OnboardingStepRead(
            key="team",
            label="Construire l’équipe",
            description="Ajoutez ou invitez un administrateur, manager ou professeur.",
            completed=(active_team_count + pending_team_invites) > 0,
            path="/app/manage/team",
        ),
        OnboardingStepRead(
            key="billing",
            label="Préparer la facturation",
            description="Renseignez la raison sociale, l'adresse légale, l'email et la devise des factures.",
            completed=bool(legal and not billing_readiness_issues(legal)),
            path="/app/manage/site-public",
        ),
        OnboardingStepRead(
            key="formation",
            label="Créer la première formation",
            description="Créez le premier espace pédagogique de votre école.",
            completed=formation_count > 0,
            path="/app/manage/onboarding",
        ),
    ]

    previous_complete = True
    for step in steps:
        step.available = previous_complete
        previous_complete = previous_complete and step.completed

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
