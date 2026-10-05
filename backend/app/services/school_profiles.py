from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    OrganizationRecord,
    OrganizationTeacherProfileRecord,
)
from app.services.school_setup import require_confirmed_matricule_prefix


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
