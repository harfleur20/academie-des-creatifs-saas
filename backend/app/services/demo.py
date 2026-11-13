"""The read-only demo of the platform, on a demonstration school (docs/DEMO.md).

A visitor of the landing page opens the demo school's management, teacher or student space
without an account: they get a short access token for one of its members, marked as a demo
token. The server refuses every change made with it, only lets it see that school, and
only opens the screens of the demo tour (DEMO_ALLOWED_READS): the others are "available
once you create your school". Nothing a demo request does is kept, and tokens and PDFs
are rate limited per visitor. The demo school's public site cannot take orders.
"""

import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimit
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
DEMO_LOCKED = "Cet écran n’est pas ouvert dans la démo. Il est disponible quand vous créez votre école."
DEMO_TOO_MANY = "Trop de demandes pour la démo en peu de temps. Réessayez dans quelques minutes."

# The reads the screens of the demo tour need (frontend/src/lib/demo.ts: DEMO_OPEN_SCREENS),
# relative to the API prefix. A demo token reads nothing else.
DEMO_ALLOWED_READS = tuple(re.compile(pattern) for pattern in (
    # Every space: the session, the school, the top bar.
    r"/auth/(me|demo|sso/config)",
    r"/organizations(/current/access-profile|/resolve-host)?",
    r"/branding/current",
    r"/billing/(plans|subscription)",
    r"/notifications",
    r"/messages/(threads|ws-ticket)",
    r"/onboarding/status",
    r"/workspace/(student|teacher)",
    r"/workspace-onboarding/(charters/(student|teacher)|teacher-profile)",
    r"/public/.+",
    r"/commerce/public/.+",
    # Management: dashboard, formations, pedagogical follow-up, statistics, sales.
    r"/academic/manage/overview",
    r"/formations(/\d+)?",
    r"/organizations/current/members",
    r"/planning/reports",
    r"/commerce/(dashboard|orders|invoices|invoices/\d+/pdf|communications/needs-review)",
    # Teacher: dashboard, sessions and their planning, students, grades.
    r"/academic/teacher/(performance|sessions/\d+/grades)",
    r"/planning/sessions/\d+/course-days",
    r"/planning/course-days/\d+/feedback",
    r"/live-recordings/sessions/\d+",
    # Student: overview, journey, courses, planning, results.
    r"/academic/student/(attendance|classes|grades|learning|progress|quizzes|resources)",
    r"/academic/classes/\d+/discussion",
    r"/assignments/student",
    # Transcripts: the student's results, the follow-up, the teacher's students.
    r"/transcripts/(mine|\d+|\d+/pdf)",
))
# Per visitor address: opening a space hands out a token, a PDF is built on the server.
DEMO_TOKEN_LIMIT = SlidingWindowLimit(40, 3600)
DEMO_PDF_LIMIT = SlidingWindowLimit(20, 600)


def demo_may_read(path: str) -> bool:
    """Whether a demo token may read this API path (without the API prefix)."""
    return any(pattern.fullmatch(path) for pattern in DEMO_ALLOWED_READS)


def demo_rate_limited(limit: SlidingWindowLimit, visitor: str) -> None:
    if not limit.allow(visitor):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, {"code": "demo_rate_limited", "message": DEMO_TOO_MANY})
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
