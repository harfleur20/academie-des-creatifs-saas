from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    EnrollmentRecord,
    FormationSessionRecord,
    SessionTeacherRecord,
)
from app.schemas.workspace import (
    StudentSessionWorkspaceRead,
    StudentWorkspaceRead,
    TeacherSessionWorkspaceRead,
    TeacherWorkspaceRead,
)
from app.services.tenancy import TenantContext, require_organization_roles


def get_teacher_workspace(
    db: Session,
    tenant: TenantContext,
) -> TeacherWorkspaceRead:
    require_organization_roles(tenant, "teacher")

    assignments = list(
        db.scalars(
            select(SessionTeacherRecord)
            .options(
                selectinload(SessionTeacherRecord.session).selectinload(
                    FormationSessionRecord.formation
                ),
                selectinload(SessionTeacherRecord.session).selectinload(
                    FormationSessionRecord.enrollments
                ),
                selectinload(SessionTeacherRecord.session).selectinload(
                    FormationSessionRecord.courses
                ),
            )
            .where(
                SessionTeacherRecord.organization_id == tenant.organization_id,
                SessionTeacherRecord.teacher_id == tenant.user.id,
            )
            .order_by(SessionTeacherRecord.assigned_at.desc())
        ).all()
    )

    rows = [
        TeacherSessionWorkspaceRead(
            formation_id=item.session.formation_id,
            formation_title=item.session.formation.title,
            session_id=item.session.id,
            session_label=item.session.label,
            start_date=item.session.start_date,
            end_date=item.session.end_date,
            status=item.session.status,
            assignment_role=item.role,
            student_count=sum(
                1
                for enrollment in item.session.enrollments
                if enrollment.status in {"active", "completed"}
            ),
            course_count=sum(
                1
                for course in item.session.courses
                if course.status != "archived"
            ),
        )
        for item in assignments
        if item.session.status != "cancelled"
    ]

    return TeacherWorkspaceRead(
        sessions=rows,
        total_sessions=len(rows),
        total_students=sum(item.student_count for item in rows),
        total_courses=sum(item.course_count for item in rows),
    )


def get_student_workspace(
    db: Session,
    tenant: TenantContext,
) -> StudentWorkspaceRead:
    require_organization_roles(tenant, "student")

    enrollments = list(
        db.scalars(
            select(EnrollmentRecord)
            .options(
                selectinload(EnrollmentRecord.session).selectinload(
                    FormationSessionRecord.formation
                ),
                selectinload(EnrollmentRecord.session).selectinload(
                    FormationSessionRecord.courses
                ),
            )
            .where(
                EnrollmentRecord.organization_id == tenant.organization_id,
                EnrollmentRecord.student_id == tenant.user.id,
                EnrollmentRecord.status.in_(["active", "completed"]),
            )
            .order_by(EnrollmentRecord.created_at.desc())
        ).all()
    )

    rows = [
        StudentSessionWorkspaceRead(
            enrollment_id=item.id,
            formation_id=item.session.formation_id,
            formation_title=item.session.formation.title,
            session_id=item.session.id,
            session_label=item.session.label,
            start_date=item.session.start_date,
            end_date=item.session.end_date,
            session_status=item.session.status,
            enrollment_status=item.status,
            course_count=sum(
                1
                for course in item.session.courses
                if course.status != "archived"
            ),
        )
        for item in enrollments
        if item.session.status != "cancelled"
    ]

    return StudentWorkspaceRead(
        sessions=rows,
        total_sessions=len(rows),
        total_courses=sum(item.course_count for item in rows),
    )
