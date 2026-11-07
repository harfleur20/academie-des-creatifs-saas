from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationStudentProfileRecord,
    OrganizationTeacherProfileRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.academic import (
    SchoolPedagogyOverviewRead,
    SchoolPedagogySessionRead,
    SchoolPedagogyStudentRead,
    SchoolTeacherPerformanceRead,
)
from app.services.learning_progress import progress_for_enrollment
from app.services.tenancy import TenantContext


VISIBLE_ENROLLMENT_STATUSES = ("active", "completed", "suspended_payment")


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _student_row(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> SchoolPedagogyStudentRead:
    student = db.get(UserRecord, enrollment.student_id)
    session = db.get(FormationSessionRecord, enrollment.session_id)
    formation = db.get(FormationRecord, session.formation_id) if session else None
    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == tenant.organization_id,
            OrganizationStudentProfileRecord.user_id == enrollment.student_id,
        )
    )
    progress = progress_for_enrollment(db, tenant, enrollment)
    attendance_pct = progress.badge.attendance_pct
    reasons: list[str] = []
    danger = False

    if enrollment.status == "suspended_payment":
        reasons.append("Accès suspendu pour impayé")
        danger = True

    if (
        attendance_pct is not None
        and progress.attendance_total >= 2
        and attendance_pct < 70
    ):
        reasons.append(f"Présence faible ({attendance_pct:.0f} %)")
        if attendance_pct < 50:
            danger = True

    if (
        progress.grade_average_pct is not None
        and progress.grade_average_pct < 50
    ):
        reasons.append(
            f"Résultats faibles ({progress.grade_average_pct:.0f} %)"
        )
        if progress.grade_average_pct < 40:
            danger = True

    if session and session.start_date < date.today() and session.end_date > session.start_date:
        elapsed_days = max(0, (date.today() - session.start_date).days)
        total_days = max(1, (session.end_date - session.start_date).days)
        elapsed_pct = min(100.0, (elapsed_days / total_days) * 100)
        if elapsed_pct >= 25 and progress.badge.score_pct < 35:
            reasons.append("Progression en retard sur la session")

    overdue_assignments = list(
        db.scalars(
            select(AssignmentRecord).where(
                AssignmentRecord.organization_id == tenant.organization_id,
                AssignmentRecord.session_id == enrollment.session_id,
                AssignmentRecord.publication_status == "published",
                AssignmentRecord.due_date < datetime.now(UTC),
            )
        ).all()
    )
    missing_overdue = 0
    for assignment in overdue_assignments:
        submission = db.scalar(
            select(AssignmentSubmissionRecord.id).where(
                AssignmentSubmissionRecord.organization_id == tenant.organization_id,
                AssignmentSubmissionRecord.assignment_id == assignment.id,
                AssignmentSubmissionRecord.enrollment_id == enrollment.id,
            )
        )
        if submission is None:
            missing_overdue += 1
    if missing_overdue:
        reasons.append(
            f"{missing_overdue} devoir(s) en retard"
        )

    alert_level = "danger" if danger else "warning" if reasons else "good"
    return SchoolPedagogyStudentRead(
        enrollment_id=enrollment.id,
        session_id=enrollment.session_id,
        student_id=enrollment.student_id,
        student_name=student.full_name if student else "Étudiant",
        student_code=profile.student_code if profile else None,
        formation_title=formation.title if formation else "Formation",
        session_label=session.label if session else "Session",
        enrollment_status=enrollment.status,
        progress_pct=progress.badge.score_pct,
        attendance_pct=attendance_pct,
        grade_average_pct=progress.grade_average_pct,
        submitted_assignments=progress.submitted_assignments,
        total_assignments=progress.total_assignments,
        attempted_quizzes=progress.attempted_quizzes,
        total_quizzes=progress.total_quizzes,
        alert_level=alert_level,
        alert_reasons=reasons,
    )


