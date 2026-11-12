"""Badge decision: the mother site's rules, made fair to the evidence available.

Guided paths (live, presentiel) must clear every criterion of a level, while the
classic path only needs its weighted score below the Professional level.

On top of the mother site's rules, the badge only weighs what there is to weigh
(see docs/BADGES.md):

- Fair: nothing counts against a student before its due date, nor while a teacher
  has not reviewed the work; what the student did counts at once.
- Proportionate: a category with few due items (quizzes, TPs, live classes) does not
  gate any level and weighs in proportion; the other categories, live classes first,
  carry the badge.
- Proven: each level needs a minimum of evidence, and Professional needs real
  evaluations.

Two properties hold and are tested: a student's own action (passing a quiz, handing
in or getting a TP reviewed, attending a class, finishing a lesson) never lowers their
score or level; publishing an activity changes nothing before it is due. They hold
because a category's weight and gating only depend on its due items, never on what
the student did early.
"""

from dataclasses import dataclass
from math import ceil

PILLAR_WEIGHTS = {"content": 35.0, "evaluation": 25.0, "production": 25.0, "live": 15.0}
LIVE_PILLAR_WEIGHTS = {
    "content": 60.0 * (35.0 / 85.0),
    "evaluation": 60.0 * (25.0 / 85.0),
    "production": 60.0 * (25.0 / 85.0),
    "live": 40.0,
}
LEVEL_RULES = {
    "debutant": {"score": 25.0, "content": 25.0, "assignments": 25.0, "quizzes": 25.0, "live": 25.0},
    "intermediaire": {"score": 50.0, "content": 50.0, "assignments": 50.0, "quizzes": 50.0, "live": 50.0, "grade": 50.0},
    "semi_pro": {"score": 75.0, "content": 75.0, "assignments": 75.0, "quizzes": 70.0, "live": 70.0, "grade": 60.0},
    "professionnel": {"score": 90.0, "content": 100.0, "assignments": 100.0, "quizzes": 80.0, "live": 80.0, "grade": 80.0},
}

# Below these numbers of due items, a category does not gate any level and only weighs
# in proportion (one due quiz out of three weighs a third of the evaluation).
EVIDENCE_THRESHOLDS = {"quizzes": 3, "assignments": 2, "live": 4}
# Evidence a guided student needs for each level: classes attended, quizzes passed, TPs handed
# in and the teacher's own grades. Lessons are not evidence: they could stand in for the classes.
LEVEL_MIN_EVIDENCE = {"debutant": 1, "intermediaire": 3, "semi_pro": 5, "professionnel": 5}


@dataclass(frozen=True)
class BadgeStats:
    guided: bool
    format_type: str
    total_lessons: int
    completed_lessons: int
    lesson_progress_pct: float
    # Quizzes and TPs that count: the due ones and the ones the student already did.
    total_assignments: int
    submitted_assignments: int
    validated_assignments: int
    total_quizzes: int
    attempted_quizzes: int
    passed_quizzes: int
    attendance_total: int
    attendance_present: int
    grade_average_pct: float | None
    has_final_project: bool
    final_project_validated: bool
    professional_eligible: bool
    # Items past their due date; None when every counted item is due.
    due_quizzes: int | None = None
    due_assignments: int | None = None
    # TPs handed in that the teacher has not reviewed yet: they do not count against validation.
    awaiting_review_assignments: int = 0
    # Grades the teacher entered (not the automatic ones of quizzes and TPs, counted already).
    teacher_grades: int = 0


@dataclass(frozen=True)
class _Criterion:
    done: float
    required: float
    missing: str

    @property
    def ratio(self) -> float:
        return max(0.0, min(1.0, self.done / self.required))

    @property
    def met(self) -> bool:
        return self.done >= self.required


def _required_count(total: int, pct: float) -> int:
    return max(1, ceil(total * pct / 100))


def _percent(done: int, total: int) -> float:
    return round(done / total * 100, 1)


def due_count(stats: BadgeStats, category: str) -> int:
    if category == "quizzes":
        return stats.total_quizzes if stats.due_quizzes is None else stats.due_quizzes
    if category == "assignments":
        return stats.total_assignments if stats.due_assignments is None else stats.due_assignments
    return stats.attendance_total


