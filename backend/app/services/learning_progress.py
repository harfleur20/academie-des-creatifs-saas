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
    LessonVideoProgressRecord,
    QuizAttemptRecord,
    QuizRecord,
    ResourceRecord,
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
    LessonVideoHeartbeatPayload,
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
from app.services.badge_rules import (
    BadgeStats,
    badge_level,
    badge_ring_pct,
    badge_score,
    missing_requirements,
    quiz_mastery_pct,
)
from app.services.grades import grade_average_pct
from app.services.pedagogy_access import dashboard_type, guided_activity_available, learning_is_open, lesson_access, require_learning_open, session_ends_at, session_starts_at
from app.services.tenancy import TenantContext


VIDEO_COMPLETION_PCT = 80.0
VIDEO_HEARTBEAT_SEEK_TOLERANCE_SECONDS = 2.5
VIDEO_HEARTBEAT_MAX_GAP_SECONDS = 15.0
VIDEO_MAX_PLAYBACK_RATE = 2.0
BADGE_PASSING_QUIZ_PCT = 80.0


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
                LessonRecord.publication_status == "published",
            )
        ).all()
    )


def _completion_set(
    db: Session,
    tenant: TenantContext,
    enrollment_id: int,
    *,
    guided: bool = False,
) -> set[int]:
    completed = set(
        db.scalars(
            select(LessonProgressRecord.lesson_id).where(
                LessonProgressRecord.organization_id == tenant.organization_id,
                LessonProgressRecord.enrollment_id == enrollment_id,
            )
        ).all()
    )
    if not guided or not completed:
        return completed
    assignment_lessons = db.execute(
        select(LessonRecord.id, LessonRecord.assignment_id).where(
            LessonRecord.organization_id == tenant.organization_id,
            LessonRecord.id.in_(completed),
            LessonRecord.lesson_type == "assignment",
        )
    ).all()
    assignment_ids = {assignment_id for _, assignment_id in assignment_lessons if assignment_id is not None}
    submitted_ids = set(db.scalars(select(AssignmentSubmissionRecord.assignment_id).where(
        AssignmentSubmissionRecord.organization_id == tenant.organization_id,
        AssignmentSubmissionRecord.enrollment_id == enrollment_id,
        AssignmentSubmissionRecord.assignment_id.in_(assignment_ids),
    )).all()) if assignment_ids else set()
    completed.difference_update(
        lesson_id for lesson_id, assignment_id in assignment_lessons
        if assignment_id not in submitted_ids
    )
    return completed


