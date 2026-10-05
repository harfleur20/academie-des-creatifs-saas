from typing import Literal

from pydantic import BaseModel, Field


class SupportRequestCreate(BaseModel):
    category: Literal["technical", "billing", "account", "pedagogy", "other"] = "technical"
    priority: Literal["normal", "urgent"] = "normal"
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=5000)
    page_url: str | None = Field(default=None, max_length=500)


class SupportRequestRead(BaseModel):
    reference: str
    message: str
