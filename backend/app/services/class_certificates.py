from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    CertificateRecord,
    ClassDiscussionPostRecord,
    ClassDiscussionReplyRecord,
    EnrollmentRecord,
    OrganizationStudentProfileRecord,
    UserRecord,
)
from app.schemas.academic import (
    CertificateEligibilityRead,
    CertificateRead,
    ClassmateRead,
    DiscussionAuthorRead,
    DiscussionCreate,
    DiscussionPostRead,
    DiscussionReplyRead,
    StudentClassRead,
)
from app.services.academic_access import (
    can_view_session,
    formation_for_session,
    get_session,
    require_student_enrollment,
)
from app.services.learning_progress import badge_for_enrollment, progress_for_enrollment
from app.services.school_branding import branding_snapshot
from app.services.tenancy import TenantContext


def _role_for_context(tenant: TenantContext) -> str:
    if tenant.has_role("teacher"):
        return "teacher"
    if tenant.has_role("student"):
        return "student"
    return "admin"


def _author(
    db: Session,
    tenant: TenantContext,
    user_id: int,
    role: str,
) -> DiscussionAuthorRead:
    user = db.get(UserRecord, user_id)
    return DiscussionAuthorRead(
        user_id=user_id,
        full_name=user.full_name if user else "Utilisateur",
        role=role,
        is_current_user=user_id == tenant.user.id,
    )


def list_student_classes(
    db: Session,
    tenant: TenantContext,
) -> list[StudentClassRead]:
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
    result: list[StudentClassRead] = []
    for own in enrollments:
        session = get_session(db, tenant, own.session_id)
        formation = formation_for_session(db, tenant, own.session_id)
        classmates = list(
            db.scalars(
                select(EnrollmentRecord).where(
                    EnrollmentRecord.organization_id == tenant.organization_id,
                    EnrollmentRecord.session_id == own.session_id,
                    EnrollmentRecord.status.in_(["active", "completed"]),
                )
            ).all()
        )
        result.append(
            StudentClassRead(
                session_id=session.id,
                formation_title=formation.title,
                session_label=session.label,
                classmates=[
                    ClassmateRead(
                        user_id=row.student_id,
                        enrollment_id=row.id,
                        full_name=(
                            db.get(UserRecord, row.student_id).full_name
                            if db.get(UserRecord, row.student_id)
                            else "Étudiant"
                        ),
                        is_current_user=row.student_id == tenant.user.id,
                        badge=badge_for_enrollment(db, tenant, row),
                    )
                    for row in classmates
                ],
            )
        )
    return result


def _reply_view(
    db: Session,
    tenant: TenantContext,
    row: ClassDiscussionReplyRecord,
) -> DiscussionReplyRead:
    return DiscussionReplyRead(
        id=row.id,
        author=_author(db, tenant, row.author_user_id, row.author_role),
        body=row.body,
        image_url=row.image_url,
        created_at=row.created_at,
    )


