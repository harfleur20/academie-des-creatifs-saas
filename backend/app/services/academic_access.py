from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
)
from app.services.tenancy import TenantContext


def get_session(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> FormationSessionRecord:
    session = db.scalar(
        select(FormationSessionRecord).where(
            FormationSessionRecord.id == session_id,
            FormationSessionRecord.organization_id == tenant.organization_id,
        )
    )
    if session is None:
        raise HTTPException(404, "Session introuvable.")
    return session


def teacher_assignment(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> SessionTeacherRecord | None:
    return db.scalar(
        select(SessionTeacherRecord).where(
            SessionTeacherRecord.organization_id == tenant.organization_id,
            SessionTeacherRecord.session_id == session_id,
            SessionTeacherRecord.teacher_id == tenant.user.id,
        )
    )


def require_teacher_assignment(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> SessionTeacherRecord:
    if not tenant.has_role("teacher"):
        raise HTTPException(403, "Accès professeur requis.")
    assignment = teacher_assignment(db, tenant, session_id)
    if assignment is None:
        raise HTTPException(403, "Cette session ne vous est pas affectée.")
    return assignment


def _ensure_student_access_active(db: Session, tenant: TenantContext) -> None:
    from app.models.entities import OrganizationStudentProfileRecord
    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == tenant.organization_id,
            OrganizationStudentProfileRecord.user_id == tenant.user.id,
        )
    )
    if profile is not None and profile.access_status == "suspended":
        raise HTTPException(
            402,
            profile.access_suspended_reason
            or "Votre accès pédagogique est suspendu en attente de régularisation.",
        )


def student_enrollment(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> EnrollmentRecord | None:
    return db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.session_id == session_id,
            EnrollmentRecord.student_id == tenant.user.id,
            EnrollmentRecord.status.in_(["active", "completed"]),
        )
    )


def require_student_enrollment(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> EnrollmentRecord:
    if not tenant.has_role("student"):
        raise HTTPException(403, "Accès étudiant requis.")
    _ensure_student_access_active(db, tenant)
    enrollment = student_enrollment(db, tenant, session_id)
    if enrollment is None:
        raise HTTPException(403, "Vous n'êtes pas inscrit à cette session.")
    return enrollment


def formation_for_session(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> FormationRecord:
    formation = db.scalar(
        select(FormationRecord)
        .join(FormationSessionRecord, FormationSessionRecord.formation_id == FormationRecord.id)
        .where(
            FormationSessionRecord.id == session_id,
            FormationSessionRecord.organization_id == tenant.organization_id,
            FormationRecord.organization_id == tenant.organization_id,
        )
    )
    if formation is None:
        raise HTTPException(404, "Formation introuvable.")
    return formation


def require_owned_course_day(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    course_day_id: int | None,
) -> SessionCourseDayRecord | None:
    if course_day_id is None:
        return None
    day = db.scalar(
        select(SessionCourseDayRecord).where(
            SessionCourseDayRecord.id == course_day_id,
            SessionCourseDayRecord.organization_id == tenant.organization_id,
            SessionCourseDayRecord.session_id == session_id,
        )
    )
    if day is None:
        raise HTTPException(422, "Le créneau ne correspond pas à cette session.")
    if day.teacher_id != tenant.user.id:
        raise HTTPException(
            403,
            "Vous ne pouvez rattacher ce contenu qu'à l'un de vos propres créneaux.",
        )
    return day


def can_view_session(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> bool:
    if tenant.organization_roles.intersection({"owner", "admin", "manager", "super_admin"}):
        return True
    if tenant.has_role("teacher") and teacher_assignment(db, tenant, session_id):
        return True
    if tenant.has_role("student") and student_enrollment(db, tenant, session_id):
        try:
            _ensure_student_access_active(db, tenant)
        except HTTPException:
            return False
        return True
    return False


def require_session_view(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> None:
    get_session(db, tenant, session_id)
    if not can_view_session(db, tenant, session_id):
        raise HTTPException(403, "Vous n'avez pas accès à cette session.")