def _lesson_progress(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> tuple[int, int, float]:
    lesson_ids = _lesson_ids_for_session(db, tenant, enrollment.session_id)
    session = get_session(db, tenant, enrollment.session_id)
    formation = formation_for_session(db, tenant, enrollment.session_id)
    if not learning_is_open(formation, session):
        return len(lesson_ids), 0, 0.0
    completed = _completion_set(db, tenant, enrollment.id, guided=dashboard_type(formation) == "guided")
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
        is_locked = not learning_is_open(formation, session)
        completed = _completion_set(db, tenant, enrollment.id, guided=dashboard_type(formation) == "guided")
        video_progress = {
            row.lesson_id: row.watched_pct
            for row in db.scalars(
                select(LessonVideoProgressRecord).where(
                    LessonVideoProgressRecord.organization_id == tenant.organization_id,
                    LessonVideoProgressRecord.enrollment_id == enrollment.id,
                )
            ).all()
        }
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
        def lesson_view(lesson: LessonRecord) -> LessonReaderRead:
            available_at, available = lesson_access(db, formation, session, lesson)
            locked = is_locked or not available
            resource = db.get(ResourceRecord, lesson.resource_id) if lesson.resource_id else None
            return LessonReaderRead(
                id=lesson.id,
                title=lesson.title,
                order_index=lesson.order_index,
                lesson_type=lesson.lesson_type,
                content=None if locked else lesson.content,
                video_url=None if locked else lesson.video_url,
                file_url=None if locked else (resource.url if resource else lesson.file_url),
                quiz_id=lesson.quiz_id,
                assignment_id=lesson.assignment_id,
                resource_id=lesson.resource_id,
                available_at=available_at,
                is_locked=locked,
                completed=not locked and lesson.id in completed,
                video_watched_pct=0 if locked else video_progress.get(lesson.id, 0),
            )
        result.append(
            LearningSessionRead(
                enrollment_id=enrollment.id,
                session_id=session.id,
                formation_id=formation.id,
                formation_title=formation.title,
                format_type=formation.format_type,
                dashboard_type=dashboard_type(formation),
                session_label=session.label,
                is_locked=is_locked,
                available_at=session_starts_at(session) if dashboard_type(formation) == "guided" else None,
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
                                    lesson_view(lesson)
                                    for lesson in chapter.lessons if lesson.publication_status == "published"
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


def _student_lesson_context(
    db: Session,
    tenant: TenantContext,
    lesson_id: int,
) -> tuple[LessonRecord, EnrollmentRecord]:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")

    row = db.execute(
        select(LessonRecord, CourseRecord)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            LessonRecord.id == lesson_id,
            LessonRecord.organization_id == tenant.organization_id,
            LessonRecord.publication_status == "published",
            CourseRecord.organization_id == tenant.organization_id,
            CourseRecord.status == "published",
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Leçon introuvable.")
    lesson, course = row
    enrollment = require_student_enrollment(db, tenant, course.session_id)
    session = get_session(db, tenant, course.session_id)
    formation = formation_for_session(db, tenant, course.session_id)
    require_learning_open(formation, session)
    if not lesson_access(db, formation, session, lesson)[1]:
        raise HTTPException(409, "Cette leçon n'est pas encore disponible.")
    return lesson, enrollment


def mark_lesson_complete(
    db: Session,
    tenant: TenantContext,
    lesson_id: int,
) -> LearningSessionRead:
    lesson, enrollment = _student_lesson_context(db, tenant, lesson_id)
    if lesson.lesson_type == "video":
        raise HTTPException(400, "Cette leçon vidéo se valide automatiquement après 80 % de lecture.")
    if lesson.lesson_type == "quiz" or lesson.quiz_id is not None:
        raise HTTPException(400, "Réussissez le quiz pour valider cette leçon.")
    if lesson.lesson_type == "assignment" or lesson.assignment_id is not None:
        raise HTTPException(400, "Déposez votre devoir pour valider cette leçon.")

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


def _merge_video_ranges(
    existing_ranges: list[object],
    start_seconds: float,
    end_seconds: float,
) -> list[list[float]]:
    ranges = [
        [float(item[0]), float(item[1])]
        for item in existing_ranges
        if isinstance(item, list)
        and len(item) == 2
        and all(isinstance(value, (int, float)) for value in item)
        and float(item[1]) > float(item[0])
    ]
    start, end = sorted((round(max(0.0, start_seconds), 3), round(max(0.0, end_seconds), 3)))
    if end > start:
        ranges.append([start, end])
    ranges.sort(key=lambda item: item[0])
    merged: list[list[float]] = []
    for current_start, current_end in ranges:
        if not merged or current_start > merged[-1][1] + 0.25:
            merged.append([current_start, current_end])
        else:
            merged[-1][1] = max(merged[-1][1], current_end)
    return [[round(start, 3), round(end, 3)] for start, end in merged]


def sync_lesson_video_progress(
    db: Session,
    tenant: TenantContext,
    lesson_id: int,
    payload: LessonVideoHeartbeatPayload,
    *,
    now: datetime | None = None,
) -> LearningSessionRead:
    lesson, enrollment = _student_lesson_context(db, tenant, lesson_id)
    if lesson.lesson_type != "video":
        raise HTTPException(400, "Le suivi vidéo ne s'applique qu'aux leçons vidéo.")

    current = now or datetime.now(UTC)
    db.execute(
        select(EnrollmentRecord.id)
        .where(
            EnrollmentRecord.id == enrollment.id,
            EnrollmentRecord.organization_id == tenant.organization_id,
        )
        .with_for_update()
    ).scalar_one()
    record = db.scalar(
        select(LessonVideoProgressRecord)
        .where(
            LessonVideoProgressRecord.organization_id == tenant.organization_id,
            LessonVideoProgressRecord.enrollment_id == enrollment.id,
            LessonVideoProgressRecord.lesson_id == lesson.id,
        )
        .with_for_update()
    )
    if record is None:
        record = LessonVideoProgressRecord(
            organization_id=tenant.organization_id,
            enrollment_id=enrollment.id,
            lesson_id=lesson.id,
            watched_ranges=[],
            watched_seconds=0,
            duration_seconds=0,
            watched_pct=0,
            last_position_seconds=0,
        )

    duration = max(payload.duration_seconds, record.duration_seconds or 0, 1.0)
    position = min(max(payload.current_time_seconds, 0.0), duration)
    record.duration_seconds = round(duration, 3)
    if payload.event != "seek":
        previous = max(record.last_position_seconds or 0.0, 0.0)
        last_heartbeat = record.last_heartbeat_at
        if last_heartbeat is not None:
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=UTC)
            elapsed = min(max((current - last_heartbeat).total_seconds(), 0.0), VIDEO_HEARTBEAT_MAX_GAP_SECONDS)
            delta = position - previous
            maximum = elapsed * min(payload.playback_rate, VIDEO_MAX_PLAYBACK_RATE) + VIDEO_HEARTBEAT_SEEK_TOLERANCE_SECONDS
            if 0 < delta <= maximum:
                record.watched_ranges = _merge_video_ranges(record.watched_ranges or [], previous, position)
                record.watched_seconds = round(sum(end - start for start, end in record.watched_ranges), 3)
                record.watched_pct = round(min(100.0, record.watched_seconds / duration * 100), 1)

    record.last_position_seconds = round(position, 3)
    record.last_heartbeat_at = current
    db.add(record)
    if (record.watched_pct or 0) >= VIDEO_COMPLETION_PCT:
        existing = db.scalar(
            select(LessonProgressRecord).where(
                LessonProgressRecord.organization_id == tenant.organization_id,
                LessonProgressRecord.enrollment_id == enrollment.id,
                LessonProgressRecord.lesson_id == lesson.id,
            )
        )
        if existing is None:
            db.add(LessonProgressRecord(
                organization_id=tenant.organization_id,
                enrollment_id=enrollment.id,
                lesson_id=lesson.id,
                completed_at=current,
            ))
    db.commit()
    return next(item for item in list_student_learning(db, tenant) if item.enrollment_id == enrollment.id)


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
        can_edit=day.teacher_id == tenant.user.id and not tenant.support_mode and day.report_submitted_at is None,
        delivery_status=day.delivery_status,
        report_submitted_at=day.report_submitted_at,
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
    if day.report_submitted_at is not None or day.status == "cancelled":
        raise HTTPException(409, "Les présences de cette séance sont clôturées.")

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
    assignments = [item for item in assignments if _linked_activity_is_published(db, tenant, "assignment", item.id)]
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
    *,
    badge: bool = False,
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
    quizzes = [item for item in quizzes if _linked_activity_is_published(db, tenant, "quiz", item.id)]
    if badge:
        quizzes = _guided_badge_quizzes(db, tenant, enrollment, quizzes)
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
            if best >= BADGE_PASSING_QUIZ_PCT:
                passed += 1
    average = round(sum(best_scores) / len(best_scores), 1) if best_scores else None
    return len(quizzes), attempted, passed, average


def _linked_activity_is_published(db: Session, tenant: TenantContext, kind: str, activity_id: int) -> bool:
    row = db.execute(
        select(LessonRecord.publication_status, CourseRecord.status)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            LessonRecord.organization_id == tenant.organization_id,
            getattr(LessonRecord, f"{kind}_id") == activity_id,
        )
    ).first()
    return row is None or (row[0] == "published" and row[1] == "published")


def _attendance_stats(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> tuple[int, int]:
    now = datetime.now(UTC)
    formation = formation_for_session(db, tenant, enrollment.session_id)
    guided = dashboard_type(formation) == "guided"
    query = select(SessionCourseDayRecord).where(
        SessionCourseDayRecord.organization_id == tenant.organization_id,
        SessionCourseDayRecord.session_id == enrollment.session_id,
        SessionCourseDayRecord.status != "cancelled",
        SessionCourseDayRecord.scheduled_at <= now,
    )
    if guided:
        query = query.where(
            SessionCourseDayRecord.report_submitted_at.is_not(None),
            SessionCourseDayRecord.delivery_status.in_(["held", "partial"]),
        )
    days = list(db.scalars(query).all())
    present = 0
    excused = 0
    for day in days:
        row = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.organization_id == tenant.organization_id,
                AttendanceRecord.course_day_id == day.id,
                AttendanceRecord.enrollment_id == enrollment.id,
            )
        )
        if row and row.status == "excused" and guided:
            excused += 1
            continue
        if row and row.status == "present":
            present += 1
    return len(days) - excused, present


def _course_day_work_excluded(day: SessionCourseDayRecord | None) -> bool:
    return day is not None and (
        day.status in {"cancelled", "not_held", "missed", "interrupted"}
        or day.delivery_status in {"not_held", "interrupted"}
    )


def _published_lessons(db: Session, tenant: TenantContext, session_id: int) -> list[LessonRecord]:
    return list(db.scalars(
        select(LessonRecord)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            CourseRecord.organization_id == tenant.organization_id,
            CourseRecord.session_id == session_id,
            CourseRecord.status == "published",
            LessonRecord.organization_id == tenant.organization_id,
            LessonRecord.publication_status == "published",
        )
    ).all())


