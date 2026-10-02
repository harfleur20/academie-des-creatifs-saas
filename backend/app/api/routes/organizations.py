from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_non_support_user, get_tenant_context
from app.db.session import get_db
from app.models.entities import OrganizationMemberRecord, UserRecord
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationInvitationAcceptResult,
    OrganizationInvitationCreate,
    OrganizationInvitationCreated,
    OrganizationInvitationPreview,
    OrganizationInvitationRead,
    OrganizationAccessProfileRead,
    OrganizationMemberCreate,
    OrganizationMemberFunctionalRolesUpdate,
    OrganizationMemberRead,
    OrganizationMemberUpdate,
    OrganizationPolicyRead,
    OrganizationRead,
    OrganizationUpdate,
    OrganizationSubdomainUpdate,
    OrganizationDomainCreate,
    OrganizationDomainRead,
    OrganizationDomainConfigRead,
    OrganizationHostBrandingRead,
)
from app.core.config import settings
from app.services.communication_delivery import process_communication_outbox
from app.services.organization_domains import (
    create_domain,
    delete_domain,
    list_domains,
    resolve_organization_for_hostname,
    set_primary_domain,
    update_subdomain,
    verify_domain,
)
from app.services.organization_management import (
    accept_invitation,
    add_member,
    cancel_invitation,
    create_invitation,
    get_invitation_preview,
    list_invitations,
    update_member,
    update_member_functional_roles,
    update_organization_settings,
)
from app.services.organizations import (
    OrganizationConflictError,
    create_organization,
    list_user_organizations,
)
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
def list_organizations_route(
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_non_support_user),
):
    return list_user_organizations(db, current_user)


@router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_route(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_non_support_user),
):
    try:
        return create_organization(db, user=current_user, payload=payload)
    except OrganizationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/current", response_model=OrganizationRead)
def get_current_organization(
    tenant: TenantContext = Depends(get_tenant_context),
):
    return tenant.organization


