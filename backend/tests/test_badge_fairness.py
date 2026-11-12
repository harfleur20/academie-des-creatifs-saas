"""The badge weighs the evidence there is (docs/BADGES.md): scenarios and the two guarantees."""
import random
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from test_academic_suite import build_db, ctx, seed

from app.models.entities import FormationRecord, QuizAttemptRecord, QuizRecord
from app.services.badge_rules import BadgeStats, badge_basis_note, badge_level, badge_score, missing_requirements
from app.services.learning_progress import badge_for_enrollment, mark_lesson_complete

ORDER = {"aventurier": 0, "debutant": 1, "intermediaire": 2, "semi_pro": 3, "professionnel": 4}

LIVE_CLASS = BadgeStats(
    guided=True, format_type="live",
    total_lessons=4, completed_lessons=4, lesson_progress_pct=100.0,
    total_assignments=0, submitted_assignments=0, validated_assignments=0,
    total_quizzes=0, attempted_quizzes=0, passed_quizzes=0,
    attendance_total=8, attendance_present=8, grade_average_pct=None,
    has_final_project=False, final_project_validated=False, professional_eligible=False,
)


@pytest.mark.parametrize(("name", "stats", "level"), [
    ("8 lives sur 8, ni quiz ni TP", LIVE_CLASS, "semi_pro"),
    ("8 lives sur 8, un seul quiz, raté", replace(LIVE_CLASS, total_quizzes=1, attempted_quizzes=1), "semi_pro"),
    ("8 lives sur 8, un TP rendu en attente de correction",
     replace(LIVE_CLASS, total_assignments=1, submitted_assignments=1, awaiting_review_assignments=1), "semi_pro"),
    ("3 lives sur 8, un quiz réussi",
     replace(LIVE_CLASS, attendance_present=3, total_quizzes=1, attempted_quizzes=1, passed_quizzes=1), "debutant"),
    ("un seul live suivi, rien d'autre",
     replace(LIVE_CLASS, attendance_total=1, attendance_present=1, total_lessons=0, completed_lessons=0, lesson_progress_pct=0.0),
     "debutant"),
])
def test_scenarios(name, stats, level):
    assert badge_level(stats) == level, name


def test_a_category_with_enough_items_gates_again():
    untouched = replace(LIVE_CLASS, total_quizzes=3, attempted_quizzes=0, passed_quizzes=0)
    assert badge_level(untouched) == "aventurier"
    assert "tentez 1 quiz sur 3" in missing_requirements("debutant", untouched)

    # Tried but failed: the effort earns Débutant, like a TP handed in; passing comes next.
    tried = replace(untouched, attempted_quizzes=3)
    assert badge_level(tried) == "debutant"
    assert "réussissez 2 quiz sur 3" in missing_requirements("intermediaire", tried)


def test_one_failed_quiz_out_of_three_waits_for_its_retake():
    # Rounded up as on the mother site: with 3 quizzes, Semi-pro needs all 3, so the quiz is retaken.
    failed_one = replace(LIVE_CLASS, total_quizzes=3, attempted_quizzes=3, passed_quizzes=2)
    assert badge_level(failed_one) == "intermediaire"
    assert badge_level(replace(failed_one, passed_quizzes=3)) == "semi_pro"


def test_professional_needs_real_evaluations():
    ended = replace(LIVE_CLASS, professional_eligible=True)
    assert badge_level(ended) == "semi_pro"
    assert badge_level(replace(ended, total_quizzes=3, attempted_quizzes=3, passed_quizzes=3)) == "professionnel"
    two_tps = replace(ended, total_assignments=2, submitted_assignments=2, validated_assignments=2)
    assert badge_level(two_tps) == "professionnel"


def test_the_badge_says_what_it_rests_on():
    assert badge_basis_note(LIVE_CLASS) == (
        "Peu de quiz et de TP échus à ce stade : votre badge repose surtout sur vos présences en live et vos contenus."
    )
    full = replace(LIVE_CLASS, total_quizzes=3, attempted_quizzes=3, passed_quizzes=3,
                   total_assignments=2, submitted_assignments=2, validated_assignments=2)
    assert badge_basis_note(full) is None


def _random_stats(rng: random.Random) -> BadgeStats:
    lessons = rng.randint(0, 8)
    quiz_due, quiz_early = rng.randint(0, 6), rng.randint(0, 3)
    quiz_due_passed = rng.randint(0, quiz_due)
    passed = quiz_due_passed + quiz_early
    attempted = rng.randint(passed, quiz_due + quiz_early)
    tp_due, tp_early = rng.randint(0, 5), rng.randint(0, 2)
    submitted = rng.randint(0, tp_due) + tp_early
    validated = rng.randint(0, submitted)
    days = rng.randint(0, 10)
    completed = rng.randint(0, lessons)
    return BadgeStats(
        guided=rng.random() < 0.7, format_type=rng.choice(["live", "presentiel", "ligne"]),
        total_lessons=lessons, completed_lessons=completed,
        lesson_progress_pct=round(completed / lessons * 100, 1) if lessons else 0.0,
        total_assignments=tp_due + tp_early, submitted_assignments=submitted, validated_assignments=validated,
        total_quizzes=quiz_due + quiz_early, attempted_quizzes=attempted, passed_quizzes=passed,
        attendance_total=days, attendance_present=rng.randint(0, days),
        grade_average_pct=rng.choice([None, round(rng.uniform(0, 100), 1)]),
        has_final_project=rng.random() < 0.3, final_project_validated=rng.random() < 0.5,
        professional_eligible=rng.random() < 0.5,
        due_quizzes=quiz_due, due_assignments=tp_due, awaiting_review_assignments=submitted - validated,
        teacher_grades=rng.randint(0, 2),
    )


