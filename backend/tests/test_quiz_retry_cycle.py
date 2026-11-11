from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from test_academic_suite import build_db, ctx, seed

from app.models.entities import QuizAttemptRecord
from app.schemas.academic import QuizAttemptPayload, QuizCreate, QuizQuestionCreate
from app.services.resources_quizzes import (
    QUIZ_RETRY_HOURS,
    create_quiz,
    list_student_quizzes,
    set_quiz_status,
    submit_quiz_attempt,
)

QUESTION = QuizQuestionCreate(text="Bonne réponse ?", options=["Non", "Oui"], correct_index=1)
WRONG = QuizAttemptPayload(answers=[0])
RIGHT = QuizAttemptPayload(answers=[1])


def active_quiz(questions: list[QuizQuestionCreate] | None = None):
    db = build_db()
    org, teacher, student, _, session, enrollment, *_ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    quiz = create_quiz(db, teacher_tenant, session.id, QuizCreate(title="Cycle", questions=questions or [QUESTION]))
    set_quiz_status(db, teacher_tenant, quiz.id, "active")
    return db, ctx(db, org, student), quiz.id, enrollment.id


def student_view(db, tenant, quiz_id):
    return next(item for item in list_student_quizzes(db, tenant) if item.id == quiz_id)


def last_attempt(db, quiz_id, enrollment_id) -> QuizAttemptRecord:
    return db.scalars(select(QuizAttemptRecord).where(
        QuizAttemptRecord.quiz_id == quiz_id,
        QuizAttemptRecord.enrollment_id == enrollment_id,
    ).order_by(QuizAttemptRecord.attempt_number.desc())).first()


def move_last_attempt_back(db, quiz_id, enrollment_id, delay: timedelta) -> None:
    last_attempt(db, quiz_id, enrollment_id).submitted_at = datetime.now(UTC) - delay
    db.commit()


def test_three_failures_wait_eight_hours_then_open_a_new_cycle() -> None:
    db, tenant, quiz_id, enrollment_id = active_quiz()
    for _ in range(3):
        view = submit_quiz_attempt(db, tenant, quiz_id, WRONG)
        assert not view.passed
    assert view.attempts_remaining == 0 and view.can_attempt is False
    submitted_at = last_attempt(db, quiz_id, enrollment_id).submitted_at.replace(tzinfo=UTC)
    assert view.next_attempt_available_at == submitted_at + timedelta(hours=QUIZ_RETRY_HOURS)
    with pytest.raises(HTTPException) as refused:
        submit_quiz_attempt(db, tenant, quiz_id, RIGHT)
    assert refused.value.status_code == 409

    move_last_attempt_back(db, quiz_id, enrollment_id, timedelta(hours=QUIZ_RETRY_HOURS) - timedelta(minutes=1))
    assert student_view(db, tenant, quiz_id).can_attempt is False

    move_last_attempt_back(db, quiz_id, enrollment_id, timedelta(hours=QUIZ_RETRY_HOURS, seconds=1))
    reopened = student_view(db, tenant, quiz_id)
    assert reopened.can_attempt is True
    assert reopened.attempts_remaining == 3 and reopened.next_attempt_available_at is None

    for remaining in (2, 1, 0):
        view = submit_quiz_attempt(db, tenant, quiz_id, WRONG)
        assert view.attempts_remaining == remaining
    assert view.attempts[-1].attempt_number == 6
    assert view.can_attempt is False and view.next_attempt_available_at is not None


def test_each_cycle_gives_three_tries_before_any_wait() -> None:
    db, tenant, quiz_id, _ = active_quiz()
    first = submit_quiz_attempt(db, tenant, quiz_id, WRONG)
    second = submit_quiz_attempt(db, tenant, quiz_id, WRONG)
    assert (first.attempts_remaining, second.attempts_remaining) == (2, 1)
    assert second.can_attempt is True and second.next_attempt_available_at is None


def test_a_pass_ends_the_retries() -> None:
    db, tenant, quiz_id, _ = active_quiz()
    submit_quiz_attempt(db, tenant, quiz_id, WRONG)
    passed = submit_quiz_attempt(db, tenant, quiz_id, RIGHT)
    assert passed.passed and passed.can_attempt is False
    assert passed.attempts_remaining == 0 and passed.next_attempt_available_at is None
    with pytest.raises(HTTPException) as refused:
        submit_quiz_attempt(db, tenant, quiz_id, RIGHT)
    assert refused.value.status_code == 409


