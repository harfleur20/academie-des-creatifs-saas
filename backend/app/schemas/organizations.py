from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, computed_field

from app.core.config import settings


def school_subdomain_url(subdomain: str | None) -> str | None:
    """The school's own address, when this deployment serves the subdomains of its base domain.

    A local setup can name the production base domain while running on localhost: its
    subdomains are not served there, so the school stays on its /school/<slug> pages.
    """
    base = settings.saas_base_domain
    app = urlsplit(settings.frontend_url)
    host = (app.hostname or "").lower()
    if not subdomain or not base or not (host == base or host.endswith(f".{base}")):
        return None
    port = f":{app.port}" if app.port else ""
    return f"{app.scheme}://{subdomain}.{base}{port}"


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    # The plan picked on the landing page: the school still starts with the trial.
    plan_code: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_-]+$")
    billing_interval: Literal["monthly", "annual"] | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    contact_email: EmailStr | None = None
    timezone: str | None = Field(default=None, min_length=2, max_length=80)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    logo_url: HttpUrl | None = None
    primary_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )
    secondary_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )
    accent_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )
    direction_accent_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
    )
    direction_sidebar_collapsed: bool | None = None
    direction_sidebar_collapse_enabled: bool | None = None


class OrganizationDeletionRequest(BaseModel):
    confirmation_name: str = Field(min_length=2, max_length=180)


class OrganizationPolicyRead(BaseModel):
    name_change_cooldown_days: int


class OrganizationCreationCapacityRead(BaseModel):
    owned_organizations: int
    maximum_organizations: int | None
    can_create: bool
    plan_code: str | None = None
    plan_name: str | None = None


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_changed_at: datetime | None
    slug: str
    subdomain: str | None
    status: str
    deletion_requested_at: datetime | None = None
    deletion_scheduled_at: datetime | None = None
    is_active: bool
    contact_email: str | None
    timezone: str
    locale: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    direction_accent_color: str | None
    direction_sidebar_collapsed: bool
    direction_sidebar_collapse_enabled: bool
    created_at: datetime

    @computed_field
    @property
    def public_site_url(self) -> str | None:
        return school_subdomain_url(self.subdomain)


class OrganizationUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class OrganizationMemberRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str


class OrganizationMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    role: str
    status: str
    roles: list[OrganizationMemberRoleRead] = []
    user: OrganizationUserSummary


class OrganizationMemberCreate(BaseModel):
    user_id: int
    role: str = Field(pattern=r"^(owner|admin|manager|teacher|student)$")


class OrganizationMemberUpdate(BaseModel):
    role: str | None = Field(
        default=None,
        pattern=r"^(owner|admin|manager|teacher|student)$",
    )
    status: str | None = Field(
        default=None,
        pattern=r"^(active|suspended)$",
    )


class OrganizationMemberFunctionalRolesUpdate(BaseModel):
    functional_roles: list[str] = Field(
        default_factory=list,
        max_length=2,
    )


class OrganizationAccessProfileRead(BaseModel):
    organization_id: int
    primary_role: str
    roles: list[str]
    spaces: list[str]
    default_space: str


class OrganizationInvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(pattern=r"^(admin|manager|teacher)$")


class OrganizationInvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    email: str
    role: str
    status: str
    invited_by_user_id: int | None
    expires_at: datetime
    created_at: datetime


class OrganizationInvitationCreated(OrganizationInvitationRead):
    acceptance_token: str


class OrganizationInvitationPreview(BaseModel):
    organization_id: int
    organization_slug: str
    organization_name: str
    favicon_url: str | None = None
    white_label: bool = False
    email: str
    role: str
    expires_at: datetime
    logo_url: str | None = None
    primary_color: str
    secondary_color: str


class OrganizationInvitationAcceptResult(BaseModel):
    organization: OrganizationRead
    membership: OrganizationMemberRead



class OrganizationSubdomainUpdate(BaseModel):
    subdomain: str | None = Field(
        default=None,
        max_length=63,
        pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    )


class OrganizationDomainCreate(BaseModel):
    hostname: str = Field(min_length=3, max_length=253)


class OrganizationDomainRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    hostname: str
    status: str
    verification_token: str
    is_primary: bool
    verified_at: datetime | None
    created_at: datetime


class OrganizationDomainConfigRead(BaseModel):
    base_domain: str | None
    cname_target: str | None
    verification_record_prefix: str = "_academie-verification"


class OrganizationHostBrandingRead(BaseModel):
    organization_id: int
    name: str
    slug: str
    subdomain: str | None
    hostname: str
    locale: str = "fr-FR"
    logo_url: str | None
    auth_background_image_url: str | None = None
    auth_show_school_name: bool = True
    primary_color: str
    secondary_color: str
    accent_color: str
