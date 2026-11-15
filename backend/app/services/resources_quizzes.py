from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    QuizAttemptRecord,
    QuizQuestionRecord,
    QuizRecord,
    ResourceRecord,
    SessionCourseDayRecord,
    UserRecord,
)
from app.schemas.academic import (
    QuizAttemptPayload,
    QuizAttemptRead,
    QuizCreate,
    QuizResultAttemptRead,
    ResourceCreate,
    ResourceRead,
    StudentQuizQuestionRead,
    StudentQuizRead,
    TeacherQuizQuestionRead,
    TeacherQuizRead,
    TeacherQuizResultsRead,
)
from app.services.academic_access import (
    formation_for_session,
    get_session,
    require_owned_course_day,
    require_student_enrollment,
    require_teacher_assignment,
)
from app.services.grades import upsert_grade
from app.services.lesson_completion import complete_activity_lessons
from app.services.pdf_lessons import PDF_READING_PCT, pdf_asset, pdf_lesson_for_quiz, viewed_pct
from app.models.entities import LessonPdfProgressRecord
from app.services.pedagogy_access import WORK_CLOSED_MESSAGE, current_utc, dashboard_type, guided_activity_available, guided_work_closed, linked_lesson_gate, session_starts_at
from app.services.school_communications import queue_school_event, queue_session_students_event
from app.services.school_notifications import notify_session_students
from app.services.program_versions import FROZEN_MESSAGE, is_frozen_requirement
from app.services.quiz_scoring import correct_answers, normalize_answer, question_points, stored_answer
from app.services.quiz_scoring import score_pct as quiz_score_pct
from app.services.tenancy import TenantContext


QUIZ_ATTEMPTS_PER_CYCLE = 3
QUIZ_RETRY_HOURS = 8


def quiz_attempt_gate(attempts: list[QuizAttemptRecord], now: datetime) -> tuple[int, datetime | None]:
    """Return the tries left and the end of the wait for a quiz not yet passed.

    As on the mother site, every quiz gives three tries per cycle. After the third
    failure of a cycle, the student waits eight hours, then a new cycle of three starts.
    """
    used = len(attempts) % QUIZ_ATTEMPTS_PER_CYCLE
    if attempts and used == 0:
        unlock_at = current_utc(attempts[-1].submitted_at) + timedelta(hours=QUIZ_RETRY_HOURS)
        if now < unlock_at:
            return 0, unlock_at
    return QUIZ_ATTEMPTS_PER_CYCLE - used, None


def _teacher_name(db: Session, teacher_id: int | None) -> str | None:
    if teacher_id is None:
        return None
    user = db.get(UserRecord, teacher_id)
    return user.full_name if user else None


def _resource_view(
    db: Session,
    tenant: TenantContext,
    row: ResourceRecord,
) -> ResourceRead:
    session = get_session(db, tenant, row.session_id)
    formation = formation_for_session(db, tenant, row.session_id)
    return ResourceRead(
        id=row.id,
        session_id=row.session_id,
        course_day_id=row.course_day_id,
        teacher_id=row.teacher_id,
        teacher_name=_teacher_name(db, row.teacher_id),
        formation_title=formation.title,
        session_label=session.label,
        title=row.title,
        resource_type=row.resource_type,
        url=row.url,
        published_at=row.published_at,
        created_at=row.created_at,
    )