def has_full_evidence(stats: BadgeStats, category: str) -> bool:
    return due_count(stats, category) >= EVIDENCE_THRESHOLDS[category]


def _confidence(stats: BadgeStats, category: str) -> float:
    """How much a category weighs: its due items against the threshold.

    Work done ahead of any due item weighs like one due item, so it counts at once; it
    is all done, so it cannot lower the score. How much of it there is never changes
    the weight, which keeps a student's action from shifting weight onto a weak category.
    """
    due = due_count(stats, category)
    total = stats.total_quizzes if category == "quizzes" else stats.total_assignments if category == "assignments" else due
    return min(1.0, max(due, 1 if total > due else 0) / EVIDENCE_THRESHOLDS[category])


def evidence_count(stats: BadgeStats) -> int:
    return stats.attendance_present + stats.passed_quizzes + stats.submitted_assignments + stats.teacher_grades


def _reviewable_assignments(stats: BadgeStats) -> int:
    return max(0, stats.total_assignments - stats.awaiting_review_assignments)


def quiz_mastery_pct(stats: BadgeStats) -> float | None:
    if stats.total_quizzes <= 0:
        return None
    passed_ratio = stats.passed_quizzes / stats.total_quizzes
    attempted_ratio = stats.attempted_quizzes / stats.total_quizzes
    return round((passed_ratio * 0.8 + attempted_ratio * 0.2) * 100, 1)


def _production_pct(stats: BadgeStats) -> float | None:
    assignment_pct = None
    if stats.total_assignments > 0:
        submitted_pct = _percent(stats.submitted_assignments, stats.total_assignments)
        reviewable = _reviewable_assignments(stats)
        # A submitted TP shows effort; a reviewed TP is the stronger evidence. Until the
        # teacher reviews anything, handing in is all the student can do.
        validated_pct = _percent(stats.validated_assignments, reviewable) if reviewable else submitted_pct
        assignment_pct = round(submitted_pct * 0.4 + validated_pct * 0.6, 1)
    # On guided paths the final project only gates Professional, so that it does
    # not hold back the early levels months before it is due.
    if stats.guided or not stats.has_final_project:
        return assignment_pct
    final_pct = 100.0 if stats.final_project_validated else 0.0
    if assignment_pct is None:
        return final_pct
    return round(assignment_pct * 0.7 + final_pct * 0.3, 1)


def badge_score(stats: BadgeStats) -> float:
    quiz = quiz_mastery_pct(stats)
    evaluation = [value for value in (quiz, stats.grade_average_pct) if value is not None]
    production = _production_pct(stats)
    # (value, confidence): a pillar with few due items weighs in proportion.
    pillars = {
        "content": (stats.lesson_progress_pct, 1.0) if stats.total_lessons > 0 else None,
        "evaluation": (
            round(sum(evaluation) / len(evaluation), 1),
            1.0 if stats.grade_average_pct is not None else _confidence(stats, "quizzes"),
        ) if evaluation else None,
        "production": (
            production,
            1.0 if not stats.guided and stats.has_final_project else _confidence(stats, "assignments"),
        ) if production is not None else None,
        "live": (
            _percent(stats.attendance_present, stats.attendance_total), _confidence(stats, "live"),
        ) if stats.attendance_total > 0 else None,
    }
    weights = LIVE_PILLAR_WEIGHTS if stats.format_type == "live" else PILLAR_WEIGHTS
    active = {name: pillar for name, pillar in pillars.items() if pillar is not None}
    total_weight = sum(weights[name] * confidence for name, (_value, confidence) in active.items())
    if total_weight <= 0:
        return 0.0
    return round(sum(value * weights[name] * confidence for name, (value, confidence) in active.items()) / total_weight, 1)


