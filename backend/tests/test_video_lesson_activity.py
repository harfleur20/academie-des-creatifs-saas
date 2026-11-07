from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_academic_suite import build_db, ctx, seed

from app.models.entities import (
    AssignmentRecord,
    ChapterRecord,
    CourseRecord,
    LessonProgressRecord,
    ResourceRecord,
)
from app.schemas.academic import QuizAttemptPayload, QuizCreate, QuizQuestionCreate
from app.schemas.formations import LessonCreate
from app.services.formations import create_lesson, publish_lesson, update_lesson
from app.services.resources_quizzes import create_quiz, set_quiz_status, submit_quiz_attempt


def school_with_activities():
    db = build_db()
    org, teacher, student, _classmate, session, enrollment, _ce, lesson, _day = seed(db)
    tenant = ctx(db, org, teacher)
    quiz = create_quiz(db, tenant, session.id, QuizCreate(
        title="Quiz vidéo", questions=[QuizQuestionCreate(text="Oui ?", options=["Non", "Oui"], correct_index=1)],
    ))
    set_quiz_status(db, tenant, quiz.id, "active")
    assignment = AssignmentRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Exercice vidéo",
        due_date=datetime.now(UTC) + timedelta(days=3),
    )
    resource = ResourceRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Support vidéo",
        resource_type="link", url="https://example.com/support",
    )
    db.add_all([assignment, resource])
    db.commit()
    chapter = db.get(ChapterRecord, lesson.chapter_id)
    course = db.get(CourseRecord, chapter.course_id)
    place = (session.formation_id, session.id, course.id, chapter.id)
    return db, org, tenant, ctx(db, org, student), enrollment, place, quiz.id, assignment.id, resource.id


def video(title="Leçon vidéo", url="https://example.com/video.mp4", **links) -> LessonCreate:
    return LessonCreate(title=title, lesson_type="video", video_url=url, order_index=1, **links)


def progress_kept(db, enrollment_id, lesson_id) -> bool:
    return db.scalar(select(LessonProgressRecord.id).where(
        LessonProgressRecord.enrollment_id == enrollment_id, LessonProgressRecord.lesson_id == lesson_id,
    )) is not None


def test_a_video_lesson_switches_its_complementary_activity_without_losing_progress() -> None:
    db, org, tenant, _student, enrollment, place, quiz_id, assignment_id, resource_id = school_with_activities()
    detail = create_lesson(db, tenant, *place, video(quiz_id=quiz_id))
    lesson = detail.sessions[0].courses[0].chapters[0].lessons[-1]
    assert lesson.quiz_id == quiz_id
    db.add(LessonProgressRecord(organization_id=org.id, enrollment_id=enrollment.id, lesson_id=lesson.id, completed_at=datetime.now(UTC)))
    db.commit()

    for links in ({"assignment_id": assignment_id}, {"resource_id": resource_id}, {}):
        update_lesson(db, tenant, *place, lesson.id, video(**links))
        assert progress_kept(db, enrollment.id, lesson.id), links

    update_lesson(db, tenant, *place, lesson.id, video(url="https://example.com/other.mp4"))
    assert not progress_kept(db, enrollment.id, lesson.id)


def test_a_video_lesson_carries_a_single_complementary_activity() -> None:
    db, _org, tenant, _student, _enrollment, place, quiz_id, assignment_id, _resource_id = school_with_activities()
    with pytest.raises(HTTPException) as refused:
        create_lesson(db, tenant, *place, video(quiz_id=quiz_id, assignment_id=assignment_id))
    assert refused.value.status_code == 422


def test_passing_the_complementary_quiz_does_not_complete_the_video() -> None:
    db, _org, tenant, student, enrollment, place, quiz_id, _assignment_id, _resource_id = school_with_activities()
    detail = create_lesson(db, tenant, *place, video(quiz_id=quiz_id))
    lesson_id = detail.sessions[0].courses[0].chapters[0].lessons[-1].id
    publish_lesson(db, tenant, *place, lesson_id)
    submit_quiz_attempt(db, student, quiz_id, QuizAttemptPayload(answers=[1]))
    assert not progress_kept(db, enrollment.id, lesson_id)
