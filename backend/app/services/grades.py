from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import GradeRecord


def upsert_grade(
    db: Session,
    *,
    organization_id: int,
    session_id: int,
    enrollment_id: int,
    teacher_id: int | None,
    source_type: str,
    source_id: int | None,
    label: str,
    score: float,
    max_score: float = 20,
    note: str = "",
) -> GradeRecord:
    row = None
    if source_id is not None:
        row = db.scalar(
            select(GradeRecord).where(
                GradeRecord.organization_id == organization_id,
                GradeRecord.enrollment_id == enrollment_id,
                GradeRecord.source_type == source_type,
                GradeRecord.source_id == source_id,
            )
        )

    if row is None:
        row = GradeRecord(
            organization_id=organization_id,
            session_id=session_id,
            enrollment_id=enrollment_id,
            teacher_id=teacher_id,
            source_type=source_type,
            source_id=source_id,
            label=label,
            score=score,
            max_score=max_score,
            note=note,
        )
        db.add(row)
    else:
        row.teacher_id = teacher_id
        row.label = label
        row.score = score
        row.max_score = max_score
        row.note = note

    return row


def grade_average_pct(db: Session, *, organization_id: int, enrollment_id: int) -> float | None:
    rows = list(
        db.scalars(
            select(GradeRecord).where(
                GradeRecord.organization_id == organization_id,
                GradeRecord.enrollment_id == enrollment_id,
            )
        ).all()
    )
    values = [
        (row.score / row.max_score) * 100
        for row in rows
        if row.max_score and row.max_score > 0
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 1)
