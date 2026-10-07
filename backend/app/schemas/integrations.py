from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class OpenAIIntegrationWrite(BaseModel):
    api_key: str = Field(min_length=20, max_length=500)
    model: str = Field(default="gpt-6-luna", min_length=2, max_length=120)


class OpenAIIntegrationRead(BaseModel):
    provider: Literal["openai"] = "openai"
    connected: bool
    status: str
    model: str | None = None
    connected_at: datetime | None = None
    last_tested_at: datetime | None = None
    last_error: str | None = None


class AiGenerationBasePayload(BaseModel):
    session_id: int
    topic: str = Field(min_length=3, max_length=5000)
    level: str | None = Field(default=None, max_length=200)
    objectives: str | None = Field(default=None, max_length=5000)


class AiCourseDraftPayload(AiGenerationBasePayload):
    chapters_count: int = Field(default=3, ge=1, le=12)
    lessons_per_chapter: int = Field(default=3, ge=1, le=12)


class AiLessonDraft(BaseModel):
    title: str
    content: str


class AiChapterDraft(BaseModel):
    title: str
    lessons: list[AiLessonDraft]


class AiCourseDraft(BaseModel):
    title: str
    description: str
    chapters: list[AiChapterDraft]


class AiQuizDraftPayload(AiGenerationBasePayload):
    course_day_id: int | None = None
    questions_count: int = Field(default=10, ge=4, le=40)
    options_per_question: int = Field(default=4, ge=4, le=6)


class AiQuizQuestionDraft(BaseModel):
    text: str
    options: list[str]
    correct_index: int


class AiQuizDraft(BaseModel):
    title: str
    duration_minutes: int | None = None
    questions: list[AiQuizQuestionDraft]


class AiAssignmentDraftPayload(AiGenerationBasePayload):
    course_day_id: int | None = None
    duration_days: int = Field(default=7, ge=1, le=90)
    is_final_project: bool = False
    assignment_type: str | None = Field(default=None, max_length=80)


class AiAssignmentDraft(BaseModel):
    title: str
    brief: dict[str, Any] = Field(default_factory=dict)
    instructions: str
    is_final_project: bool
    duration_days: int