def test_each_attempt_comes_with_its_own_correction() -> None:
    db = build_db()
    org, teacher, student, classmate, session, *_ = seed(db)
    teacher_tenant = ctx(db, org, teacher)
    second = QuizQuestionCreate(text="Deuxième ?", options=["A", "B", "C"], correct_index=2)
    quiz = create_quiz(db, teacher_tenant, session.id, QuizCreate(title="Correction", questions=[QUESTION, second]))
    set_quiz_status(db, teacher_tenant, quiz.id, "active")

    view = submit_quiz_attempt(db, ctx(db, org, student), quiz.id, QuizAttemptPayload(answers=[1, -1]))
    attempt = view.attempts[-1]
    assert attempt.score_pct == 50
    assert attempt.submitted_answers == [[1], []]  # []: left unanswered
    assert attempt.correct_answers == [[1], [2]]
    assert student_view(db, ctx(db, org, classmate), quiz.id).attempts == []


MULTIPLE = QuizQuestionCreate(
    text="Couleurs primaires ?", options=["Rouge", "Vert", "Bleu", "Jaune"],
    selection_mode="multiple", correct_indices=[2, 0, 3], points=3,
)


@pytest.mark.parametrize(("ticked", "expected_pct"), [
    ([0, 2, 3], 75.0),  # 3 points of 3, plus the single question's 0 of 1
    ([0, 2], 50.0),  # one share per right answer ticked
    ([0, 1], 0.0),  # a wrong answer takes a share back
    ([1], 0.0),  # never below zero
    ([], 0.0),
])
def test_a_multiple_answer_question_earns_a_share_per_right_answer(ticked, expected_pct) -> None:
    db, tenant, quiz_id, _ = active_quiz([MULTIPLE, QUESTION])
    view = submit_quiz_attempt(db, tenant, quiz_id, QuizAttemptPayload(answers=[ticked, 0]))
    attempt = view.attempts[-1]
    assert attempt.score_pct == expected_pct
    assert attempt.correct_answers == [[0, 2, 3], [1]]
    assert attempt.submitted_answers[0] == ticked


def test_points_weigh_each_question() -> None:
    heavy = QuizQuestionCreate(text="Lourde ?", options=["A", "B"], correct_index=0, points=3)
    db, tenant, quiz_id, _ = active_quiz([heavy, QUESTION])
    view = submit_quiz_attempt(db, tenant, quiz_id, QuizAttemptPayload(answers=[0, 0]))
    assert view.attempts[-1].score_pct == 75.0


def test_a_single_answer_question_keeps_only_one_ticked_option() -> None:
    db, tenant, quiz_id, _ = active_quiz()
    view = submit_quiz_attempt(db, tenant, quiz_id, QuizAttemptPayload(answers=[[1, 0]]))
    assert view.attempts[-1].submitted_answers == [[1]]
    assert view.passed


def test_a_multiple_answer_question_needs_a_right_answer() -> None:
    with pytest.raises(ValidationError):
        QuizQuestionCreate(text="Aucune ?", options=["A", "B"], selection_mode="multiple", correct_indices=[])


def test_a_quiz_is_passed_at_eighty_percent_at_least() -> None:
    with pytest.raises(ValidationError):
        QuizCreate(title="Trop facile", pass_pct=70, questions=[QUESTION])
    assert QuizCreate(title="Par défaut", questions=[QUESTION]).pass_pct == 80
    assert QuizCreate(title="Exigeant", pass_pct=90, questions=[QUESTION]).pass_pct == 90

    db, tenant, quiz_id, _ = active_quiz([QUESTION] * 4)
    three_of_four = submit_quiz_attempt(db, tenant, quiz_id, QuizAttemptPayload(answers=[1, 1, 1, 0]))
    assert three_of_four.best_score_pct == 75 and not three_of_four.passed
    assert three_of_four.pass_pct == 80 and three_of_four.attempts_remaining == 2
    four_of_four = submit_quiz_attempt(db, tenant, quiz_id, QuizAttemptPayload(answers=[1, 1, 1, 1]))
    assert four_of_four.passed
