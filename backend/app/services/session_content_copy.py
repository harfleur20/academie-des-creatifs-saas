"""A new session takes back the content of an earlier one of the same formation.

The school builds a formation's courses once and reuses them from one session to the next:
courses, modules and lessons are copied as they are. Quizzes (with their questions),
assignments and resources are copied as drafts, their dates moved by as many days as the new
session starts after the old one, so the teacher checks them before publishing. The planning
of course days, the students and everything they did stay with the old session.
"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    AssignmentRecord,
    ChapterRecord,
    CourseRecord,
    FormationSessionRecord,
    LessonRecord,
    QuizQuestionRecord,
    QuizRecord,
    ResourceRecord,
    SessionTeacherRecord,
)
from app.services.tenancy import TenantContext


def _shifted(value, days: timedelta):
    return value + days if value is not None else None


def copy_session_content(
    db: Session,
    tenant: TenantContext,
    source: FormationSessionRecord,
    target: FormationSessionRecord,
    *,
    with_teachers: bool,
) -> None:
    if source.organization_id != tenant.organization_id or source.formation_id != target.formation_id or source.id == target.id:
        raise HTTPException(422, "Choisissez une session de cette formation pour en reprendre le contenu.")
    org_id = tenant.organization_id
    shift = timedelta(days=(target.start_date - source.start_date).days)

    teacher_ids: set[int] = set()
    if with_teachers:
        for assignment in db.scalars(select(SessionTeacherRecord).where(
            SessionTeacherRecord.organization_id == org_id, SessionTeacherRecord.session_id == source.id,
        ).order_by(SessionTeacherRecord.id)).all():
            db.add(SessionTeacherRecord(organization_id=org_id, session_id=target.id,
                                        teacher_id=assignment.teacher_id, role=assignment.role))
            teacher_ids.add(assignment.teacher_id)

    def teacher(value: int | None) -> int | None:
        # A course or an activity keeps its teacher only when that teacher comes along.
        return value if value in teacher_ids else None

    quizzes: dict[int, int] = {}
    for quiz in db.scalars(select(QuizRecord).options(selectinload(QuizRecord.questions)).where(
        QuizRecord.organization_id == org_id, QuizRecord.session_id == source.id,
    ).order_by(QuizRecord.id)).all():
        copy = QuizRecord(
            organization_id=org_id, session_id=target.id, teacher_id=teacher(quiz.teacher_id), title=quiz.title,
            assessment_type=quiz.assessment_type, duration_minutes=quiz.duration_minutes,
            scheduled_at=_shifted(quiz.scheduled_at, shift), status="draft", pass_pct=quiz.pass_pct,
        )
        copy.questions = [QuizQuestionRecord(
            organization_id=org_id, order_index=question.order_index, text=question.text, options=list(question.options),
            correct_index=question.correct_index, selection_mode=question.selection_mode,
            correct_indices=list(question.correct_indices) if question.correct_indices is not None else None,
            points=question.points,
        ) for question in quiz.questions]
        db.add(copy)
        db.flush()
        quizzes[quiz.id] = copy.id

    assignments: dict[int, int] = {}
    for assignment in db.scalars(select(AssignmentRecord).where(
        AssignmentRecord.organization_id == org_id, AssignmentRecord.session_id == source.id,
    ).order_by(AssignmentRecord.id)).all():
        copy = AssignmentRecord(
            organization_id=org_id, session_id=target.id, teacher_id=teacher(assignment.teacher_id),
            title=assignment.title, publication_status="draft", instructions=assignment.instructions,
            brief_json=assignment.brief_json, due_date=assignment.due_date + shift,
            is_final_project=assignment.is_final_project,
        )
        db.add(copy)
        db.flush()
        assignments[assignment.id] = copy.id

    resources: dict[int, int] = {}
    for resource in db.scalars(select(ResourceRecord).where(
        ResourceRecord.organization_id == org_id, ResourceRecord.session_id == source.id,
    ).order_by(ResourceRecord.id)).all():
        copy = ResourceRecord(
            organization_id=org_id, session_id=target.id, teacher_id=teacher(resource.teacher_id), title=resource.title,
            resource_type=resource.resource_type, url=resource.url, published_at=None,
        )
        db.add(copy)
        db.flush()
        resources[resource.id] = copy.id

    courses = db.scalars(select(CourseRecord).options(
        selectinload(CourseRecord.chapters).selectinload(ChapterRecord.lessons),
    ).where(
        CourseRecord.organization_id == org_id, CourseRecord.session_id == source.id, CourseRecord.status != "archived",
    ).order_by(CourseRecord.id)).all()
    from app.services.formations import _record_lesson_version

    for course in courses:
        course_copy = CourseRecord(
            organization_id=org_id, session_id=target.id, teacher_id=teacher(course.teacher_id),
            title=course.title, description=course.description, status=course.status,
        )
        db.add(course_copy)
        db.flush()
        for chapter in course.chapters:
            chapter_copy = ChapterRecord(organization_id=org_id, course_id=course_copy.id, title=chapter.title,
                                         order_index=chapter.order_index)
            db.add(chapter_copy)
            db.flush()
            for lesson in chapter.lessons:
                lesson_copy = LessonRecord(
                    organization_id=org_id, chapter_id=chapter_copy.id, title=lesson.title,
                    order_index=lesson.order_index, lesson_type=lesson.lesson_type,
                    publication_status=lesson.publication_status, content=lesson.content,
                    video_url=lesson.video_url, file_url=lesson.file_url,
                    quiz_id=quizzes.get(lesson.quiz_id) if lesson.quiz_id else None,
                    assignment_id=assignments.get(lesson.assignment_id) if lesson.assignment_id else None,
                    resource_id=resources.get(lesson.resource_id) if lesson.resource_id else None,
                    available_at=_shifted(lesson.available_at, shift),
                )
                db.add(lesson_copy)
                db.flush()
                _record_lesson_version(db, tenant, lesson_copy, "created")


def copy_source_for(db: Session, tenant: TenantContext, formation_id: int, session_id: int) -> FormationSessionRecord:
    source = db.scalar(select(FormationSessionRecord).where(
        FormationSessionRecord.id == session_id,
        FormationSessionRecord.organization_id == tenant.organization_id,
        FormationSessionRecord.formation_id == formation_id,
    ))
    if source is None:
        raise HTTPException(404, "La session dont reprendre le contenu est introuvable.")
    return source