@router.patch("/current", response_model=OrganizationRead)
def update_current_organization(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return update_organization_settings(db, tenant, payload)


@router.get("/current/members", response_model=list[OrganizationMemberRead])
def list_current_members(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return list(
        db.scalars(
            select(OrganizationMemberRecord)
            .options(
                selectinload(OrganizationMemberRecord.user),
                selectinload(OrganizationMemberRecord.roles),
            )
            .where(
                OrganizationMemberRecord.organization_id == tenant.organization_id,
            )
            .order_by(
                OrganizationMemberRecord.status,
                OrganizationMemberRecord.role,
                OrganizationMemberRecord.id,
            )
        ).all()
    )


@router.post(
    "/current/members",
    response_model=OrganizationMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_current_member(
    payload: OrganizationMemberCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if payload.role in {"teacher", "student"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Les professeurs rejoignent l'école par invitation et "
                "les étudiants après l'achat d'une session."
            ),
        )
    user = db.get(UserRecord, payload.user_id)
    if user is None or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )
    return add_member(db, tenant, user=user, role=payload.role)


@router.patch(
    "/current/members/{member_id}",
    response_model=OrganizationMemberRead,
)
def update_current_member(
    member_id: int,
    payload: OrganizationMemberUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return update_member(db, tenant, member_id, payload)


@router.get(
    "/current/access-profile",
    response_model=OrganizationAccessProfileRead,
)
def get_current_access_profile(
    tenant: TenantContext = Depends(get_tenant_context),
):
    roles = sorted(tenant.organization_roles)
    spaces: list[str] = []
    if tenant.user.platform_role == "super_admin" or tenant.support_mode or set(roles).intersection({"owner", "admin", "manager"}):
        spaces.append("manage")
    if "teacher" in roles:
        spaces.append("teacher")
    if "student" in roles:
        spaces.append("student")

    default_space = (
        "manage"
        if "manage" in spaces
        else "teacher"
        if "teacher" in spaces
        else "student"
        if "student" in spaces
        else ""
    )
    return OrganizationAccessProfileRead(
        organization_id=tenant.organization_id,
        primary_role=tenant.organization_role,
        roles=roles,
        spaces=spaces,
        default_space=default_space,
    )


@router.put(
    "/current/members/{member_id}/functional-roles",
    response_model=OrganizationMemberRead,
)
def update_current_member_functional_roles(
    member_id: int,
    payload: OrganizationMemberFunctionalRolesUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return update_member_functional_roles(
        db,
        tenant,
        member_id,
        payload,
    )


@router.get(
    "/current/invitations",
    response_model=list[OrganizationInvitationRead],
)
def list_current_invitations(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_invitations(db, tenant)


@router.post(
    "/current/invitations",
    response_model=OrganizationInvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_current_invitation(
    payload: OrganizationInvitationCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    invitation, token = create_invitation(db, tenant, payload)
    process_communication_outbox(
        db,
        organization_id=tenant.organization_id,
        limit=20,
    )
    return OrganizationInvitationCreated(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        invited_by_user_id=invitation.invited_by_user_id,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        acceptance_token=token,
    )


@router.post(
    "/current/invitations/{invitation_id}/cancel",
    response_model=OrganizationInvitationRead,
)
def cancel_current_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return cancel_invitation(db, tenant, invitation_id)




@router.get(
    "/invitations/{token}",
    response_model=OrganizationInvitationPreview,
)
def preview_organization_invitation(
    token: str,
    db: Session = Depends(get_db),
):
    return OrganizationInvitationPreview(
        **get_invitation_preview(db, token=token)
    )

@router.post(
    "/invitations/{token}/accept",
    response_model=OrganizationInvitationAcceptResult,
)
def accept_organization_invitation(
    token: str,
    db: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_non_support_user),
):
    organization, membership = accept_invitation(
        db,
        current_user=current_user,
        token=token,
    )
    membership = db.scalar(
        select(OrganizationMemberRecord)
        .options(
            selectinload(OrganizationMemberRecord.user),
            selectinload(OrganizationMemberRecord.roles),
        )
        .where(OrganizationMemberRecord.id == membership.id)
    )
    return OrganizationInvitationAcceptResult(
        organization=OrganizationRead.model_validate(organization),
        membership=OrganizationMemberRead.model_validate(membership),
    )



@router.get("/policy", response_model=OrganizationPolicyRead)
def get_organization_policy():
    return OrganizationPolicyRead(
        name_change_cooldown_days=settings.organization_name_change_cooldown_days,
    )


@router.get("/domain-config", response_model=OrganizationDomainConfigRead)
def get_domain_config():
    return OrganizationDomainConfigRead(
        base_domain=settings.saas_base_domain or None,
        cname_target=settings.saas_cname_target or None,
    )


@router.get("/resolve-host", response_model=OrganizationHostBrandingRead)
def resolve_host_branding(
    hostname: str,
    db: Session = Depends(get_db),
):
    resolved = resolve_organization_for_hostname(db, hostname=hostname)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune école n'est associée à ce domaine.",
        )
    organization, normalized = resolved
    return OrganizationHostBrandingRead(
        organization_id=organization.id,
        name=organization.name,
        slug=organization.slug,
        subdomain=organization.subdomain,
        hostname=normalized,
        logo_url=organization.logo_url,
        primary_color=organization.primary_color,
        secondary_color=organization.secondary_color,
        accent_color=organization.accent_color,
    )


@router.patch("/current/subdomain", response_model=OrganizationRead)
def update_current_subdomain(
    payload: OrganizationSubdomainUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return update_subdomain(
        db,
        tenant,
        subdomain=payload.subdomain,
    )


@router.get("/current/domains", response_model=list[OrganizationDomainRead])
def list_current_domains(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_domains(db, tenant)


@router.post(
    "/current/domains",
    response_model=OrganizationDomainRead,
    status_code=status.HTTP_201_CREATED,
)
def create_current_domain(
    payload: OrganizationDomainCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_domain(
        db,
        tenant,
        hostname=payload.hostname,
    )


@router.post(
    "/current/domains/{domain_id}/verify",
    response_model=OrganizationDomainRead,
)
def verify_current_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return verify_domain(db, tenant, domain_id=domain_id)


@router.post(
    "/current/domains/{domain_id}/primary",
    response_model=OrganizationDomainRead,
)
def set_current_primary_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return set_primary_domain(db, tenant, domain_id=domain_id)


@router.delete(
    "/current/domains/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_current_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    delete_domain(db, tenant, domain_id=domain_id)
    return None