def _lesson_course_day(db: Session, lesson: LessonRecord) -> SessionCourseDayRecord | None:
    activity = None
    if lesson.quiz_id is not None:
        activity = db.get(QuizRecord, lesson.quiz_id)
    elif lesson.assignment_id is not None:
        activity = db.get(AssignmentRecord, lesson.assignment_id)
    elif lesson.resource_id is not None:
        activity = db.get(ResourceRecord, lesson.resource_id)
    if activity is None or activity.course_day_id is None:
        return None
    return db.get(SessionCourseDayRecord, activity.course_day_id)


def _guided_badge_quizzes(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
    quizzes: list[QuizRecord],
) -> list[QuizRecord]:
    """Keep the quizzes that are open and are not already the proof of a content lesson."""
    formation = formation_for_session(db, tenant, enrollment.session_id)
    if dashboard_type(formation) != "guided":
        return quizzes
    session = get_session(db, tenant, enrollment.session_id)
    content_validation_ids = {
        lesson.quiz_id
        for lesson in _published_lessons(db, tenant, enrollment.session_id)
        if lesson.lesson_type in {"text", "pdf"} and lesson.quiz_id is not None
    }
    kept = []
    for quiz in quizzes:
        day = db.get(SessionCourseDayRecord, quiz.course_day_id) if quiz.course_day_id else None
        if (
            quiz.id not in content_validation_ids
            and not _course_day_work_excluded(day)
            and guided_activity_available(formation, session, scheduled_at=quiz.scheduled_at, day=day)
        ):
            kept.append(quiz)
    return kept


