"""The read-only demo of the platform, on a demonstration school (docs/DEMO.md).

A visitor of the landing page opens the demo school's management, teacher or student space
without an account: they get a short access token for one of its members, marked as a demo
token. The server refuses every change made with it, and only lets it see that school.
The demo school's public site cannot take orders.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.entities import (
    EnrollmentRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.services.membership_roles import effective_member_roles

DEMO_SPACES = ("manage", "teacher", "student")
DEMO_TOKEN_MINUTES = 120
DEMO_READ_ONLY = "Mode démo : rien n’est enregistré. Créez votre école pour essayer pour de vrai."
DEMO_SITE_CLOSED = "Site de démonstration : les inscriptions et les paiements sont désactivés."
SPACE_ROLES = {"manage": "owner", "teacher": "teacher", "student": "student"}


def demo_organization(db: Session) -> OrganizationRecord | None:
    slug = settings.demo_organization_slug
    if not slug:
        return None
    return db.scalar(select(OrganizationRecord).where(
        OrganizationRecord.slug == slug,
        OrganizationRecord.is_active.is_(True),
    ))


def is_demo_organization(org: OrganizationRecord | None) -> bool:
    return bool(org is not None and settings.demo_organization_slug and org.slug == settings.demo_organization_slug)


def require_not_demo(org: OrganizationRecord) -> None:
    """The demo school's public site shows everything but takes no order nor favourite."""
    if is_demo_organization(org):
        raise HTTPException(status.HTTP_403_FORBIDDEN, DEMO_SITE_CLOSED)


def demo_member(db: Session, org: OrganizationRecord, space: str) -> UserRecord:
    """The member a visitor borrows for a space: the owner, the teacher with the most sessions, a student taking a session."""
    role = SPACE_ROLES.get(space)
    if role is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisissez l’espace direction, professeur ou étudiant.")
    members = db.scalars(select(OrganizationMemberRecord).where(
        OrganizationMemberRecord.organization_id == org.id,
        OrganizationMemberRecord.status == "active",
    ).order_by(OrganizationMemberRecord.id)).all()
    candidates = [member for member in members if role in effective_member_roles(member) and member.user.status == "active"]
    if space == "teacher":
        sessions = {member.user_id: len(db.scalars(select(SessionTeacherRecord.id).where(
            SessionTeacherRecord.organization_id == org.id, SessionTeacherRecord.teacher_id == member.user_id,
        )).all()) for member in candidates}
        candidates.sort(key=lambda member: -sessions[member.user_id])
    if space == "student":
        enrolled = set(db.scalars(select(EnrollmentRecord.student_id).where(
            EnrollmentRecord.organization_id == org.id, EnrollmentRecord.status == "active",
        )).all())
        candidates = [member for member in candidates if member.user_id in enrolled]
    if not candidates:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La démo n’est pas disponible pour le moment.")
    return candidates[0].user


def demo_token(user: UserRecord, org: OrganizationRecord) -> str:
    return create_access_token(
        user.id,
        minutes=DEMO_TOKEN_MINUTES,
        session_version=user.session_version,
        additional_claims={"demo_org": org.id},
    )
