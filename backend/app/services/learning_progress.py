from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    AttendanceRecord,
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    LessonProgressRecord,
    LessonRecord,
    QuizAttemptRecord,
    QuizRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.academic import (
    AttendanceCourseDayRead,
    AttendanceMarkPayload,
    AttendanceRowRead,
    BadgeRead,
    ChapterReaderRead,
    CourseReaderRead,
    GradeRead,
    LearningSessionRead,
    LessonReaderRead,
    ProgressRead,
    StudentAttendanceRead,
    TeacherPerformanceRead,
    TeacherPerformanceSessionRead,
)
from app.services.academic_access import (
    formation_for_session,
    get_session,
    require_student_enrollment,
    require_teacher_assignment,
)
from app.services.grades import grade_average_pct
from app.services.tenancy import TenantContext


BADGE_LABELS = {
    "aventurier": "Aventurier",
    "debutant": "Débutant",
    "intermediaire": "Intermédiaire",
    "semi_pro": "Semi-pro",
    "professionnel": "Professionnel",
}
NEXT_BADGE = {
    "aventurier": "debutant",
    "debutant": "intermediaire",
    "intermediaire": "semi_pro",
    "semi_pro": "professionnel",
}


def _lesson_ids_for_session(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> list[int]:
    return list(
        db.scalars(
            select(LessonRecord.id)
            .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
            .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
            .where(
                CourseRecord.organization_id == tenant.organization_id,
                CourseRecord.session_id == session_id,
                CourseRecord.status == "published",
                LessonRecord.organization_id == tenant.organization_id,
            )
        ).all()
    )


def _completion_set(
    db: Session,
    tenant: TenantContext,
    enrollment_id: int,
) -> set[int]:
    return set(
        db.scalars(
            select(LessonProgressRecord.lesson_id).where(
                LessonProgressRecord.organization_id == tenant.organization_id,
                LessonProgressRecord.enrollment_id == enrollment_id,
            )
        ).all()
    )


def _lesson_progress(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> tuple[int, int, float]:
    lesson_ids = _lesson_ids_for_session(db, tenant, enrollment.session_id)
    completed = _completion_set(db, tenant, enrollment.id)
    completed_count = sum(1 for lesson_id in lesson_ids if lesson_id in completed)
    total = len(lesson_ids)
    pct = round((completed_count / total) * 100, 1) if total else 0.0
    return total, completed_count, pct


def list_student_learning(
    db: Session,
    tenant: TenantContext,
) -> list[LearningSessionRead]:
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
    result: list[LearningSessionRead] = []
    for enrollment in enrollments:
        session = get_session(db, tenant, enrollment.session_id)
        formation = formation_for_session(db, tenant, enrollment.session_id)
        completed = _completion_set(db, tenant, enrollment.id)
        courses = list(
            db.scalars(
                select(CourseRecord)
                .options(
                    selectinload(CourseRecord.teacher),
                    selectinload(CourseRecord.chapters).selectinload(ChapterRecord.lessons),
                )
                .where(
                    CourseRecord.organization_id == tenant.organization_id,
                    CourseRecord.session_id == session.id,
                    CourseRecord.status == "published",
                )
                .order_by(CourseRecord.created_at)
            ).all()
        )
        result.append(
            LearningSessionRead(
                enrollment_id=enrollment.id,
                session_id=session.id,
                formation_id=formation.id,
                formation_title=formation.title,
                session_label=session.label,
                courses=[
                    CourseReaderRead(
                        id=course.id,
                        title=course.title,
                        description=course.description,
                        teacher_name=course.teacher.full_name if course.teacher else None,
                        chapters=[
                            ChapterReaderRead(
                                id=chapter.id,
                                title=chapter.title,
                                order_index=chapter.order_index,
                                lessons=[
                                    LessonReaderRead(
                                        id=lesson.id,
                                        title=lesson.title,
                                        order_index=lesson.order_index,
                                        lesson_type=lesson.lesson_type,
                                        content=lesson.content,
                                        video_url=lesson.video_url,
                                        file_url=lesson.file_url,
                                        completed=lesson.id in completed,
                                    )
                                    for lesson in chapter.lessons
                                ],
                            )
                            for chapter in course.chapters
                        ],
                    )
                    for course in courses
                ],
            )
        )
    return result


def mark_lesson_complete(
    db: Session,
    tenant: TenantContext,
    lesson_id: int,
) -> LearningSessionRead:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")

    row = db.execute(
        select(LessonRecord, CourseRecord)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            LessonRecord.id == lesson_id,
            LessonRecord.organization_id == tenant.organization_id,
            CourseRecord.organization_id == tenant.organization_id,
            CourseRecord.status == "published",
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Leçon introuvable.")
    lesson, course = row
    enrollment = require_student_enrollment(db, tenant, course.session_id)

    existing = db.scalar(
        select(LessonProgressRecord).where(
            LessonProgressRecord.organization_id == tenant.organization_id,
            LessonProgressRecord.enrollment_id == enrollment.id,
            LessonProgressRecord.lesson_id == lesson.id,
        )
    )
    if existing is None:
        db.add(
            LessonProgressRecord(
                organization_id=tenant.organization_id,
                enrollment_id=enrollment.id,
                lesson_id=lesson.id,
                completed_at=datetime.now(UTC),
            )
        )
        db.commit()

    return next(
        item
        for item in list_student_learning(db, tenant)
        if item.enrollment_id == enrollment.id
    )


def _course_day_attendance(
    db: Session,
    tenant: TenantContext,
    day: SessionCourseDayRecord,
) -> AttendanceCourseDayRead:
    enrollments = list(
        db.scalars(
            select(EnrollmentRecord).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.session_id == day.session_id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        ).all()
    )
    rows: list[AttendanceRowRead] = []
    for enrollment in enrollments:
        student = db.get(UserRecord, enrollment.student_id)
        attendance = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == tenant.organization_id,
                AttendanceRecord.course_day_id == day.id,
                AttendanceRecord.enrollment_id == enrollment.id,
            )
        )
        rows.append(
            AttendanceRowRead(
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                student_name=student.full_name if student else "—",
                status=attendance.status if attendance else None,
            )
        )

    teacher = db.get(UserRecord, day.teacher_id) if day.teacher_id else None
    return AttendanceCourseDayRead(
        course_day_id=day.id,
        session_id=day.session_id,
        title=day.title,
        scheduled_at=day.scheduled_at,
        teacher_id=day.teacher_id,
        teacher_name=teacher.full_name if teacher else None,
        can_edit=day.teacher_id == tenant.user.id and not tenant.support_mode,
        rows=rows,
    )


def teacher_attendance(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> list[AttendanceCourseDayRead]:
    require_teacher_assignment(db, tenant, session_id)
    days = list(
        db.scalars(
            select(SessionCourseDayRecord).where(
                SessionCourseDayRecord.organization_id == tenant.organization_id,
                SessionCourseDayRecord.session_id == session_id,
                SessionCourseDayRecord.status != "cancelled",
            ).order_by(SessionCourseDayRecord.scheduled_at)
        ).all()
    )
    return [_course_day_attendance(db, tenant, day) for day in days]


def mark_attendance(
    db: Session,
    tenant: TenantContext,
    course_day_id: int,
    payload: AttendanceMarkPayload,
) -> AttendanceCourseDayRead:
    day = db.scalar(
        select(SessionCourseDayRecord).where(
            SessionCourseDayRecord.id == course_day_id,
            SessionCourseDayRecord.organization_id == tenant.organization_id,
        )
    )
    if day is None:
        raise HTTPException(404, "Séance introuvable.")
    require_teacher_assignment(db, tenant, day.session_id)
    if day.teacher_id != tenant.user.id:
        raise HTTPException(
            403,
            "La présence de ce créneau est gérée par le professeur propriétaire.",
        )
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")

    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.id == payload.enrollment_id,
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == day.session_id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )
    )
    if enrollment is None:
        raise HTTPException(422, "Cet étudiant n'appartient pas à la session.")

    row = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.organization_id == tenant.organization_id,
            AttendanceRecord.course_day_id == day.id,
            AttendanceRecord.enrollment_id == enrollment.id,
        )
    )
    if row is None:
        row = AttendanceRecord(
            organization_id=tenant.organization_id,
            course_day_id=day.id,
            enrollment_id=enrollment.id,
            status=payload.status,
            marked_by_user_id=tenant.user.id,
            marked_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.status = payload.status
        row.marked_by_user_id = tenant.user.id
        row.marked_at = datetime.now(UTC)
    db.commit()
    return _course_day_attendance(db, tenant, day)


def student_attendance(
    db: Session,
    tenant: TenantContext,
) -> list[StudentAttendanceRead]:
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
    result: list[StudentAttendanceRead] = []
    for enrollment in enrollments:
        days = list(
            db.scalars(
                select(SessionCourseDayRecord).where(
                    SessionCourseDayRecord.organization_id == tenant.organization_id,
                    SessionCourseDayRecord.session_id == enrollment.session_id,
                    SessionCourseDayRecord.status != "cancelled",
                ).order_by(SessionCourseDayRecord.scheduled_at)
            ).all()
        )
        for day in days:
            row = db.scalar(
                select(AttendanceRecord).where(
                    AttendanceRecord.organization_id == tenant.organization_id,
                    AttendanceRecord.course_day_id == day.id,
                    AttendanceRecord.enrollment_id == enrollment.id,
                )
            )
            result.append(
                StudentAttendanceRead(
                    course_day_id=day.id,
                    title=day.title,
                    scheduled_at=day.scheduled_at,
                    status=row.status if row else None,
                )
            )
    return result


def student_grades(
    db: Session,
    tenant: TenantContext,
) -> list[GradeRead]:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")
    enrollment_ids = list(
        db.scalars(
            select(EnrollmentRecord.id).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.student_id == tenant.user.id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
        ).all()
    )
    if not enrollment_ids:
        return []
    rows = list(
        db.scalars(
            select(GradeRecord).where(
                GradeRecord.organization_id == tenant.organization_id,
                GradeRecord.enrollment_id.in_(enrollment_ids),
            ).order_by(GradeRecord.created_at.desc())
        ).all()
    )
    return [
        GradeRead(
            id=row.id,
            session_id=row.session_id,
            label=row.label,
            source_type=row.source_type,
            score=row.score,
            max_score=row.max_score,
            note=row.note,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _assignment_stats(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> tuple[int, int, bool, bool]:
    assignments = list(
        db.scalars(
            select(AssignmentRecord).where(
                AssignmentRecord.organization_id == tenant.organization_id,
                AssignmentRecord.session_id == enrollment.session_id,
            )
        ).all()
    )
    submitted = 0
    has_final = False
    final_valid = False
    for assignment in assignments:
        submission = db.scalar(
            select(AssignmentSubmissionRecord).where(
                AssignmentSubmissionRecord.organization_id == tenant.organization_id,
                AssignmentSubmissionRecord.assignment_id == assignment.id,
                AssignmentSubmissionRecord.enrollment_id == enrollment.id,
            )
        )
        if submission:
            submitted += 1
        if assignment.is_final_project:
            has_final = True
            if (
                submission
                and submission.is_reviewed
                and submission.review_score is not None
                and submission.review_max_score > 0
                and (submission.review_score / submission.review_max_score) * 100 >= 80
            ):
                final_valid = True
    return len(assignments), submitted, has_final, final_valid


def _quiz_stats(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> tuple[int, int, int, float | None]:
    quizzes = list(
        db.scalars(
            select(QuizRecord).where(
                QuizRecord.organization_id == tenant.organization_id,
                QuizRecord.session_id == enrollment.session_id,
                QuizRecord.status.in_(["active", "closed"]),
            )
        ).all()
    )
    attempted = 0
    passed = 0
    best_scores: list[float] = []
    for quiz in quizzes:
        attempts = list(
            db.scalars(
                select(QuizAttemptRecord).where(
                    QuizAttemptRecord.organization_id == tenant.organization_id,
                    QuizAttemptRecord.quiz_id == quiz.id,
                    QuizAttemptRecord.enrollment_id == enrollment.id,
                )
            ).all()
        )
        if attempts:
            attempted += 1
            best = max(item.score_pct for item in attempts)
            best_scores.append(best)
            if best >= quiz.pass_pct:
                passed += 1
    average = round(sum(best_scores) / len(best_scores), 1) if best_scores else None
    return len(quizzes), attempted, passed, average


def _attendance_stats(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> tuple[int, int]:
    now = datetime.now(UTC)
    days = list(
        db.scalars(
            select(SessionCourseDayRecord).where(
                SessionCourseDayRecord.organization_id == tenant.organization_id,
                SessionCourseDayRecord.session_id == enrollment.session_id,
                SessionCourseDayRecord.status != "cancelled",
                SessionCourseDayRecord.scheduled_at <= now,
            )
        ).all()
    )
    present = 0
    for day in days:
        row = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == tenant.organization_id,
                AttendanceRecord.course_day_id == day.id,
                AttendanceRecord.enrollment_id == enrollment.id,
            )
        )
        if row and row.status == "present":
            present += 1
    return len(days), present


def badge_for_enrollment(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> BadgeRead:
    total_lessons, completed_lessons, lesson_pct = _lesson_progress(db, tenant, enrollment)
    total_assignments, submitted_assignments, has_final, final_valid = _assignment_stats(
        db, tenant, enrollment
    )
    total_quizzes, attempted_quizzes, passed_quizzes, _quiz_average = _quiz_stats(
        db, tenant, enrollment
    )
    attendance_total, attendance_present = _attendance_stats(db, tenant, enrollment)
    grade_pct = grade_average_pct(
        db,
        organization_id=tenant.organization_id,
        enrollment_id=enrollment.id,
    )

    assignment_pct = (
        round((submitted_assignments / total_assignments) * 100, 1)
        if total_assignments
        else None
    )
    quiz_pct = (
        round(((passed_quizzes * 0.8 + attempted_quizzes * 0.2) / total_quizzes) * 100, 1)
        if total_quizzes
        else None
    )
    attendance_pct = (
        round((attendance_present / attendance_total) * 100, 1)
        if attendance_total
        else None
    )

    formation = formation_for_session(db, tenant, enrollment.session_id)
    weights = (
        {"content": 24.7, "evaluation": 17.6, "production": 17.7, "live": 40.0}
        if formation.format_type == "live"
        else {"content": 35.0, "evaluation": 25.0, "production": 25.0, "live": 15.0}
    )
    pillars: dict[str, float] = {}
    if total_lessons:
        pillars["content"] = lesson_pct

    evaluation_values: list[float] = []
    if quiz_pct is not None:
        evaluation_values.append(quiz_pct)
    if grade_pct is not None:
        evaluation_values.append(grade_pct)
    if evaluation_values:
        pillars["evaluation"] = sum(evaluation_values) / len(evaluation_values)

    production_values: list[float] = []
    if assignment_pct is not None:
        production_values.append(assignment_pct)
    if has_final:
        production_values.append(100.0 if final_valid else 0.0)
    if production_values:
        pillars["production"] = sum(production_values) / len(production_values)

    if attendance_pct is not None:
        pillars["live"] = attendance_pct

    total_weight = sum(weights[key] for key in pillars)
    score = (
        round(sum(value * weights[key] for key, value in pillars.items()) / total_weight, 1)
        if total_weight
        else 0.0
    )

    professional = (
        score >= 90
        and (not total_lessons or lesson_pct >= 100)
        and (not total_assignments or submitted_assignments >= total_assignments)
        and (not total_quizzes or passed_quizzes >= max(1, round(total_quizzes * 0.8)))
        and (not attendance_total or attendance_pct is not None and attendance_pct >= 80)
        and (not has_final or final_valid)
        and (grade_pct is None or grade_pct >= 80)
    )
    if professional:
        level = "professionnel"
    elif score >= 75:
        level = "semi_pro"
    elif score >= 50:
        level = "intermediaire"
    elif score >= 25:
        level = "debutant"
    else:
        level = "aventurier"

    return BadgeRead(
        level=level,
        label=BADGE_LABELS[level],
        score_pct=score,
        next_level=NEXT_BADGE.get(level),
        lesson_progress_pct=lesson_pct,
        assignment_progress_pct=assignment_pct,
        quiz_progress_pct=quiz_pct,
        attendance_pct=attendance_pct,
        grade_average_pct=grade_pct,
        final_project_validated=final_valid,
    )


def progress_for_enrollment(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> ProgressRead:
    total_lessons, completed_lessons, lesson_pct = _lesson_progress(db, tenant, enrollment)
    total_assignments, submitted_assignments, _has_final, _final_valid = _assignment_stats(
        db, tenant, enrollment
    )
    total_quizzes, attempted_quizzes, _passed, _avg = _quiz_stats(db, tenant, enrollment)
    attendance_total, attendance_present = _attendance_stats(db, tenant, enrollment)
    grade_pct = grade_average_pct(
        db,
        organization_id=tenant.organization_id,
        enrollment_id=enrollment.id,
    )
    formation = formation_for_session(db, tenant, enrollment.session_id)
    session = get_session(db, tenant, enrollment.session_id)
    return ProgressRead(
        enrollment_id=enrollment.id,
        session_id=enrollment.session_id,
        formation_title=formation.title,
        session_label=session.label,
        completed_lessons=completed_lessons,
        total_lessons=total_lessons,
        lesson_progress_pct=lesson_pct,
        submitted_assignments=submitted_assignments,
        total_assignments=total_assignments,
        attempted_quizzes=attempted_quizzes,
        total_quizzes=total_quizzes,
        attendance_present=attendance_present,
        attendance_total=attendance_total,
        grade_average_pct=grade_pct,
        badge=badge_for_enrollment(db, tenant, enrollment),
    )


def student_progress(
    db: Session,
    tenant: TenantContext,
) -> list[ProgressRead]:
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
    return [progress_for_enrollment(db, tenant, enrollment) for enrollment in enrollments]


def teacher_performance(
    db: Session,
    tenant: TenantContext,
) -> TeacherPerformanceRead:
    if not tenant.has_role("teacher"):
        raise HTTPException(403, "Accès professeur requis.")
    assignments = list(
        db.scalars(
            select(SessionTeacherRecord).where(
                SessionTeacherRecord.organization_id == tenant.organization_id,
                SessionTeacherRecord.teacher_id == tenant.user.id,
            )
        ).all()
    )
    sessions: list[TeacherPerformanceSessionRead] = []
    distinct_students: set[int] = set()
    attendance_values: list[float] = []
    pending_total = 0

    for assignment in assignments:
        session = get_session(db, tenant, assignment.session_id)
        formation = formation_for_session(db, tenant, session.id)
        enrollments = list(
            db.scalars(
                select(EnrollmentRecord).where(
                    EnrollmentRecord.organization_id == tenant.organization_id,
                    EnrollmentRecord.session_id == session.id,
                    EnrollmentRecord.status.in_(["active", "completed"]),
                )
            ).all()
        )
        distinct_students.update(item.student_id for item in enrollments)

        progress_values = [
            progress_for_enrollment(db, tenant, item).badge.score_pct
            for item in enrollments
        ]
        session_progress = round(sum(progress_values) / len(progress_values), 1) if progress_values else 0.0

        attendance_rates: list[float] = []
        for enrollment in enrollments:
            total, present = _attendance_stats(db, tenant, enrollment)
            if total:
                attendance_rates.append((present / total) * 100)
        attendance_rate = (
            round(sum(attendance_rates) / len(attendance_rates), 1)
            if attendance_rates
            else None
        )
        if attendance_rate is not None:
            attendance_values.append(attendance_rate)

        quiz_scores: list[float] = []
        for enrollment in enrollments:
            _total, _attempted, _passed, avg = _quiz_stats(db, tenant, enrollment)
            if avg is not None:
                quiz_scores.append(avg)
        quiz_average = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else None

        teacher_assignment_ids = list(
            db.scalars(
                select(AssignmentRecord.id).where(
                    AssignmentRecord.organization_id == tenant.organization_id,
                    AssignmentRecord.session_id == session.id,
                    AssignmentRecord.teacher_id == tenant.user.id,
                )
            ).all()
        )
        pending_reviews = 0
        if teacher_assignment_ids:
            pending_reviews = int(
                db.scalar(
                    select(func.count(AssignmentSubmissionRecord.id)).where(
                        AssignmentSubmissionRecord.organization_id == tenant.organization_id,
                        AssignmentSubmissionRecord.assignment_id.in_(teacher_assignment_ids),
                        AssignmentSubmissionRecord.is_reviewed.is_(False),
                    )
                )
                or 0
            )
        pending_total += pending_reviews

        sessions.append(
            TeacherPerformanceSessionRead(
                session_id=session.id,
                formation_title=formation.title,
                session_label=session.label,
                enrolled_count=len(enrollments),
                progress_pct=session_progress,
                attendance_rate_pct=attendance_rate,
                quiz_average_score_pct=quiz_average,
                pending_reviews_count=pending_reviews,
            )
        )

    return TeacherPerformanceRead(
        total_sessions=len(assignments),
        total_students=len(distinct_students),
        attendance_rate_pct=(
            round(sum(attendance_values) / len(attendance_values), 1)
            if attendance_values
            else None
        ),
        pending_reviews_count=pending_total,
        sessions=sessions,
    )