def _badge_lesson_progress(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
    formation: FormationRecord,
    session: FormationSessionRecord,
) -> tuple[int, int, float]:
    if dashboard_type(formation) != "guided":
        return _lesson_progress(db, tenant, enrollment)
    lesson_ids = {
        lesson.id
        for lesson in _published_lessons(db, tenant, session.id)
        if lesson.lesson_type not in {"quiz", "assignment"}
        and lesson_access(db, formation, session, lesson)[1]
        and not _course_day_work_excluded(_lesson_course_day(db, lesson))
    }
    completed = _completion_set(db, tenant, enrollment.id, guided=True) & lesson_ids
    pct = round(len(completed) / len(lesson_ids) * 100, 1) if lesson_ids else 0.0
    return len(lesson_ids), len(completed), pct


def _final_project_passed(submission: AssignmentSubmissionRecord | None) -> bool:
    return bool(
        submission is not None
        and submission.is_reviewed
        and submission.review_score is not None
        and submission.review_max_score > 0
        and submission.review_score / submission.review_max_score * 100 >= 80
    )


def _badge_assignment_stats(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
    formation: FormationRecord,
    session: FormationSessionRecord,
) -> tuple[int, int, int, bool, bool]:
    guided = dashboard_type(formation) == "guided"
    standard: list[AssignmentRecord] = []
    finals: list[AssignmentRecord] = []
    for assignment in db.scalars(select(AssignmentRecord).where(
        AssignmentRecord.organization_id == tenant.organization_id,
        AssignmentRecord.session_id == enrollment.session_id,
    )).all():
        if not _linked_activity_is_published(db, tenant, "assignment", assignment.id):
            continue
        day = db.get(SessionCourseDayRecord, assignment.course_day_id) if assignment.course_day_id else None
        if guided and (_course_day_work_excluded(day) or not guided_activity_available(formation, session, day=day)):
            continue
        (finals if assignment.is_final_project else standard).append(assignment)
    submissions = {
        item.assignment_id: item
        for item in db.scalars(select(AssignmentSubmissionRecord).where(
            AssignmentSubmissionRecord.organization_id == tenant.organization_id,
            AssignmentSubmissionRecord.enrollment_id == enrollment.id,
        )).all()
    }
    submitted = [item for item in standard if item.id in submissions]
    validated = [item for item in submitted if submissions[item.id].is_reviewed]
    final_valid = bool(finals) and all(_final_project_passed(submissions.get(item.id)) for item in finals)
    return len(standard), len(submitted), len(validated), bool(finals), final_valid


