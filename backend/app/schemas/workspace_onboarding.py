from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TeacherProfessionalProfileUpdate(BaseModel):
    professional_title: str = Field(min_length=2, max_length=180)
    experience_years: int = Field(ge=0, le=80)
    activity_domains: list[str] = Field(min_length=1, max_length=20)
    bio: str = Field(min_length=40, max_length=2000)
    skills: list[str] = Field(min_length=1, max_length=40)
    portfolio_url: str | None = Field(default=None, max_length=1024)
    linkedin_url: str | None = Field(default=None, max_length=1024)
    behance_url: str | None = Field(default=None, max_length=1024)
    github_url: str | None = Field(default=None, max_length=1024)
    website_url: str | None = Field(default=None, max_length=1024)
    city: str = Field(min_length=2, max_length=120)
    country: str = Field(min_length=2, max_length=120)
    languages: list[str] = Field(min_length=1, max_length=20)
    whatsapp_phone: str = Field(min_length=4, max_length=64)
    whatsapp_country: str = Field(min_length=2, max_length=2)


class TeacherAssignedSessionRead(BaseModel):
    session_id: int
    formation_title: str
    session_label: str
    start_date: date
    end_date: date
    role: str
    assigned_at: datetime
    course_titles: list[str] = Field(default_factory=list)


class TeacherProfessionalProfileRead(BaseModel):
    organization_id: int
    organization_name: str
    user_id: int
    full_name: str
    email: str
    phone: str | None
    avatar_url: str | None
    teacher_code: str | None
    professional_title: str
    experience_years: int
    activity_domains: list[str]
    bio: str
    skills: list[str]
    portfolio_url: str | None
    portfolio_file_name: str | None
    cv_file_name: str | None
    linkedin_url: str | None
    behance_url: str | None
    github_url: str | None
    website_url: str | None
    city: str | None
    country: str | None
    languages: list[str]
    whatsapp_phone: str | None
    whatsapp_country: str | None
    whatsapp_phone_legacy: bool
    whatsapp_phone_verified_at: datetime | None
    profile_completed_at: datetime | None
    is_complete: bool
    registered_at: datetime | None = None
    joined_at: datetime | None = None
    membership_status: str | None = None
    assigned_sessions: list[TeacherAssignedSessionRead] = Field(default_factory=list)


class PhoneCountryRead(BaseModel):
    code: str
    dial_code: str


class OrganizationCharterUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    content: str = Field(min_length=20, max_length=10000)
    is_enabled: bool


class OrganizationCharterRead(BaseModel):
    id: int
    organization_id: int
    audience: Literal["teacher", "student"]
    title: str
    content: str
    is_enabled: bool
    version: int
    accepted_current_version: bool
    accepted_at: datetime | None = None
