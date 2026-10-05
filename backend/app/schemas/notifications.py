from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SchoolNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audience: str
    title: str
    message: str
    category: str
    tone: str
    action_label: str | None
    action_path: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=100)
