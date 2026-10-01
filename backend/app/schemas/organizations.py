from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    status: str
    is_active: bool
    created_at: datetime


class OrganizationMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    role: str
    status: str


class OrganizationMemberCreate(BaseModel):
    user_id: int
    role: str = Field(pattern=r"^(owner|admin|manager|teacher|student)$")
