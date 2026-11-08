from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_academic_suite import build_db, ctx, seed

from app.models.entities import (
    BadgeAwardRecord,
    ChapterRecord,
    CourseRecord,
    FormationRecord,
    LessonRecord,
    SessionProgramVersionRecord,
)
from app.schemas.academic import QuizCreate, QuizQuestionCreate
from app.schemas.assignments import AssignmentCreate, AssignmentUpdate
from app.schemas.formations import CourseUpdate, LessonCreate
from app.services.assignments import create_assignment, list_teacher_assignments, publish_assignment, update_assignment
from app.services.formations import create_lesson, get_formation_detail, publish_lesson, update_course, update_lesson
from app.services.learning_progress import mark_lesson_complete, student_progress
from app.services.program_versions import ensure_program_frozen
from app.services.resources_quizzes import create_quiz, set_quiz_status


def live_school():
    db = build_db()
    org, teacher, student, _classmate, session, enrollment, _ce, lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    chapter = db.get(ChapterRecord, lesson.chapter_id)
    place = (session.formation_id, session.id, chapter.course_id, chapter.id)
    return db, org, ctx(db, org, teacher), ctx(db, org, student), session, enrollment, lesson, day, place


def versions(db, session_id) -> int:
    return int(db.scalar(select(func.count(SessionProgramVersionRecord.id)).where(
        SessionProgramVersionRecord.session_id == session_id,
    )) or 0)


def test_a_started_complete_program_freezes_once() -> None:
    db, org, teacher, student, session, *_ = live_school()
    student_progress(db, student)
    student_progress(db, student)
    assert versions(db, session.id) == 1
    frozen = db.scalar(select(SessionProgramVersionRecord).where(SessionProgramVersionRecord.session_id == session.id))
    assert frozen.requirements_json["lesson_ids"] and frozen.requirements_json["course_day_ids"]
    formation = db.get(FormationRecord, session.formation_id)
    assert ensure_program_frozen(db, session, formation).id == frozen.id
    detail = get_formation_detail(db, teacher, session.formation_id)
    assert detail.sessions[0].program_frozen_at is not None and detail.sessions[0].program_missing == []


def test_an_incomplete_program_holds_the_badge_and_says_what_is_missing() -> None:
    db, org, teacher, student, session, _e, _lesson, day, _place = live_school()
    day.status = "cancelled"  # no course day left
    db.commit()
    badge = student_progress(db, student)[0].badge
    assert badge.level == "aventurier" and "en préparation" in badge.missing_requirements[0]
    assert versions(db, session.id) == 0
    assert "planifiez au moins une séance" in get_formation_detail(db, teacher, session.formation_id).sessions[0].program_missing


def test_a_badge_once_reached_does_not_go_down_when_new_work_is_published() -> None:
    db, org, teacher, student, session, enrollment, lesson, _day, place = live_school()
    mark_lesson_complete(db, student, lesson.id)
    before = student_progress(db, student)[0].badge
    assert before.level != "aventurier"
    for index in range(4):
        detail = create_lesson(db, teacher, *place, LessonCreate(title=f"Nouvelle {index}", content="Contenu", order_index=10 + index))
        publish_lesson(db, teacher, *place, detail.sessions[0].courses[0].chapters[0].lessons[-1].id)
    after = student_progress(db, student)[0].badge
    assert after.lesson_progress_pct < before.lesson_progress_pct  # the new lessons count...
    assert after.level == before.level  # ...but the level reached is kept
    assert db.scalar(select(BadgeAwardRecord.level).where(BadgeAwardRecord.enrollment_id == enrollment.id)) == before.level


def test_a_frozen_lesson_takes_text_corrections_only() -> None:
    db, org, teacher, student, session, _e, lesson, _day, place = live_school()
    student_progress(db, student)  # freezes the program
    update_lesson(db, teacher, *place, lesson.id, LessonCreate(title="Introduction corrigée", content="Contenu corrigé"))
    assert db.get(LessonRecord, lesson.id).title == "Introduction corrigée"
    with pytest.raises(HTTPException) as refused:
        update_lesson(db, teacher, *place, lesson.id, LessonCreate(
            title="Introduction", lesson_type="video", video_url="https://example.com/video.mp4",
        ))
    assert refused.value.status_code == 409 and "programme figé" in refused.value.detail

    detail = create_lesson(db, teacher, *place, LessonCreate(title="Ajoutée après", content="Texte", order_index=9))
    added = detail.sessions[0].courses[0].chapters[0].lessons[-1].id
    update_lesson(db, teacher, *place, added, LessonCreate(title="Ajoutée après", lesson_type="video", video_url="https://example.com/v.mp4", order_index=9))


def test_frozen_assignments_quizzes_and_courses_keep_their_structure() -> None:
    db, org, teacher, student, session, _e, lesson, _day, place = live_school()
    assignment = create_assignment(db, teacher, session.id, AssignmentCreate(title="TP figé", due_date=datetime(2025, 1, 25, tzinfo=UTC)))
    publish_assignment(db, teacher, assignment.id)
    quiz = create_quiz(db, teacher, session.id, QuizCreate(
        title="Quiz figé", questions=[QuizQuestionCreate(text="Oui ?", options=["Non", "Oui"], correct_index=1)],
    ))
    set_quiz_status(db, teacher, quiz.id, "active")
    student_progress(db, student)  # freezes the program

    update_assignment(db, teacher, assignment.id, AssignmentUpdate(title="TP figé, consigne corrigée"))
    with pytest.raises(HTTPException) as moved:
        update_assignment(db, teacher, assignment.id, AssignmentUpdate(due_date=datetime(2025, 1, 28, tzinfo=UTC)))
    assert moved.value.status_code == 409
    listed = next(item for item in list_teacher_assignments(db, teacher, session.id) if item.id == assignment.id)
    assert "programme figé" in listed.delete_blocked_reason

    with pytest.raises(HTTPException) as drafted:
        set_quiz_status(db, teacher, quiz.id, "draft")
    assert drafted.value.status_code == 409

    with pytest.raises(HTTPException) as unpublished:
        update_course(db, teacher, place[0], place[1], place[2], CourseUpdate(status="draft"))
    assert unpublished.value.status_code == 409
    assert db.get(CourseRecord, place[2]).status == "published"