def list_teacher_resources(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> list[ResourceRead]:
    require_teacher_assignment(db, tenant, session_id)
    rows = db.scalars(
        select(ResourceRecord)
        .where(
            ResourceRecord.organization_id == tenant.organization_id,
            ResourceRecord.session_id == session_id,
        )
        .order_by(ResourceRecord.created_at.desc())
    ).all()
    return [_resource_view(db, tenant, row) for row in rows]


def create_resource(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    payload: ResourceCreate,
) -> ResourceRead:
    session = get_session(db, tenant, session_id)
    require_teacher_assignment(db, tenant, session_id)
    require_owned_course_day(db, tenant, session_id, payload.course_day_id)
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")
    if session.status in {"cancelled", "completed"}:
        raise HTTPException(409, "Cette session n'accepte plus de nouvelles ressources.")

    row = ResourceRecord(
        organization_id=tenant.organization_id,
        session_id=session_id,
        course_day_id=payload.course_day_id,
        teacher_id=tenant.user.id,
        title=payload.title,
        resource_type=payload.resource_type,
        url=payload.url,
        published_at=datetime.now(UTC) if payload.publish_now else None,
    )
    db.add(row)
    db.flush()
    if row.published_at is not None:
        notify_session_students(
            db, organization_id=tenant.organization_id, session_id=session_id,
            event_key=f"resource.published:{row.id}",
            title="Nouvelle ressource disponible",
            message=f"{row.title} est disponible dans votre session.",
            action_label="Voir les ressources", action_path="/app/student/resources",
        )
    db.commit()
    db.refresh(row)
    return _resource_view(db, tenant, row)


def list_student_resources(
    db: Session,
    tenant: TenantContext,
) -> list[ResourceRead]:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")

    session_ids = list(
        db.scalars(
            select(EnrollmentRecord.session_id).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.student_id == tenant.user.id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        ).all()
    )
    if not session_ids:
        return []

    now = datetime.now(UTC)
    rows = list(
        db.scalars(
            select(ResourceRecord)
            .where(
                ResourceRecord.organization_id == tenant.organization_id,
                ResourceRecord.session_id.in_(session_ids),
                ResourceRecord.published_at.is_not(None),
                ResourceRecord.published_at <= now,
            )
            .order_by(ResourceRecord.published_at.desc())
        ).all()
    )
    available: list[ResourceRead] = []
    for row in rows:
        session = get_session(db, tenant, row.session_id)
        formation = formation_for_session(db, tenant, row.session_id)
        day = db.get(SessionCourseDayRecord, row.course_day_id) if row.course_day_id else None
        if guided_activity_available(
            formation, session, day=day, published_at=row.published_at, now=now,
        ):
            available.append(_resource_view(db, tenant, row))
    return available


def _teacher_quiz_view(
    db: Session,
    row: QuizRecord,
) -> TeacherQuizRead:
    attempts_count = int(
        db.scalar(
            select(func.count(QuizAttemptRecord.id)).where(
                QuizAttemptRecord.quiz_id == row.id,
                QuizAttemptRecord.organization_id == row.organization_id,
            )
        )
        or 0
    )
    return TeacherQuizRead(
        id=row.id,
        session_id=row.session_id,
        course_day_id=row.course_day_id,
        teacher_id=row.teacher_id,
        teacher_name=_teacher_name(db, row.teacher_id),
        title=row.title,
        assessment_type=row.assessment_type,
        duration_minutes=row.duration_minutes,
        scheduled_at=row.scheduled_at,
        status=row.status,
        pass_pct=row.pass_pct,
        questions=[
            TeacherQuizQuestionRead(
                id=question.id,
                order_index=question.order_index,
                text=question.text,
                options=list(question.options or []),
                correct_index=question.correct_index,
                selection_mode=question.selection_mode or "single",
                correct_indices=correct_answers(question),
                points=question_points(question),
            )
            for question in row.questions
        ],
        attempts_count=attempts_count,
        created_at=row.created_at,
    )


def list_teacher_quizzes(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> list[TeacherQuizRead]:
    require_teacher_assignment(db, tenant, session_id)
    rows = list(
        db.scalars(
            select(QuizRecord)
            .options(selectinload(QuizRecord.questions))
            .where(
                QuizRecord.organization_id == tenant.organization_id,
                QuizRecord.session_id == session_id,
            )
            .order_by(QuizRecord.created_at.desc())
        ).all()
    )
    return [_teacher_quiz_view(db, row) for row in rows]


def create_quiz(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    payload: QuizCreate,
) -> TeacherQuizRead:
    session = get_session(db, tenant, session_id)
    require_teacher_assignment(db, tenant, session_id)
    require_owned_course_day(db, tenant, session_id, payload.course_day_id)
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")
    if session.status in {"cancelled", "completed"}:
        raise HTTPException(409, "Cette session n'accepte plus de nouvelle évaluation.")

    if payload.scheduled_at is not None:
        value = payload.scheduled_at
        if value.date() < session.start_date or value.date() > session.end_date:
            raise HTTPException(422, "La date de l'évaluation doit rester dans la session.")

    quiz = QuizRecord(
        organization_id=tenant.organization_id,
        session_id=session_id,
        course_day_id=payload.course_day_id,
        teacher_id=tenant.user.id,
        title=payload.title.strip(),
        assessment_type=payload.assessment_type,
        duration_minutes=payload.duration_minutes,
        scheduled_at=payload.scheduled_at,
        status="draft",
        pass_pct=payload.pass_pct,
    )
    db.add(quiz)
    db.flush()

    for index, question in enumerate(payload.questions):
        db.add(
            QuizQuestionRecord(
                organization_id=tenant.organization_id,
                quiz_id=quiz.id,
                order_index=index,
                text=question.text.strip(),
                options=[item.strip() for item in question.options],
                correct_index=question.correct_index,
                selection_mode=question.selection_mode,
                correct_indices=question.correct_indices,
                points=question.points,
            )
        )

    db.commit()
    quiz = db.scalar(
        select(QuizRecord)
        .options(selectinload(QuizRecord.questions))
        .where(QuizRecord.id == quiz.id)
    )
    return _teacher_quiz_view(db, quiz)


def set_quiz_status(
    db: Session,
    tenant: TenantContext,
    quiz_id: int,
    status_value: str,
) -> TeacherQuizRead:
    quiz = db.scalar(
        select(QuizRecord)
        .options(selectinload(QuizRecord.questions))
        .where(
            QuizRecord.id == quiz_id,
            QuizRecord.organization_id == tenant.organization_id,
        )
    )
    if quiz is None:
        raise HTTPException(404, "Évaluation introuvable.")
    require_teacher_assignment(db, tenant, quiz.session_id)
    if quiz.teacher_id != tenant.user.id:
        raise HTTPException(
            403,
            "Cette évaluation appartient à un autre professeur.",
        )
    previous_status = quiz.status
    if status_value == "draft" and previous_status != "draft" and is_frozen_requirement(db, quiz.session_id, "quiz_ids", quiz.id):
        raise HTTPException(409, FROZEN_MESSAGE)
    quiz.status = status_value
    if status_value == "active" and quiz.opened_at is None:
        quiz.opened_at = datetime.now(UTC)
    if status_value == "active" and previous_status != "active":
        session = get_session(db, tenant, quiz.session_id)
        queue_session_students_event(
            db,
            org=tenant.organization,
            session_id=quiz.session_id,
            event_key="student.quiz.published",
            context={
                "quiz_title": quiz.title,
                "session_label": session.label,
            },
        )
        notify_session_students(
            db, organization_id=tenant.organization_id, session_id=quiz.session_id,
            event_key=f"quiz.published:{quiz.id}",
            title="Nouveau quiz disponible",
            message=f"{quiz.title} est disponible dans votre session.",
            action_label="Voir le quiz", action_path=f"/app/student/quizzes#quiz-{quiz.id}",
        )
    db.commit()
    db.refresh(quiz)
    return _teacher_quiz_view(db, quiz)


def _attempts_for(
    db: Session,
    tenant: TenantContext,
    quiz_id: int,
    enrollment_id: int,
) -> list[QuizAttemptRecord]:
    return list(
        db.scalars(
            select(QuizAttemptRecord)
            .where(
                QuizAttemptRecord.organization_id == tenant.organization_id,
                QuizAttemptRecord.quiz_id == quiz_id,
                QuizAttemptRecord.enrollment_id == enrollment_id,
            )
            .order_by(QuizAttemptRecord.attempt_number)
        ).all()
    )


def _student_quiz_view(
    db: Session,
    tenant: TenantContext,
    quiz: QuizRecord,
    enrollment: EnrollmentRecord,
) -> StudentQuizRead:
    session = get_session(db, tenant, quiz.session_id)
    formation = formation_for_session(db, tenant, quiz.session_id)
    attempts = _attempts_for(db, tenant, quiz.id, enrollment.id)
    best = max((item.score_pct for item in attempts), default=None)
    passed = best is not None and best >= quiz.pass_pct
    now = datetime.now(UTC)
    scheduled_open = quiz.scheduled_at is None or now >= current_utc(quiz.scheduled_at)
    day = db.get(SessionCourseDayRecord, quiz.course_day_id) if quiz.course_day_id else None
    activity_open = guided_activity_available(
        formation, session, scheduled_at=quiz.scheduled_at, day=day, now=now,
    )
    opening_times = []
    if dashboard_type(formation) == "guided":
        opening_times.append(session_starts_at(session))
    if quiz.scheduled_at is not None:
        opening_times.append(current_utc(quiz.scheduled_at))
    if day is not None:
        opening_times.append(current_utc(day.scheduled_at))
    available_at = max(opening_times) if opening_times else None
    linked_gate = linked_lesson_gate(db, formation, session, "quiz", quiz.id, now=now)
    if linked_gate is not None:
        linked_opening, linked_available = linked_gate
        if linked_opening is not None:
            available_at = max(available_at, linked_opening) if available_at else linked_opening
        activity_open = activity_open and linked_available
    pdf_lesson = pdf_lesson_for_quiz(db, tenant.organization_id, session.id, quiz.id)
    pdf_reading_pct = None
    pdf_reading_locked = False
    if pdf_lesson is not None:
        asset = pdf_asset(db, tenant.organization_id, pdf_lesson.file_url)
        progress = db.scalar(select(LessonPdfProgressRecord).where(
            LessonPdfProgressRecord.organization_id == tenant.organization_id,
            LessonPdfProgressRecord.enrollment_id == enrollment.id,
            LessonPdfProgressRecord.lesson_id == pdf_lesson.id,
        ))
        pdf_reading_pct = viewed_pct(progress if progress is not None and asset is not None and progress.source_sha == asset.source_sha else None, asset.page_count if asset else 0)
        pdf_reading_locked = pdf_reading_pct < PDF_READING_PCT
        activity_open = activity_open and not pdf_reading_locked
    locked = not activity_open or quiz.status != "active"
    attempts_remaining, next_attempt_available_at = (0, None) if passed else quiz_attempt_gate(attempts, now)
    work_closed = guided_work_closed(formation, session, now=now)
    can_attempt = (
        quiz.status == "active"
        and scheduled_open
        and activity_open
        and attempts_remaining > 0
        and not work_closed
    )
    return StudentQuizRead(
        id=quiz.id,
        session_id=quiz.session_id,
        enrollment_id=enrollment.id,
        formation_title=formation.title,
        session_label=session.label,
        teacher_name=_teacher_name(db, quiz.teacher_id),
        title=quiz.title,
        assessment_type=quiz.assessment_type,
        duration_minutes=quiz.duration_minutes,
        scheduled_at=quiz.scheduled_at,
        available_at=available_at,
        is_locked=locked,
        pass_pct=quiz.pass_pct,
        questions=[
            StudentQuizQuestionRead(
                id=question.id,
                order_index=question.order_index,
                text=question.text,
                options=list(question.options or []),
                selection_mode=question.selection_mode or "single",
                points=question_points(question),
            )
            for question in quiz.questions
        ] if not locked else [],
        attempts=[
            QuizAttemptRead(
                id=item.id,
                attempt_number=item.attempt_number,
                score_pct=item.score_pct,
                submitted_at=item.submitted_at,
                submitted_answers=[stored_answer(question, answer) for question, answer in zip(quiz.questions, item.answers or [])],
                correct_answers=[correct_answers(question) for question in quiz.questions],
            )
            for item in attempts
        ],
        best_score_pct=best,
        passed=passed,
        can_attempt=can_attempt,
        attempts_remaining=attempts_remaining,
        next_attempt_available_at=next_attempt_available_at,
        pdf_reading_pct=pdf_reading_pct,
        pdf_reading_locked=pdf_reading_locked,
        work_closed=work_closed,
    )


def list_student_quizzes(
    db: Session,
    tenant: TenantContext,
) -> list[StudentQuizRead]:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")

    enrollments = list(
        db.scalars(
            select(EnrollmentRecord).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.student_id == tenant.user.id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        ).all()
    )
    result: list[StudentQuizRead] = []
    for enrollment in enrollments:
        quizzes = list(
            db.scalars(
                select(QuizRecord)
                .options(selectinload(QuizRecord.questions))
                .where(
                    QuizRecord.organization_id == tenant.organization_id,
                    QuizRecord.session_id == enrollment.session_id,
                    QuizRecord.status.in_(["active", "closed"]),
                )
                .order_by(QuizRecord.scheduled_at, QuizRecord.created_at)
            ).all()
        )
        result.extend(
            _student_quiz_view(db, tenant, quiz, enrollment)
            for quiz in quizzes
        )
    return result


def submit_quiz_attempt(
    db: Session,
    tenant: TenantContext,
    quiz_id: int,
    payload: QuizAttemptPayload,
) -> StudentQuizRead:
    quiz = db.scalar(
        select(QuizRecord)
        .options(selectinload(QuizRecord.questions))
        .where(
            QuizRecord.id == quiz_id,
            QuizRecord.organization_id == tenant.organization_id,
        )
    )
    if quiz is None:
        raise HTTPException(404, "Évaluation introuvable.")

    enrollment = require_student_enrollment(db, tenant, quiz.session_id)
    db.get(EnrollmentRecord, enrollment.id, populate_existing=True, with_for_update=True)
    view = _student_quiz_view(db, tenant, quiz, enrollment)
    if view.work_closed:
        raise HTTPException(409, WORK_CLOSED_MESSAGE)
    if not view.can_attempt:
        raise HTTPException(409, "Cette évaluation n'accepte pas de nouvelle tentative.")

    questions = list(quiz.questions)
    if len(payload.answers) != len(questions):
        raise HTTPException(422, "Toutes les questions doivent recevoir une réponse.")

    picked = [normalize_answer(question, answer) for question, answer in zip(questions, payload.answers)]
    score_pct = quiz_score_pct(questions, picked)
    attempts = _attempts_for(db, tenant, quiz.id, enrollment.id)
    row = QuizAttemptRecord(
        organization_id=tenant.organization_id,
        quiz_id=quiz.id,
        enrollment_id=enrollment.id,
        attempt_number=len(attempts) + 1,
        answers=picked,
        score_pct=score_pct,
        submitted_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    if score_pct >= quiz.pass_pct:
        complete_activity_lessons(
            db,
            organization_id=tenant.organization_id,
            session_id=quiz.session_id,
            enrollment_id=enrollment.id,
            activity_type="quiz",
            activity_id=quiz.id,
        )

    previous_best = max((item.score_pct for item in attempts), default=0.0)
    best_score = max(previous_best, score_pct)
    upsert_grade(
        db,
        organization_id=tenant.organization_id,
        session_id=quiz.session_id,
        enrollment_id=enrollment.id,
        teacher_id=quiz.teacher_id,
        source_type="quiz",
        source_id=quiz.id,
        label=("Examen : " if quiz.assessment_type == "exam" else "Quiz : ") + quiz.title,
        score=round((best_score / 100) * 20, 2),
        max_score=20,
        note="Note automatique calculée depuis le meilleur score.",
    )
    queue_school_event(
        db,
        org=tenant.organization,
        user=tenant.user,
        event_key="student.quiz.result",
        context={
            "quiz_title": quiz.title,
            "score_pct": score_pct,
        },
    )
    db.commit()
    return _student_quiz_view(db, tenant, quiz, enrollment)


def teacher_quiz_results(
    db: Session,
    tenant: TenantContext,
    quiz_id: int,
) -> TeacherQuizResultsRead:
    quiz = db.get(QuizRecord, quiz_id)
    if quiz is None or quiz.organization_id != tenant.organization_id:
        raise HTTPException(404, "Évaluation introuvable.")
    require_teacher_assignment(db, tenant, quiz.session_id)

    enrollment_ids = list(
        db.scalars(
            select(EnrollmentRecord.id).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.session_id == quiz.session_id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        ).all()
    )
    attempts = list(
        db.scalars(
            select(QuizAttemptRecord)
            .where(
                QuizAttemptRecord.organization_id == tenant.organization_id,
                QuizAttemptRecord.quiz_id == quiz.id,
            )
            .order_by(QuizAttemptRecord.submitted_at)
        ).all()
    )

    result: list[QuizResultAttemptRead] = []
    for attempt in attempts:
        enrollment = db.get(EnrollmentRecord, attempt.enrollment_id)
        student = db.get(UserRecord, enrollment.student_id) if enrollment else None
        result.append(
            QuizResultAttemptRead(
                enrollment_id=attempt.enrollment_id,
                student_name=student.full_name if student else "-",
                attempt_number=attempt.attempt_number,
                score_pct=attempt.score_pct,
                submitted_at=attempt.submitted_at,
            )
        )

    return TeacherQuizResultsRead(
        quiz_id=quiz.id,
        title=quiz.title,
        total_students=len(enrollment_ids),
        attempts=result,
    )