def badge_for_enrollment(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> BadgeRead:
    formation = formation_for_session(db, tenant, enrollment.session_id)
    session = get_session(db, tenant, enrollment.session_id)
    guided = dashboard_type(formation) == "guided"
    if guided and not learning_is_open(formation, session):
        return BadgeRead(
            level="aventurier",
            label=BADGE_LABELS["aventurier"],
            score_pct=0.0,
            next_level="debutant",
            lesson_progress_pct=0.0,
            assignment_progress_pct=None,
            quiz_progress_pct=None,
            attendance_pct=None,
            grade_average_pct=None,
            final_project_validated=False,
            missing_requirements=["Session non démarrée"],
        )
    total_lessons, completed_lessons, lesson_pct = _badge_lesson_progress(db, tenant, enrollment, formation, session)
    total_assignments, submitted_assignments, validated_assignments, has_final, final_valid = _badge_assignment_stats(
        db, tenant, enrollment, formation, session
    )
    total_quizzes, attempted_quizzes, passed_quizzes, _quiz_average = _quiz_stats(
        db, tenant, enrollment, badge=True
    )
    attendance_total, attendance_present = _attendance_stats(db, tenant, enrollment)
    grade_pct = grade_average_pct(
        db,
        organization_id=tenant.organization_id,
        enrollment_id=enrollment.id,
    )

    current = datetime.now(UTC)
    unresolved_days = guided and db.scalar(select(SessionCourseDayRecord.id).where(
        SessionCourseDayRecord.organization_id == tenant.organization_id,
        SessionCourseDayRecord.session_id == session.id,
        SessionCourseDayRecord.status != "cancelled",
        SessionCourseDayRecord.scheduled_at <= current,
        SessionCourseDayRecord.report_submitted_at.is_(None),
    )) is not None
    stats = BadgeStats(
        guided=guided,
        format_type=formation.format_type,
        total_lessons=total_lessons,
        completed_lessons=completed_lessons,
        lesson_progress_pct=lesson_pct,
        total_assignments=total_assignments,
        submitted_assignments=submitted_assignments,
        validated_assignments=validated_assignments,
        total_quizzes=total_quizzes,
        attempted_quizzes=attempted_quizzes,
        passed_quizzes=passed_quizzes,
        attendance_total=attendance_total,
        attendance_present=attendance_present,
        grade_average_pct=grade_pct,
        has_final_project=has_final,
        final_project_validated=final_valid,
        professional_eligible=not guided or (
            session.status != "cancelled" and current >= session_ends_at(session) and not unresolved_days
        ),
    )
    level = badge_level(stats)
    next_level = NEXT_BADGE.get(level)

    return BadgeRead(
        level=level,
        label=BADGE_LABELS[level],
        score_pct=badge_score(stats),
        next_level=next_level,
        lesson_progress_pct=lesson_pct,
        assignment_progress_pct=(
            round(submitted_assignments / total_assignments * 100, 1) if total_assignments else None
        ),
        quiz_progress_pct=quiz_mastery_pct(stats),
        attendance_pct=round(attendance_present / attendance_total * 100, 1) if attendance_total else None,
        grade_average_pct=grade_pct,
        final_project_validated=final_valid,
        missing_requirements=missing_requirements(next_level, stats) if next_level else [],
        ring_pct=badge_ring_pct(level, next_level, stats),
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
