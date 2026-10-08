from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    OrganizationTeacherProfileRecord,
)

from app.services.school_branding import get_or_create_identity_records
from app.services.school_setup import require_confirmed_matricule_prefix


def ensure_student_profile(
    db: Session,
    organization: OrganizationRecord,
    user_id: int,
    *,
    first_purchase_at: datetime | None = None,
) -> OrganizationStudentProfileRecord:
    profile_query = select(OrganizationStudentProfileRecord).where(
        OrganizationStudentProfileRecord.organization_id == organization.id,
        OrganizationStudentProfileRecord.user_id == user_id,
    )
    existing = db.scalar(profile_query)
    if existing:
        if first_purchase_at and existing.first_purchase_at is None:
            existing.first_purchase_at = first_purchase_at
        return existing

    # The identity row serializes code allocation for this school on PostgreSQL.
    get_or_create_identity_records(db, organization)
    site = db.scalar(
        select(OrganizationPublicSiteRecord)
        .where(OrganizationPublicSiteRecord.organization_id == organization.id)
        .with_for_update()
    )
    if site is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Identité de l'école introuvable pour générer le matricule.")
    if not site.student_code_prefix.strip() or not site.student_code_prefix_confirmed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "Confirmez le préfixe des matricules avant d'inscrire un étudiant.")

    # A concurrent request may have created the profile while waiting for the lock.
    existing = db.scalar(profile_query)
    if existing:
        if first_purchase_at and existing.first_purchase_at is None:
            existing.first_purchase_at = first_purchase_at
        return existing

    now = datetime.now(UTC)
    sequence_year = now.year
    base = f"{site.student_code_prefix.upper()[:8]}{now:%y}-"
    persisted_sequence = site.student_code_sequence if site.student_code_sequence_year == sequence_year else 0
    existing_codes = db.scalars(
        select(OrganizationStudentProfileRecord.student_code).where(
            OrganizationStudentProfileRecord.organization_id == organization.id,
            OrganizationStudentProfileRecord.student_code.like(f"{base}%"),
        )
    ).all()
    highest_existing = max(
        (int(code[len(base):]) for code in existing_codes if code[len(base):].isdigit()),
        default=0,
    )
    next_number = max(persisted_sequence, highest_existing) + 1
    if next_number > 999_999:
        raise HTTPException(status.HTTP_409_CONFLICT, "La séquence de matricules de cette école est épuisée.")

    site.student_code_sequence_year = sequence_year
    site.student_code_sequence = next_number
    profile = OrganizationStudentProfileRecord(
        organization_id=organization.id,
        user_id=user_id,
        student_code=f"{base}{next_number:03d}",
        status="active",
        first_purchase_at=first_purchase_at,
    )
    db.add(profile)
    db.flush()
    return profile


def ensure_teacher_profile(
    db: Session,
    organization: OrganizationRecord,
    user_id: int,
) -> OrganizationTeacherProfileRecord:
    existing = db.scalar(
        select(OrganizationTeacherProfileRecord).where(
            OrganizationTeacherProfileRecord.organization_id == organization.id,
            OrganizationTeacherProfileRecord.user_id == user_id,
        )
    )
    if existing:
        if existing.status != "active":
            existing.status = "active"
        return existing

    site = require_confirmed_matricule_prefix(db, organization.id)
    prefix = site.student_code_prefix.upper()
    year = datetime.now(UTC).strftime("%y")
    base = f"{prefix}-P{year}-"
    count = int(
        db.scalar(
            select(func.count(OrganizationTeacherProfileRecord.id)).where(
                OrganizationTeacherProfileRecord.organization_id == organization.id,
                OrganizationTeacherProfileRecord.teacher_code.like(f"{base}%"),
            )
        )
        or 0
    )
    for sequence in range(count + 1, count + 10000):
        code = f"{base}{sequence:03d}"
        if db.scalar(
            select(OrganizationTeacherProfileRecord.id).where(
                OrganizationTeacherProfileRecord.organization_id == organization.id,
                OrganizationTeacherProfileRecord.teacher_code == code,
            )
        ) is None:
            row = OrganizationTeacherProfileRecord(
                organization_id=organization.id,
                user_id=user_id,
                teacher_code=code,
                status="active",
                first_assigned_at=datetime.now(UTC),
            )
            db.add(row)
            db.flush()
            return row
    raise RuntimeError("Impossible de générer un code enseignant unique.")
