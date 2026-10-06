from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.teacher_onboarding import (
    OrganizationCharterAcceptanceRecord,
    OrganizationCharterRecord,
    TeacherProfessionalProfileRecord,
)
from app.services.tenancy import TenantContext


def teacher_profile_complete(row: TeacherProfessionalProfileRecord) -> bool:
    return bool(
        row.professional_title.strip()
        and row.activity_domains
        and len(row.bio.strip()) >= 40
        and row.skills
        and row.languages
        and row.whatsapp_phone
        and row.whatsapp_country
        and row.city
        and row.country
        and (row.portfolio_url or row.portfolio_file_key)
    )


def require_teacher_ready(db: Session, tenant: TenantContext) -> None:
    if not tenant.has_role("teacher"):
        return

    profile = db.scalar(
        select(TeacherProfessionalProfileRecord).where(
            TeacherProfessionalProfileRecord.organization_id == tenant.organization_id,
            TeacherProfessionalProfileRecord.user_id == tenant.user.id,
        )
    )
    if profile is None or not teacher_profile_complete(profile):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Finalisez votre fiche enseignant avant de commencer à donner cours.",
        )

    charter = db.scalar(
        select(OrganizationCharterRecord).where(
            OrganizationCharterRecord.organization_id == tenant.organization_id,
            OrganizationCharterRecord.audience == "teacher",
        )
    )
    if charter is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Finalisez votre fiche enseignant et validez la charte avant de commencer à donner cours.",
        )
    if not charter.is_enabled:
        return

    acceptance = db.scalar(
        select(OrganizationCharterAcceptanceRecord.id).where(
            OrganizationCharterAcceptanceRecord.organization_id == tenant.organization_id,
            OrganizationCharterAcceptanceRecord.charter_id == charter.id,
            OrganizationCharterAcceptanceRecord.user_id == tenant.user.id,
            OrganizationCharterAcceptanceRecord.version == charter.version,
        )
    )
    if acceptance is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Validez la charte enseignant avant de commencer à donner cours.",
        )
