"""School-scoped equivalents of the mother site's course availability rules."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentRecord, ChapterRecord, CourseRecord, FormationRecord, FormationSessionRecord, LessonRecord,
    QuizRecord, ResourceRecord, SessionCourseDayRecord,
)


PARIS = ZoneInfo("Europe/Paris")


def dashboard_type(formation: FormationRecord) -> str:
    return "classic" if formation.format_type == "ligne" else "guided"


def current_utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def session_starts_at(session: FormationSessionRecord) -> datetime:
    return datetime.combine(session.start_date, time.min, tzinfo=PARIS).astimezone(UTC)


def learning_is_open(
    formation: FormationRecord,
    session: FormationSessionRecord,
    *,
    now: datetime | None = None,
) -> bool:
    if session.status == "cancelled":
        return False
    if dashboard_type(formation) == "classic":
        return True
    return current_utc(now) >= session_starts_at(session)


def require_learning_open(
    formation: FormationRecord,
    session: FormationSessionRecord,
) -> None:
    if not learning_is_open(formation, session):
        raise HTTPException(409, "Cette session n'a pas encore commencé ou a été annulée.")


def guided_activity_available(
    formation: FormationRecord,
    session: FormationSessionRecord,
    *,
    scheduled_at: datetime | None = None,
    day: SessionCourseDayRecord | None = None,
    published_at: datetime | None = None,
    now: datetime | None = None,
) -> bool:
    if session.status == "cancelled":
        return False
    if day is not None and day.status in {"cancelled", "not_held", "missed"}:
        return False
    if not learning_is_open(formation, session, now=now):
        if published_at is None or current_utc(published_at) >= session_starts_at(session):
            return False
        # A resource explicitly published before the session is preparatory.
        return current_utc(now) >= current_utc(published_at)
    opening = session_starts_at(session)
    if scheduled_at is not None:
        opening = max(opening, current_utc(scheduled_at))
    if day is not None:
        opening = max(opening, current_utc(day.scheduled_at))
    if published_at is not None:
        opening = max(opening, current_utc(published_at))
    return current_utc(now) >= opening


def lesson_access(
    db: Session,
    formation: FormationRecord,
    session: FormationSessionRecord,
    lesson: LessonRecord,
    *,
    now: datetime | None = None,
) -> tuple[datetime | None, bool]:
    """Return the opening date and availability of a linked lesson."""
    opening_times = []
    if dashboard_type(formation) == "guided":
        opening_times.append(session_starts_at(session))
    if lesson.available_at is not None:
        opening_times.append(current_utc(lesson.available_at))

    day = None
    if lesson.quiz_id is not None:
        quiz = db.get(QuizRecord, lesson.quiz_id)
        if quiz is None or quiz.organization_id != lesson.organization_id or quiz.session_id != session.id or quiz.status not in {"active", "closed"}:
            return max(opening_times) if opening_times else None, False
        if quiz.scheduled_at is not None:
            opening_times.append(current_utc(quiz.scheduled_at))
        day = db.get(SessionCourseDayRecord, quiz.course_day_id) if quiz.course_day_id else None
    elif lesson.assignment_id is not None:
        assignment = db.get(AssignmentRecord, lesson.assignment_id)
        if assignment is None or assignment.organization_id != lesson.organization_id or assignment.session_id != session.id:
            return max(opening_times) if opening_times else None, False
        day = db.get(SessionCourseDayRecord, assignment.course_day_id) if assignment.course_day_id else None
    elif lesson.resource_id is not None:
        resource = db.get(ResourceRecord, lesson.resource_id)
        if resource is None or resource.organization_id != lesson.organization_id or resource.session_id != session.id or resource.published_at is None:
            return max(opening_times) if opening_times else None, False
        opening_times.append(current_utc(resource.published_at))
        day = db.get(SessionCourseDayRecord, resource.course_day_id) if resource.course_day_id else None
    if day is not None:
        if day.organization_id != lesson.organization_id or day.session_id != session.id or day.status in {"cancelled", "not_held", "missed"}:
            return max(opening_times) if opening_times else None, False
        opening_times.append(current_utc(day.scheduled_at))
    opening = max(opening_times) if opening_times else None
    return opening, learning_is_open(formation, session, now=now) and (opening is None or current_utc(now) >= opening)


def linked_lesson_gate(
    db: Session,
    formation: FormationRecord,
    session: FormationSessionRecord,
    activity_type: str,
    activity_id: int,
    *,
    now: datetime | None = None,
) -> tuple[datetime | None, bool] | None:
    if activity_type not in {"quiz", "assignment"}:
        raise ValueError("Unsupported lesson activity")
    lesson = db.scalar(
        select(LessonRecord)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            LessonRecord.organization_id == session.organization_id,
            ChapterRecord.organization_id == session.organization_id,
            CourseRecord.organization_id == session.organization_id,
            CourseRecord.session_id == session.id,
            getattr(LessonRecord, f"{activity_type}_id") == activity_id,
        )
    )
    if lesson is None:
        return None
    course = db.get(CourseRecord, db.get(ChapterRecord, lesson.chapter_id).course_id)
    opening, available = lesson_access(db, formation, session, lesson, now=now)
    return opening, available and course.status == "published"
