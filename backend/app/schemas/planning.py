from datetime import datetime
from typing import Literal

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
    delivery_status: str | None
    report_summary: str | None
    report_submitted_at: datetime | None
    feedback_count: int
    average_rating: float | None
    my_feedback: "CourseDayFeedbackRead | None"
    can_edit: bool
    created_at: datetime


class SessionPlanningRead(BaseModel):
    session_id: int
    formation_id: int
    formation_title: str
    format_type: str
    live_enabled: bool
    session_label: str
    session_start_date: str
    session_end_date: str
    course_days: list[CourseDayRead]


class LiveRoomRead(BaseModel):
    course_day_id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    domain: str
    room_name: str
    external_api_url: str
    token: str
    moderator: bool


class CourseDayReportSubmit(BaseModel):
    delivery_status: Literal["held", "partial", "not_held", "interrupted"]
    summary: str = Field(min_length=10, max_length=5000)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("Le compte rendu doit contenir au moins 10 caractères.")
        return cleaned


class CourseDayFeedbackSubmit(BaseModel):
    rating: int = Field(ge=1, le=5)
    delivery_status: Literal["held", "partial", "not_held"]
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CourseDayFeedbackRead(BaseModel):
    id: int
    rating: int
    delivery_status: Literal["held", "partial", "not_held"]
    comment: str | None
    created_at: datetime
    updated_at: datetime


class CourseDayFeedbackReviewRead(CourseDayFeedbackRead):
    student_name: str


class SchoolCourseDayReportRead(BaseModel):
    course_day_id: int
    session_id: int
    formation_title: str
    session_label: str
    teacher_name: str | None
    title: str
    scheduled_at: datetime
    delivery_status: Literal["held", "partial", "not_held", "interrupted"]
    summary: str
    submitted_at: datetime
    feedback_count: int
    average_rating: float | None
