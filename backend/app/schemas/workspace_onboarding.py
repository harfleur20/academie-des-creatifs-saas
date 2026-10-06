from datetime import datetime
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
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    languages: list[str] = Field(default_factory=list, max_length=20)


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
    profile_completed_at: datetime | None
    is_complete: bool


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
