from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


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


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    status: str
    is_active: bool
    contact_email: str | None
    timezone: str
    locale: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    created_at: datetime


class OrganizationUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class OrganizationMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    role: str
    status: str
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


class OrganizationInvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(pattern=r"^(admin|manager|teacher|student)$")


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
    hostname: str
    logo_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
