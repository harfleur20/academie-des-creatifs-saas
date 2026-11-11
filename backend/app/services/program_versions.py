"""Frozen guided programs and badge history, ported from the mother site's program_versions.

A guided (live or présentiel) session freezes its program once it has started and is
complete. Frozen lessons, quizzes and assignments then accept editorial corrections
only: changing their structure would change what students are measured against.
Badges follow the mother site's dynamic rules (what is published and open counts),
but a level once reached is kept: the displayed badge never goes below it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentRecord,
    BadgeAwardRecord,
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    LessonRecord,
    QuizRecord,
    SessionCourseDayRecord,
    SessionProgramVersionRecord,
)
from app.services.pedagogy_access import current_utc, dashboard_type, learning_is_open, session_ends_at

BADGE_ORDER = {"aventurier": 0, "debutant": 1, "intermediaire": 2, "semi_pro": 3, "professionnel": 4}
FROZEN_MESSAGE = (
    "Ce contenu fait partie du programme figé de la session. Seules les corrections de texte "
    "sont possibles : créez un nouveau contenu pour changer sa structure."
)


@dataclass(frozen=True)
class ProgramReadiness:
    missing: tuple[str, ...]
    counts: dict[str, int]

    @property
    def ready(self) -> bool:
        return not self.missing


def _published_lessons(db: Session, session: FormationSessionRecord) -> list[LessonRecord]:
    return list(db.scalars(
        select(LessonRecord)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            CourseRecord.organization_id == session.organization_id,
            CourseRecord.session_id == session.id,
            CourseRecord.status == "published",
            LessonRecord.publication_status == "published",
        )
        .order_by(CourseRecord.id, ChapterRecord.order_index, LessonRecord.order_index, LessonRecord.id)
    ).all())


def build_program_snapshot(db: Session, session: FormationSessionRecord) -> dict[str, object]:
    lessons = _published_lessons(db, session)
    validation_quiz_ids = {lesson.quiz_id for lesson in lessons if lesson.lesson_type in {"text", "pdf"} and lesson.quiz_id}
    quiz_ids = sorted(
        quiz_id for quiz_id in db.scalars(select(QuizRecord.id).where(
            QuizRecord.organization_id == session.organization_id,
            QuizRecord.session_id == session.id,
            QuizRecord.status.in_(["active", "closed"]),
        )).all()
        if quiz_id not in validation_quiz_ids
    )
    assignments = db.scalars(select(AssignmentRecord).where(
        AssignmentRecord.organization_id == session.organization_id,
        AssignmentRecord.session_id == session.id,
        AssignmentRecord.publication_status == "published",
    ).order_by(AssignmentRecord.id)).all()
    course_day_ids = list(db.scalars(select(SessionCourseDayRecord.id).where(
        SessionCourseDayRecord.organization_id == session.organization_id,
        SessionCourseDayRecord.session_id == session.id,
        SessionCourseDayRecord.status != "cancelled",
    ).order_by(SessionCourseDayRecord.scheduled_at, SessionCourseDayRecord.id)).all())
    return {
        "lesson_ids": [lesson.id for lesson in lessons],
        "content_lesson_ids": [lesson.id for lesson in lessons if lesson.lesson_type not in {"quiz", "assignment"}],
        "quiz_ids": quiz_ids,
        "assignment_ids": [item.id for item in assignments if not item.is_final_project],
        "final_project_ids": [item.id for item in assignments if item.is_final_project],
        "course_day_ids": course_day_ids,
    }


def program_readiness(db: Session, session: FormationSessionRecord, formation: FormationRecord) -> ProgramReadiness:
    """What the mother site checks before a guided program can be frozen."""
    snapshot = build_program_snapshot(db, session)
    lessons = _published_lessons(db, session)
    published_courses = int(db.scalar(select(func.count(CourseRecord.id)).where(
        CourseRecord.organization_id == session.organization_id,
        CourseRecord.session_id == session.id,
        CourseRecord.status == "published",
    )) or 0)
    missing: list[str] = []
    if published_courses == 0:
        missing.append("publiez au moins un cours")
    if not lessons:
        missing.append("publiez au moins une leçon")
    if formation.format_type in {"live", "presentiel"} and not snapshot["course_day_ids"]:
        missing.append("planifiez au moins une séance")
    session_end = session_ends_at(session)
    late = next((lesson for lesson in lessons if lesson.available_at and current_utc(lesson.available_at) > session_end), None)
    if late is not None:
        missing.append(f"la leçon « {late.title} » ouvre après la fin de la session")
    linked_quiz_ids = {lesson.quiz_id for lesson in lessons if lesson.quiz_id}
    if linked_quiz_ids:
        active = set(db.scalars(select(QuizRecord.id).where(
            QuizRecord.id.in_(linked_quiz_ids), QuizRecord.status.in_(["active", "closed"]),
        )).all())
        if linked_quiz_ids - active:
            missing.append("activez les quiz liés aux leçons publiées")
    counts = {
        "courses": published_courses,
        "lessons": len(snapshot["lesson_ids"]),
        "quizzes": len(snapshot["quiz_ids"]),
        "assignments": len(snapshot["assignment_ids"]),
        "final_projects": len(snapshot["final_project_ids"]),
        "course_days": len(snapshot["course_day_ids"]),
    }
    return ProgramReadiness(tuple(missing), counts)


def active_program_version(db: Session, session_id: int) -> SessionProgramVersionRecord | None:
    return db.scalar(select(SessionProgramVersionRecord).where(
        SessionProgramVersionRecord.session_id == session_id,
    ).order_by(SessionProgramVersionRecord.version.desc()))


def ensure_program_frozen(
    db: Session,
    session: FormationSessionRecord,
    formation: FormationRecord,
    *,
    now: datetime | None = None,
) -> SessionProgramVersionRecord | None:
    """Freeze a started, complete guided program once; return None while it cannot be frozen."""
    existing = active_program_version(db, session.id)
    if existing is not None:
        return existing
    if dashboard_type(formation) != "guided" or not learning_is_open(formation, session, now=now):
        return None
    if not program_readiness(db, session, formation).ready:
        return None
    try:
        # Two first readers of a just-started session may both try: the loser reuses the winner's version.
        with db.begin_nested():
            version = SessionProgramVersionRecord(
                organization_id=session.organization_id, session_id=session.id, version=1,
                frozen_at=current_utc(now), requirements_json=build_program_snapshot(db, session),
            )
            db.add(version)
    except IntegrityError:
        return active_program_version(db, session.id)
    db.commit()
    return version


def is_frozen_requirement(db: Session, session_id: int, key: str, entity_id: int) -> bool:
    versions = db.scalars(select(SessionProgramVersionRecord.requirements_json).where(
        SessionProgramVersionRecord.session_id == session_id,
    )).all()
    return any(entity_id in (requirements or {}).get(key, []) for requirements in versions)


def require_structure_mutable(db: Session, session_id: int, key: str, entity_id: int) -> None:
    if is_frozen_requirement(db, session_id, key, entity_id):
        raise HTTPException(409, FROZEN_MESSAGE)


def badge_floor(
    db: Session,
    *,
    enrollment: EnrollmentRecord,
    version: SessionProgramVersionRecord,
    level: str,
    score_pct: float,
    evidence: dict[str, object],
) -> str:
    """Record the level reached and return the level to show: never below the best one reached."""
    awards = {award.level for award in db.scalars(select(BadgeAwardRecord).where(
        BadgeAwardRecord.enrollment_id == enrollment.id,
    )).all()}
    if level != "aventurier" and level not in awards:
        try:
            with db.begin_nested():
                db.add(BadgeAwardRecord(
                    organization_id=enrollment.organization_id, enrollment_id=enrollment.id,
                    program_version_id=version.id, level=level, score_pct=score_pct,
                    evidence_json=evidence, awarded_at=datetime.now(UTC),
                ))
            db.commit()
        except IntegrityError:
            pass  # recorded meanwhile by a concurrent read
        awards.add(level)
    best = max(awards | {level}, key=lambda item: BADGE_ORDER.get(item, -1))
    return best