def discussion_posts(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> list[DiscussionPostRead]:
    if not can_view_session(db, tenant, session_id):
        raise HTTPException(403, "Vous n'avez pas accès à cette classe.")

    posts = list(
        db.scalars(
            select(ClassDiscussionPostRecord)
            .where(
                ClassDiscussionPostRecord.organization_id == tenant.organization_id,
                ClassDiscussionPostRecord.session_id == session_id,
            )
            .order_by(ClassDiscussionPostRecord.created_at.desc())
        ).all()
    )
    result: list[DiscussionPostRead] = []
    for post in posts:
        replies = list(
            db.scalars(
                select(ClassDiscussionReplyRecord)
                .where(
                    ClassDiscussionReplyRecord.organization_id == tenant.organization_id,
                    ClassDiscussionReplyRecord.post_id == post.id,
                )
                .order_by(ClassDiscussionReplyRecord.created_at)
            ).all()
        )
        result.append(
            DiscussionPostRead(
                id=post.id,
                author=_author(db, tenant, post.author_user_id, post.author_role),
                body=post.body,
                image_url=post.image_url,
                created_at=post.created_at,
                replies=[_reply_view(db, tenant, item) for item in replies],
            )
        )
    return result


def create_discussion_post(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    payload: DiscussionCreate,
) -> DiscussionPostRead:
    if not can_view_session(db, tenant, session_id):
        raise HTTPException(403, "Vous n'avez pas accès à cette classe.")
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")

    row = ClassDiscussionPostRecord(
        organization_id=tenant.organization_id,
        session_id=session_id,
        author_user_id=tenant.user.id,
        author_role=_role_for_context(tenant),
        body=payload.body.strip(),
        image_url=payload.image_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return next(
        item
        for item in discussion_posts(db, tenant, session_id)
        if item.id == row.id
    )


def create_discussion_reply(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    post_id: int,
    payload: DiscussionCreate,
) -> DiscussionReplyRead:
    if not can_view_session(db, tenant, session_id):
        raise HTTPException(403, "Vous n'avez pas accès à cette classe.")
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")

    post = db.scalar(
        select(ClassDiscussionPostRecord).where(
            ClassDiscussionPostRecord.id == post_id,
            ClassDiscussionPostRecord.organization_id == tenant.organization_id,
            ClassDiscussionPostRecord.session_id == session_id,
        )
    )
    if post is None:
        raise HTTPException(404, "Publication introuvable.")

    row = ClassDiscussionReplyRecord(
        organization_id=tenant.organization_id,
        post_id=post.id,
        author_user_id=tenant.user.id,
        author_role=_role_for_context(tenant),
        body=payload.body.strip(),
        image_url=payload.image_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _reply_view(db, tenant, row)


def delete_discussion_post(
    db: Session,
    tenant: TenantContext,
    session_id: int,
    post_id: int,
) -> None:
    post = db.scalar(
        select(ClassDiscussionPostRecord).where(
            ClassDiscussionPostRecord.id == post_id,
            ClassDiscussionPostRecord.organization_id == tenant.organization_id,
            ClassDiscussionPostRecord.session_id == session_id,
        )
    )
    if post is None:
        raise HTTPException(404, "Publication introuvable.")
    if post.author_user_id != tenant.user.id:
        raise HTTPException(403, "Vous ne pouvez supprimer que vos publications.")
    db.delete(post)
    db.commit()


def _certificate_number(
    enrollment_id: int,
    issued_at: datetime,
    prefix: str = "AC",
) -> str:
    message = f"saas-certificate:{enrollment_id}".encode()
    digest = hmac.new(
        settings.jwt_secret_key.encode(),
        message,
        hashlib.sha256,
    ).digest()
    token = base64.b32encode(digest).decode("ascii").rstrip("=")[:12]
    safe_prefix = "".join(ch for ch in prefix.upper() if ch.isalnum())[:8] or "AC"
    return f"{safe_prefix}-CERT-{issued_at.year}-{token[:4]}-{token[4:8]}-{token[8:12]}"


def _verification_token(certificate: CertificateRecord) -> str:
    message = (
        f"certificate:{certificate.id}:{certificate.certificate_number}"
    ).encode()
    digest = hmac.new(
        settings.jwt_secret_key.encode(),
        message,
        hashlib.sha256,
    ).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{certificate.id}.{signature}"


def _certificate_view(certificate: CertificateRecord) -> CertificateRead:
    return CertificateRead(
        enrollment_id=certificate.enrollment_id,
        certificate_number=certificate.certificate_number,
        student_name=certificate.student_name,
        formation_title=certificate.formation_title,
        issued_at=certificate.issued_at,
        status=certificate.status,
        verification_token=_verification_token(certificate),
    )


def _certificate_reason(
    db: Session,
    tenant: TenantContext,
    enrollment: EnrollmentRecord,
) -> str | None:
    session = get_session(db, tenant, enrollment.session_id)
    progress = progress_for_enrollment(db, tenant, enrollment)

    if session.status == "cancelled":
        return "La session a été annulée."
    if date.today() <= session.end_date and session.status != "completed":
        return "Le certificat sera disponible après la fin de la session."
    if progress.total_lessons <= 0:
        return "Le parcours ne contient encore aucune leçon validable."
    if progress.lesson_progress_pct < 100:
        return "Toutes les leçons doivent être terminées."
    if progress.total_assignments and progress.submitted_assignments < progress.total_assignments:
        return "Tous les devoirs doivent être remis."
    if progress.total_quizzes and progress.attempted_quizzes < progress.total_quizzes:
        return "Toutes les évaluations doivent être réalisées."
    if progress.badge.level != "professionnel":
        return "Le parcours doit atteindre le niveau Professionnel pour être validé."
    return None


def certificate_eligibility(
    db: Session,
    tenant: TenantContext,
    enrollment_id: int,
) -> CertificateEligibilityRead:
    enrollment = db.scalar(
        select(EnrollmentRecord).where(
            EnrollmentRecord.id == enrollment_id,
            EnrollmentRecord.organization_id == tenant.organization_id,
            EnrollmentRecord.student_id == tenant.user.id,
        )
    )
    if enrollment is None:
        raise HTTPException(404, "Inscription introuvable.")

    existing = db.scalar(
        select(CertificateRecord).where(
            CertificateRecord.organization_id == tenant.organization_id,
            CertificateRecord.enrollment_id == enrollment.id,
        )
    )
    if existing:
        return CertificateEligibilityRead(
            enrollment_id=enrollment.id,
            eligible=True,
            reason=None,
            certificate=_certificate_view(existing),
        )

    reason = _certificate_reason(db, tenant, enrollment)
    return CertificateEligibilityRead(
        enrollment_id=enrollment.id,
        eligible=reason is None,
        reason=reason,
        certificate=None,
    )


def issue_certificate(
    db: Session,
    tenant: TenantContext,
    enrollment_id: int,
) -> CertificateRead:
    eligibility = certificate_eligibility(db, tenant, enrollment_id)
    if eligibility.certificate:
        return eligibility.certificate
    if not eligibility.eligible:
        raise HTTPException(409, eligibility.reason or "Parcours non validé.")

    enrollment = db.get(EnrollmentRecord, enrollment_id)
    student = db.get(UserRecord, enrollment.student_id)
    formation = formation_for_session(db, tenant, enrollment.session_id)
    issued_at = datetime.now(UTC)
    session = get_session(db, tenant, enrollment.session_id)
    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == tenant.organization_id,
            OrganizationStudentProfileRecord.user_id == enrollment.student_id,
        )
    )
    snapshot = branding_snapshot(db, tenant.organization)
    snapshot["document"] = {
        "student_code": profile.student_code if profile else None,
        "session_label": session.label,
        "session_start_date": session.start_date.isoformat(),
        "session_end_date": session.end_date.isoformat(),
        "training_hours": formation.training_hours,
    }
    prefix = str(snapshot.get("student_code_prefix") or "AC")
    row = CertificateRecord(
        organization_id=tenant.organization_id,
        enrollment_id=enrollment.id,
        certificate_number=_certificate_number(enrollment.id, issued_at, prefix),
        student_name=student.full_name if student else "Étudiant",
        formation_title=formation.title,
        issued_at=issued_at,
        status="valid",
        branding_snapshot=snapshot,
    )
    enrollment.status = "completed"
    db.add(row)
    db.commit()
    db.refresh(row)
    return _certificate_view(row)


def verify_certificate_token(
    db: Session,
    token: str,
) -> CertificateRead:
    try:
        certificate_id_text, signature = token.split(".", 1)
        certificate_id = int(certificate_id_text)
    except (ValueError, TypeError):
        raise HTTPException(404, "Certificat introuvable.")

    row = db.get(CertificateRecord, certificate_id)
    if row is None or row.status != "valid":
        raise HTTPException(404, "Certificat introuvable.")
    expected = _verification_token(row)
    if not hmac.compare_digest(expected, token):
        raise HTTPException(404, "Certificat introuvable.")
    return _certificate_view(row)
