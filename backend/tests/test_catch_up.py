"""Catching up on late work until a live or presentiel session ends (docs/BADGES.md)."""
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import HTTPException
from test_academic_suite import build_db, ctx as academic_ctx, seed as academic_seed
from test_assignment_workflow import ctx, days_from_now, dbx, published_assignment, seed

from app.models.entities import AssignmentRecord, FormationRecord, QuizRecord
from app.schemas.academic import QuizAttemptPayload, QuizCreate, QuizQuestionCreate
from app.schemas.assignments import AssignmentCreate, AssignmentSubmit
from app.services.assignments import list_student_assignments, submit_assignment
from app.services.learning_progress import _badge_quiz_stats, badge_for_enrollment
from app.services.pedagogy_access import WORK_CLOSED_MESSAGE
from app.services.resources_quizzes import create_quiz, list_student_quizzes, set_quiz_status, submit_quiz_attempt

QUESTION = QuizQuestionCreate(text="Bonne réponse ?", options=["Non", "Oui"], correct_index=1)


def school(format_type: str):
    db = dbx()
    org, teacher, student, session = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = format_type
    db.commit()
    work = published_assignment(db, ctx(db, org, teacher), session.id, AssignmentCreate(
        title="TP couleurs", instructions="Créer", due_date=days_from_now(2),
    ))
    quiz = create_quiz(db, ctx(db, org, teacher), session.id, QuizCreate(title="Quiz couleurs", questions=[QUESTION]))
    set_quiz_status(db, ctx(db, org, teacher), quiz.id, "active")
    return db, org, student, session, work, quiz


def end_session(db, session):
    session.end_date = date.today() - timedelta(days=1)
    db.commit()


def test_a_live_session_takes_no_more_work_once_over():
    db, org, student, session, work, quiz = school("live")
    tenant = ctx(db, org, student)
    end_session(db, session)

    with pytest.raises(HTTPException) as late_work:
        submit_assignment(db, tenant, work.id, AssignmentSubmit(file_url="x"))
    assert (late_work.value.status_code, late_work.value.detail) == (409, WORK_CLOSED_MESSAGE)
    assert list_student_assignments(db, tenant)[0].submissions_closed is True

    with pytest.raises(HTTPException) as retake:
        submit_quiz_attempt(db, tenant, quiz.id, QuizAttemptPayload(answers=[1]))
    assert (retake.value.status_code, retake.value.detail) == (409, WORK_CLOSED_MESSAGE)
    view = list_student_quizzes(db, tenant)[0]
    assert view.work_closed is True and view.can_attempt is False


def test_a_live_session_still_takes_late_work_before_it_ends():
    db, org, student, _session, work, quiz = school("live")
    tenant = ctx(db, org, student)
    db.get(AssignmentRecord, work.id).due_date = days_from_now(-1)
    db.commit()
    # Past the deadline, the TP is still accepted: only the file check stops this fake file.
    with pytest.raises(HTTPException) as file_check:
        submit_assignment(db, tenant, work.id, AssignmentSubmit(file_url="x"))
    assert file_check.value.status_code == 422
    assert submit_quiz_attempt(db, tenant, quiz.id, QuizAttemptPayload(answers=[1])).passed


def test_an_online_session_stays_open_after_its_end_date():
    db, org, student, session, work, quiz = school("ligne")
    tenant = ctx(db, org, student)
    end_session(db, session)
    with pytest.raises(HTTPException) as file_check:
        submit_assignment(db, tenant, work.id, AssignmentSubmit(file_url="x"))
    assert file_check.value.status_code == 422
    assert list_student_assignments(db, tenant)[0].submissions_closed is False
    assert submit_quiz_attempt(db, tenant, quiz.id, QuizAttemptPayload(answers=[1])).passed


def test_late_work_comes_first_in_what_to_do_and_goes_when_the_session_ends():
    db = build_db()
    org, teacher, student, _classmate, session, enrollment, _ce, _lesson, _day = academic_seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    session.end_date = date.today() + timedelta(days=30)
    now = datetime.now(UTC)
    db.add_all([
        AssignmentRecord(
            organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="TP en retard",
            publication_status="published", due_date=now - timedelta(days=1),
        ),
        QuizRecord(
            organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Quiz à rattraper",
            status="active", opened_at=now - timedelta(days=10),  # due 3 days ago: the oldest comes first
        ),
        QuizRecord(
            organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Quiz de la semaine",
            status="active", opened_at=now,
        ),
    ])
    db.commit()
    tenant = academic_ctx(db, org, student)

    badge = badge_for_enrollment(db, tenant, enrollment)
    assert [(item.title, item.overdue) for item in badge.upcoming] == [
        ("Quiz à rattraper", True), ("TP en retard", True), ("Quiz de la semaine", False),
    ]
    assert _badge_quiz_stats(db, tenant, enrollment).due == 1

    end_session(db, session)
    assert badge_for_enrollment(db, tenant, enrollment).upcoming == []
    # Nothing can be done any more: the quiz of the week is due with the session.
    assert _badge_quiz_stats(db, tenant, enrollment).due == 2
