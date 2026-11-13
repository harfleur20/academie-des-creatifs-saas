"""The student's transcript, for one enrollment (app/services/transcripts.py)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class TranscriptLineRead(BaseModel):
    label: str
    date: date | None
    score: float
    max_score: float
    score_20: float
    note: str
    # False for the automatic quiz grades: the official average leaves them out.
    counted: bool


class TranscriptGroupRead(BaseModel):
    key: Literal["assignments", "exams", "session_grades", "teacher_grades", "quizzes"]
    label: str
    lines: list[TranscriptLineRead]


class TranscriptRead(BaseModel):
    enrollment_id: int
    # Provisional while the session runs; final once it has ended or the enrollment is completed.
    status: Literal["provisional", "final"]
    issued_at: datetime
    school_name: str
    logo_url: str | None
    legal_name: str | None
    legal_address: str | None
    signer_name: str | None
    signer_title: str | None
    white_label: bool
    student_name: str
    student_code: str | None
    formation_title: str
    format_label: str
    training_hours: int | None
    session_label: str
    session_start: date
    session_end: date
    groups: list[TranscriptGroupRead]
    # The same average as the badge and the pedagogical follow-up, on 20.
    average_20: float | None
    mention: str | None
    counted_sessions: int
    attended_sessions: int
    attendance_pct: float | None
    badge_label: str | None


class TranscriptSummaryRead(BaseModel):
    enrollment_id: int
    formation_title: str
    session_label: str
    status: Literal["provisional", "final"]
    average_20: float | None
