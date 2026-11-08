"""Badge decision aligned on the mother site's rules.

Guided paths (live, presentiel) must clear every criterion of a level, while the
classic path only needs its weighted score below the Professional level.
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


@dataclass(frozen=True)
class BadgeStats:
    guided: bool
    format_type: str
    total_lessons: int
    completed_lessons: int
    lesson_progress_pct: float
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


def quiz_mastery_pct(stats: BadgeStats) -> float | None:
    if stats.total_quizzes <= 0:
        return None
    passed_ratio = stats.passed_quizzes / stats.total_quizzes
    attempted_ratio = stats.attempted_quizzes / stats.total_quizzes
    return round((passed_ratio * 0.8 + attempted_ratio * 0.2) * 100, 1)


def _production_pct(stats: BadgeStats) -> float | None:
    assignment_pct = None
    if stats.total_assignments > 0:
        # A submitted TP shows effort; a reviewed TP is the stronger evidence.
        assignment_pct = round(
            _percent(stats.submitted_assignments, stats.total_assignments) * 0.4
            + _percent(stats.validated_assignments, stats.total_assignments) * 0.6,
            1,
        )
    # On guided paths the final project only gates Professional, so that it does
    # not hold back the early levels months before it is due.
    if stats.guided or not stats.has_final_project:
        return assignment_pct
    final_pct = 100.0 if stats.final_project_validated else 0.0
    if assignment_pct is None:
        return final_pct
    return round(assignment_pct * 0.7 + final_pct * 0.3, 1)


def badge_score(stats: BadgeStats) -> float:
    evaluation = [value for value in (quiz_mastery_pct(stats), stats.grade_average_pct) if value is not None]
    pillars = {
        "content": stats.lesson_progress_pct if stats.total_lessons > 0 else None,
        "evaluation": round(sum(evaluation) / len(evaluation), 1) if evaluation else None,
        "production": _production_pct(stats),
        "live": _percent(stats.attendance_present, stats.attendance_total) if stats.attendance_total > 0 else None,
    }
    weights = LIVE_PILLAR_WEIGHTS if stats.format_type == "live" else PILLAR_WEIGHTS
    active = {name: value for name, value in pillars.items() if value is not None}
    total_weight = sum(weights[name] for name in active)
    if total_weight <= 0:
        return 0.0
    return round(sum(value * weights[name] for name, value in active.items()) / total_weight, 1)


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
    if stats.total_assignments > 0:
        required = _required_count(stats.total_assignments, rule["assignments"])
        if level == "debutant":
            criteria.append(_Criterion(
                stats.submitted_assignments, required,
                f"rendez {required} TP sur {stats.total_assignments}",
            ))
        else:
            criteria.append(_Criterion(
                stats.validated_assignments, required,
                f"faites corriger et valider {required} TP sur {stats.total_assignments}",
            ))
    if stats.total_quizzes > 0:
        required = _required_count(stats.total_quizzes, rule["quizzes"])
        criteria.append(_Criterion(
            stats.passed_quizzes, required,
            f"réussissez {required} quiz sur {stats.total_quizzes}",
        ))
    if stats.attendance_total > 0:
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
    if level == "professionnel":
        if not stats.professional_eligible:
            criteria.append(_Criterion(0, 1, "attendez la fin de la session et la validation des séances"))
        if stats.has_final_project:
            criteria.append(_Criterion(
                1 if stats.final_project_validated else 0, 1,
                "validez le projet final avec au moins 80%",
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
