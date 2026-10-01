from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FormationCreate(BaseModel):
    slug: str = Field(
        min_length=2,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=5000)


class FormationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    slug: str
    title: str
    description: str
    status: str
    created_at: datetime