def _criteria(level: str, stats: BadgeStats) -> list[_Criterion]:
    rule = LEVEL_RULES[level]
    criteria = [_Criterion(badge_score(stats), rule["score"], f"atteignez {int(rule['score'])}% de score global")]
    if level != "professionnel" and not stats.guided:
        return criteria

    if stats.total_lessons > 0:
        required = _required_count(stats.total_lessons, rule["content"])
        criteria.append(_Criterion(
            stats.completed_lessons, required,
            f"terminez {required} contenu(s) obligatoire(s) sur {stats.total_lessons}",
        ))
    if has_full_evidence(stats, "assignments"):
        if level == "debutant":
            required = _required_count(stats.total_assignments, rule["assignments"])
            criteria.append(_Criterion(
                stats.submitted_assignments, required,
                f"rendez {required} TP sur {stats.total_assignments}",
            ))
        elif _reviewable_assignments(stats):
            reviewable = _reviewable_assignments(stats)
            required = _required_count(reviewable, rule["assignments"])
            criteria.append(_Criterion(
                stats.validated_assignments, required,
                f"faites corriger et valider {required} TP sur {reviewable}",
            ))
    if has_full_evidence(stats, "quizzes"):
        required = _required_count(stats.total_quizzes, rule["quizzes"])
        criteria.append(_Criterion(
            stats.passed_quizzes, required,
            f"réussissez {required} quiz sur {stats.total_quizzes}",
        ))
    if has_full_evidence(stats, "live"):
        required = _required_count(stats.attendance_total, rule["live"])
        criteria.append(_Criterion(
            stats.attendance_present, required,
            f"validez {required} présence(s) sur {stats.attendance_total}",
        ))
    if "grade" in rule and stats.grade_average_pct is not None:
        criteria.append(_Criterion(
            stats.grade_average_pct, rule["grade"],
            f"obtenez une moyenne d'au moins {int(rule['grade'] / 5)}/20",
        ))
    if stats.guided:
        needed = LEVEL_MIN_EVIDENCE[level]
        criteria.append(_Criterion(
            evidence_count(stats), needed,
            f"cumulez {needed} preuve(s) : séances suivies, quiz réussis, TP rendus ou notes du professeur",
        ))
    if level == "professionnel":
        if not stats.professional_eligible:
            criteria.append(_Criterion(0, 1, "attendez la fin de la session et la validation des séances"))
        if stats.has_final_project:
            criteria.append(_Criterion(
                1 if stats.final_project_validated else 0, 1,
                "validez le projet final avec au moins 80%",
            ))
        if not (has_full_evidence(stats, "quizzes") or has_full_evidence(stats, "assignments")):
            criteria.append(_Criterion(
                0, 1,
                f"le niveau Professionnel demande au moins {EVIDENCE_THRESHOLDS['quizzes']} quiz "
                f"ou {EVIDENCE_THRESHOLDS['assignments']} TP échus",
            ))
    return criteria


def badge_level(stats: BadgeStats) -> str:
    for level in ("professionnel", "semi_pro", "intermediaire", "debutant"):
        if all(item.met for item in _criteria(level, stats)):
            return level
    return "aventurier"


def missing_requirements(level: str, stats: BadgeStats) -> list[str]:
    return [item.missing for item in _criteria(level, stats) if not item.met]


def level_readiness_pct(level: str, stats: BadgeStats) -> float:
    """Average advancement of a level's criteria: it never grants the level by itself."""
    criteria = _criteria(level, stats)
    return round(sum(item.ratio for item in criteria) / len(criteria) * 100, 1)


def badge_ring_pct(level: str, next_level: str | None, stats: BadgeStats) -> float:
    """Progress shown around the badge, capped so that only a real award reaches 100 %."""
    if next_level is None:
        return 100.0
    if stats.guided:
        return min(99.0, level_readiness_pct(next_level, stats))
    start = 0.0 if level == "aventurier" else LEVEL_RULES[level]["score"]
    end = LEVEL_RULES[next_level]["score"]
    return max(0.0, min(99.0, round((badge_score(stats) - start) / (end - start) * 100)))


def badge_basis_note(stats: BadgeStats) -> str | None:
    """What the badge rests on when quizzes or TPs are still too few to weigh fully."""
    if not stats.guided:
        return None
    thin = [label for category, label in (("quizzes", "de quiz"), ("assignments", "de TP")) if not has_full_evidence(stats, category)]
    if not thin:
        return None
    sources = []
    if stats.attendance_total > 0:
        sources.append("vos présences en live" if stats.format_type == "live" else "vos présences aux séances")
    if stats.total_lessons > 0:
        sources.append("vos contenus")
    if not sources:
        return f"Peu {' et '.join(thin)} échus à ce stade : votre badge se construira avec vos prochaines activités."
    return f"Peu {' et '.join(thin)} échus à ce stade : votre badge repose surtout sur {' et '.join(sources)}."
