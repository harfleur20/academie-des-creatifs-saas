"""Complete lessons through the activity linked by the school."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import ChapterRecord, CourseRecord, LessonProgressRecord, LessonRecord


def complete_activity_lessons(
    db: Session,
    *,
    organization_id: int,
    session_id: int,
    enrollment_id: int,
    activity_type: str,
    activity_id: int,
) -> None:
    if activity_type not in {"quiz", "assignment"}:
        raise ValueError("Unsupported lesson activity")
    linked_id = getattr(LessonRecord, f"{activity_type}_id")
    lesson_ids = db.scalars(
        select(LessonRecord.id)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            LessonRecord.organization_id == organization_id,
            ChapterRecord.organization_id == organization_id,
            CourseRecord.organization_id == organization_id,
            CourseRecord.session_id == session_id,
            linked_id == activity_id,
        )
    ).all()
    for lesson_id in lesson_ids:
        exists = db.scalar(select(LessonProgressRecord.id).where(
            LessonProgressRecord.organization_id == organization_id,
            LessonProgressRecord.enrollment_id == enrollment_id,
            LessonProgressRecord.lesson_id == lesson_id,
        ))
        if exists is None:
            db.add(LessonProgressRecord(
                organization_id=organization_id,
                enrollment_id=enrollment_id,
                lesson_id=lesson_id,
                completed_at=datetime.now(UTC),
            ))