def school_pedagogy_overview(
    db: Session,
    tenant: TenantContext,
) -> SchoolPedagogyOverviewRead:
    enrollments = list(
        db.scalars(
            select(EnrollmentRecord).where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.status.in_(VISIBLE_ENROLLMENT_STATUSES),
            )
        ).all()
    )
    student_rows = [
        _student_row(db, tenant, enrollment)
        for enrollment in enrollments
    ]

    sessions = list(
        db.scalars(
            select(FormationSessionRecord).where(
                FormationSessionRecord.organization_id == tenant.organization_id,
                FormationSessionRecord.status != "cancelled",
            ).order_by(FormationSessionRecord.start_date.desc())
        ).all()
    )
    session_rows: list[SchoolPedagogySessionRead] = []
    pending_total = 0

    for session in sessions:
        formation = db.get(FormationRecord, session.formation_id)
        rows = [
            row
            for row in student_rows
            if row.session_id == session.id
        ]
        session_enrollment_ids = [
            enrollment.id
            for enrollment in enrollments
            if enrollment.session_id == session.id
        ]
        assignment_ids = list(
            db.scalars(
                select(AssignmentRecord.id).where(
                    AssignmentRecord.organization_id == tenant.organization_id,
                    AssignmentRecord.session_id == session.id,
                )
            ).all()
        )
        pending = 0
        if assignment_ids and session_enrollment_ids:
            pending = int(
                db.scalar(
                    select(func.count(AssignmentSubmissionRecord.id)).where(
                        AssignmentSubmissionRecord.organization_id == tenant.organization_id,
                        AssignmentSubmissionRecord.assignment_id.in_(assignment_ids),
                        AssignmentSubmissionRecord.enrollment_id.in_(session_enrollment_ids),
                        AssignmentSubmissionRecord.is_reviewed.is_(False),
                    )
                )
                or 0
            )
        pending_total += pending
        attendance_values = [
            row.attendance_pct
            for row in rows
            if row.attendance_pct is not None
        ]
        capacity = session.seat_capacity or 0
        fill = (
            round((len(rows) / capacity) * 100, 1)
            if capacity > 0
            else 0.0
        )
        session_rows.append(
            SchoolPedagogySessionRead(
                session_id=session.id,
                formation_title=formation.title if formation else "Formation",
                session_label=session.label,
                status=session.status,
                enrolled_count=len(rows),
                seat_capacity=capacity,
                fill_rate_pct=fill,
                progress_pct=_average([row.progress_pct for row in rows]) or 0.0,
                attendance_rate_pct=_average(attendance_values),
                pending_reviews_count=pending,
                at_risk_count=sum(
                    1 for row in rows if row.alert_level != "good"
                ),
            )
        )

    teacher_assignments = list(
        db.scalars(
            select(SessionTeacherRecord).where(
                SessionTeacherRecord.organization_id == tenant.organization_id,
            )
        ).all()
    )
    teacher_ids = sorted({row.teacher_id for row in teacher_assignments})
    teacher_rows: list[SchoolTeacherPerformanceRead] = []
    for teacher_id in teacher_ids:
        teacher = db.get(UserRecord, teacher_id)
        profile = db.scalar(
            select(OrganizationTeacherProfileRecord).where(
                OrganizationTeacherProfileRecord.organization_id == tenant.organization_id,
                OrganizationTeacherProfileRecord.user_id == teacher_id,
            )
        )
        session_ids = {
            row.session_id
            for row in teacher_assignments
            if row.teacher_id == teacher_id
        }
        teacher_students = [
            row
            for row in student_rows
            if row.session_id in session_ids
        ]
        attendance_values = [
            row.attendance_pct
            for row in teacher_students
            if row.attendance_pct is not None
        ]
        assignment_ids = list(
            db.scalars(
                select(AssignmentRecord.id).where(
                    AssignmentRecord.organization_id == tenant.organization_id,
                    AssignmentRecord.teacher_id == teacher_id,
                )
            ).all()
        )
        pending = 0
        if assignment_ids:
            pending = int(
                db.scalar(
                    select(func.count(AssignmentSubmissionRecord.id)).where(
                        AssignmentSubmissionRecord.organization_id == tenant.organization_id,
                        AssignmentSubmissionRecord.assignment_id.in_(assignment_ids),
                        AssignmentSubmissionRecord.is_reviewed.is_(False),
                    )
                )
                or 0
            )
        teacher_rows.append(
            SchoolTeacherPerformanceRead(
                teacher_id=teacher_id,
                teacher_name=teacher.full_name if teacher else "Professeur",
                teacher_code=profile.teacher_code if profile else None,
                sessions_count=len(session_ids),
                students_count=len({row.student_id for row in teacher_students}),
                progress_pct=_average(
                    [row.progress_pct for row in teacher_students]
                ) or 0.0,
                attendance_rate_pct=_average(attendance_values),
                pending_reviews_count=pending,
            )
        )

    attendance_values = [
        row.attendance_pct
        for row in student_rows
        if row.attendance_pct is not None
    ]
    active_sessions = sum(
        1 for session in sessions if session.status in {"planned", "open"}
    )
    active_students = len({
        row.student_id
        for row in student_rows
        if row.enrollment_status in {"active", "suspended_payment"}
    })

    return SchoolPedagogyOverviewRead(
        generated_at=datetime.now(UTC),
        active_students=active_students,
        active_sessions=active_sessions,
        average_progress_pct=_average(
            [row.progress_pct for row in student_rows]
        ) or 0.0,
        average_attendance_pct=_average(attendance_values),
        at_risk_students=sum(
            1 for row in student_rows if row.alert_level != "good"
        ),
        pending_reviews_count=pending_total,
        students=student_rows,
        sessions=session_rows,
        teachers=teacher_rows,
    )
