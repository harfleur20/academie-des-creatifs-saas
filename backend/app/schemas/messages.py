from datetime import datetime

from pydantic import BaseModel, Field


class MessageRecipientRead(BaseModel):
    id: int
    full_name: str
    role: str
    avatar_url: str | None = None


class SchoolMessageRead(BaseModel):
    id: int
    thread_id: int
    sender_user_id: int
    sender_name: str
    body: str
    created_at: datetime


class SchoolThreadRead(BaseModel):
    id: int
    subject: str
    participants: list[MessageRecipientRead]
    last_message: SchoolMessageRead | None
    unread_count: int
    last_message_at: datetime | None


class SchoolThreadDetail(SchoolThreadRead):
    messages: list[SchoolMessageRead]


class CreateSchoolThread(BaseModel):
    participant_ids: list[int] = Field(min_length=1, max_length=8)
    subject: str = Field(default="", max_length=255)
    body: str = Field(min_length=1, max_length=5000)


class CreateSchoolMessage(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
