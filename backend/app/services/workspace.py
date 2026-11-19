from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    EnrollmentRecord,
    FormationSessionRecord,
    OrganizationStudentProfileRecord,
    SessionTeacherRecord,
)
from app.schemas.workspace import (
    StudentSessionWorkspaceRead,
    StudentWorkspaceRead,
    TeacherSessionWorkspaceRead,
    TeacherWorkspaceRead,
)
from app.services.pedagogy_access import dashboard_type
from app.services.school_profiles import ensure_student_profile, ensure_teacher_profile
from app.services.school_setup import confirmed_matricule_prefix
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
            formation_image=item.session.formation.cover_image_url,
            format_type=item.session.formation.format_type,
            session_id=item.session.id,
            session_label=item.session.label,
            start_date=item.session.start_date,
            end_date=item.session.end_date,
            campus_label=item.session.campus_label,
            seat_capacity=item.session.seat_capacity,
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

    teacher_profile = ensure_teacher_profile(db, tenant.organization, tenant.user.id)
    db.commit()
    return TeacherWorkspaceRead(
        teacher_code=teacher_profile.teacher_code,
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
                selectinload(EnrollmentRecord.session)
                .selectinload(FormationSessionRecord.teachers)
                .selectinload(SessionTeacherRecord.teacher),
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
            formation_image=item.session.formation.cover_image_url,
            format_type=item.session.formation.format_type,
            dashboard_type=dashboard_type(item.session.formation),
            session_id=item.session.id,
            session_label=item.session.label,
            start_date=item.session.start_date,
            end_date=item.session.end_date,
            teacher_name=next(
                (assignment.teacher.full_name for assignment in sorted(
                    item.session.teachers,
                    key=lambda assignment: (assignment.role != "principal", assignment.id),
                )),
                None,
            ),
            teacher_avatar_url=next(
                (assignment.teacher.avatar_url for assignment in sorted(
                    item.session.teachers,
                    key=lambda assignment: (assignment.role != "principal", assignment.id),
                )),
                None,
            ),
            campus_label=item.session.campus_label,
            session_status=item.session.status,
            enrollment_status=item.status,
            course_count=sum(
                1
                for course in item.session.courses
                if course.status == "published"
            ),
        )
        for item in enrollments
        if item.session.status != "cancelled"
    ]

    student_profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == tenant.organization_id,
            OrganizationStudentProfileRecord.user_id == tenant.user.id,
        )
    )
    if student_profile is None and confirmed_matricule_prefix(db, tenant.organization_id):
        student_profile = ensure_student_profile(db, tenant.organization, tenant.user.id)
        db.commit()
    return StudentWorkspaceRead(
        student_code=student_profile.student_code if student_profile else None,
        sessions=rows,
        total_sessions=len(rows),
        total_courses=sum(item.course_count for item in rows),
    )
