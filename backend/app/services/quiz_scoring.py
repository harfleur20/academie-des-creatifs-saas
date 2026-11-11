"""Quiz scoring ported from the mother site's online lesson quizzes.

A question has one or several right answers and is worth some points (1 by default).
A single-answer question earns its points only when the answer is right. A
multiple-answer question earns a share of its points per right answer ticked and
loses as much per wrong one, never below zero.
"""
from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException

from app.models.entities import QuizQuestionRecord


def correct_answers(question: QuizQuestionRecord) -> list[int]:
    options = len(question.options or [])
    if question.selection_mode == "multiple" and question.correct_indices:
        return sorted({index for index in question.correct_indices if isinstance(index, int) and 0 <= index < options})
    return [question.correct_index]


def question_points(question: QuizQuestionRecord) -> float:
    return float(question.points) if question.points and question.points > 0 else 1.0


def normalize_answer(question: QuizQuestionRecord, answer: int | Sequence[int]) -> list[int]:
    """The ticked options of one question; -1 or an empty list means unanswered."""
    raw = [answer] if isinstance(answer, int) else list(answer)
    options = len(question.options or [])
    if any(not isinstance(value, int) or value < -1 or value >= options for value in raw):
        raise HTTPException(422, "Une réponse ne correspond pas aux options proposées.")
    picked = list(dict.fromkeys(value for value in raw if value >= 0))
    return picked if question.selection_mode == "multiple" else picked[:1]


def stored_answer(question: QuizQuestionRecord, stored: object) -> list[int]:
    """Read an attempt's saved answer, older attempts having one integer per question."""
    if isinstance(stored, bool):
        return []
    if isinstance(stored, int):
        return [stored] if stored >= 0 else []
    if isinstance(stored, list):
        return [value for value in stored if isinstance(value, int) and not isinstance(value, bool) and value >= 0]
    return []


def score_question(question: QuizQuestionRecord, picked: list[int]) -> float:
    points = question_points(question)
    right = set(correct_answers(question))
    chosen = set(picked)
    if question.selection_mode != "multiple":
        return points if chosen == right else 0.0
    share = points / len(right)
    earned = share * len(chosen & right) - share * len(chosen - right)
    return round(max(0.0, min(points, earned)), 4)


def score_pct(questions: Sequence[QuizQuestionRecord], answers: Sequence[list[int]]) -> float:
    total = sum(question_points(question) for question in questions)
    if total <= 0:
        return 0.0
    earned = sum(score_question(question, picked) for question, picked in zip(questions, answers))
    return round(earned / total * 100, 1)