def _student_actions(stats: BadgeStats) -> list[BadgeStats]:
    """Every single thing the student can do next."""
    actions = []
    early_passed = stats.total_quizzes - stats.due_quizzes
    if stats.passed_quizzes - early_passed < stats.due_quizzes:  # pass a due quiz
        attempted = stats.attempted_quizzes if stats.attempted_quizzes > stats.passed_quizzes else stats.attempted_quizzes + 1
        actions.append(replace(stats, passed_quizzes=stats.passed_quizzes + 1, attempted_quizzes=attempted))
    if stats.attempted_quizzes < stats.total_quizzes:  # try a due quiz without passing it
        actions.append(replace(stats, attempted_quizzes=stats.attempted_quizzes + 1))
    actions.append(replace(  # pass a quiz ahead of its due date
        stats, total_quizzes=stats.total_quizzes + 1, passed_quizzes=stats.passed_quizzes + 1,
        attempted_quizzes=stats.attempted_quizzes + 1,
    ))
    early_submitted = stats.total_assignments - stats.due_assignments
    if stats.submitted_assignments - early_submitted < stats.due_assignments:  # hand in a due TP
        actions.append(replace(
            stats, submitted_assignments=stats.submitted_assignments + 1,
            awaiting_review_assignments=stats.awaiting_review_assignments + 1,
        ))
    actions.append(replace(  # hand in a TP ahead of its due date
        stats, total_assignments=stats.total_assignments + 1, submitted_assignments=stats.submitted_assignments + 1,
        awaiting_review_assignments=stats.awaiting_review_assignments + 1,
    ))
    if stats.attendance_present < stats.attendance_total:  # be there at a class
        actions.append(replace(stats, attendance_present=stats.attendance_present + 1))
    if stats.completed_lessons < stats.total_lessons:  # finish a lesson
        done = stats.completed_lessons + 1
        actions.append(replace(stats, completed_lessons=done, lesson_progress_pct=round(done / stats.total_lessons * 100, 1)))
    return actions


def test_a_students_action_never_lowers_their_score_or_level():
    rng = random.Random(2026)
    for _ in range(4000):
        before = _random_stats(rng)
        for after in _student_actions(before):
            assert badge_score(after) >= badge_score(before), (before, after)
            assert ORDER[badge_level(after)] >= ORDER[badge_level(before)], (before, after)


def test_publishing_a_quiz_changes_nothing_before_it_is_due():
    db = build_db()
    org, teacher, student, _classmate, session, enrollment, _ce, lesson, _day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    session.end_date = date.today() + timedelta(days=30)  # still running: work is not due yet
    db.commit()
    tenant = ctx(db, org, student)
    mark_lesson_complete(db, tenant, lesson.id)
    before = badge_for_enrollment(db, tenant, enrollment)

    quiz = QuizRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Nouveau quiz",
        status="active", opened_at=datetime.now(UTC),
    )
    db.add(quiz)
    db.commit()
    published = badge_for_enrollment(db, tenant, enrollment)
    assert published.model_dump(exclude={"upcoming"}) == before.model_dump(exclude={"upcoming"})
    assert [item.title for item in published.upcoming] == ["Nouveau quiz"]

    # Passed ahead of its due date, it counts at once.
    db.add(QuizAttemptRecord(
        organization_id=org.id, quiz_id=quiz.id, enrollment_id=enrollment.id,
        attempt_number=1, answers=[], score_pct=90, submitted_at=datetime.now(UTC),
    ))
    db.commit()
    assert badge_for_enrollment(db, tenant, enrollment).quiz_progress_pct == 100


def test_an_open_quiz_left_aside_counts_once_due():
    db = build_db()
    org, teacher, student, _classmate, session, enrollment, _ce, _lesson, _day = seed(db)
    tenant = ctx(db, org, student)
    db.add(QuizRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Quiz oublié",
        status="active", opened_at=datetime.now(UTC) - timedelta(days=8),
    ))
    db.commit()
    badge = badge_for_enrollment(db, tenant, enrollment)
    assert badge.quiz_progress_pct == 0
    # Still open: listed as work to catch up on.
    assert [(item.title, item.overdue) for item in badge.upcoming] == [("Quiz oublié", True)]
