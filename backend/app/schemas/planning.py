from datetime import datetime

from pydantic import BaseModel, Field, field_validator


COURSE_DAY_STATUSES = r"^(planned|cancelled)$"


class CourseDayCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    scheduled_at: datetime
    duration_minutes: int = Field(default=90, ge=15, le=480)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()


class CourseDayUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    status: str | None = Field(default=None, pattern=COURSE_DAY_STATUSES)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class CourseDayDraftItem(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    scheduled_at: datetime
    duration_minutes: int = Field(default=90, ge=15, le=480)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()


class CourseDayDraftPublish(BaseModel):
    days: list[CourseDayDraftItem] = Field(min_length=1, max_length=40)


class CourseDayRead(BaseModel):
    id: int
    session_id: int
    teacher_id: int | None
    teacher_name: str | None
    title: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    can_edit: bool
    created_at: datetime


class SessionPlanningRead(BaseModel):
    session_id: int
    formation_id: int
    formation_title: str
    session_label: str
    session_start_date: str
    session_end_date: str
    course_days: list[CourseDayRead]
