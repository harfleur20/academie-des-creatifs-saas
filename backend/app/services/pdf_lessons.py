"""School-scoped PDF lesson storage, reading and quiz eligibility."""
from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.object_storage import b2_client
from app.models.entities import (
    ChapterRecord, CourseRecord, EnrollmentRecord, LessonPdfAssetRecord,
    LessonPdfProgressRecord, LessonProgressRecord, LessonRecord, QuizAttemptRecord, QuizRecord,
)
from app.services.learning_progress import _student_lesson_context
from app.services.tenancy import TenantContext


PDF_READING_PCT = 80.0
PDF_PAGE_MIN_SECONDS = 2.0
PDF_MAX_BYTES = 15 * 1024 * 1024


def pdf_asset(db: Session, organization_id: int, source_url: str | None) -> LessonPdfAssetRecord | None:
    if not source_url:
        return None
    return db.scalar(select(LessonPdfAssetRecord).where(
        LessonPdfAssetRecord.organization_id == organization_id,
        LessonPdfAssetRecord.source_url == source_url,
    ))


def pdf_lesson_for_quiz(db: Session, organization_id: int, session_id: int, quiz_id: int) -> LessonRecord | None:
    return db.scalar(
        select(LessonRecord)
        .join(ChapterRecord, ChapterRecord.id == LessonRecord.chapter_id)
        .join(CourseRecord, CourseRecord.id == ChapterRecord.course_id)
        .where(
            LessonRecord.organization_id == organization_id,
            ChapterRecord.organization_id == organization_id,
            CourseRecord.organization_id == organization_id,
            CourseRecord.session_id == session_id,
            LessonRecord.lesson_type == "pdf",
            LessonRecord.quiz_id == quiz_id,
        )
    )


def viewed_pct(progress: LessonPdfProgressRecord | None, page_count: int) -> float:
    if progress is None or page_count < 1:
        return 0.0
    count = len({page for page in progress.viewed_pages or [] if 1 <= page <= page_count})
    return math.floor(1000 * count / page_count) / 10


def _progress(db: Session, organization_id: int, enrollment_id: int, lesson_id: int, asset: LessonPdfAssetRecord) -> LessonPdfProgressRecord | None:
    progress = db.scalar(select(LessonPdfProgressRecord).where(
        LessonPdfProgressRecord.organization_id == organization_id,
        LessonPdfProgressRecord.enrollment_id == enrollment_id,
        LessonPdfProgressRecord.lesson_id == lesson_id,
    ))
    if progress is not None and progress.source_sha != asset.source_sha:
        progress.source_sha = asset.source_sha
        progress.viewed_pages = []
        progress.last_page = 1
        progress.active_page = None
        progress.active_since = None
    return progress


def _context(db: Session, tenant: TenantContext, lesson_id: int):
    lesson, enrollment = _student_lesson_context(db, tenant, lesson_id)
    asset = pdf_asset(db, tenant.organization_id, lesson.file_url)
    if lesson.lesson_type != "pdf" or lesson.quiz_id is None or asset is None:
        raise HTTPException(404, "Suivi PDF indisponible pour cette leçon.")
    quiz = db.get(QuizRecord, lesson.quiz_id)
    if quiz is None or quiz.organization_id != tenant.organization_id or quiz.session_id != enrollment.session_id:
        raise HTTPException(404, "Quiz PDF introuvable.")
    return lesson, enrollment, asset


def _view(db: Session, organization_id: int, lesson: LessonRecord, enrollment: EnrollmentRecord, asset: LessonPdfAssetRecord, progress: LessonPdfProgressRecord | None) -> dict:
    completed = db.scalar(select(LessonProgressRecord.id).where(
        LessonProgressRecord.organization_id == organization_id,
        LessonProgressRecord.enrollment_id == enrollment.id,
        LessonProgressRecord.lesson_id == lesson.id,
    )) is not None
    pct = viewed_pct(progress, asset.page_count)
    return {
        "page_count": asset.page_count,
        "viewed_pages": list(progress.viewed_pages or []) if progress else [],
        "viewed_pct": pct,
        "last_page": progress.last_page if progress else 1,
        "quiz_unlocked": pct >= PDF_READING_PCT,
        "is_completed": completed,
    }


def read_pdf_progress(db: Session, tenant: TenantContext, lesson_id: int) -> dict:
    lesson, enrollment, asset = _context(db, tenant, lesson_id)
    progress = _progress(db, tenant.organization_id, enrollment.id, lesson.id, asset)
    if progress is not None and db.is_modified(progress):
        db.commit()
    return _view(db, tenant.organization_id, lesson, enrollment, asset, progress)


def report_pdf_page(db: Session, tenant: TenantContext, lesson_id: int, page: int, event: str) -> dict:
    lesson, enrollment, asset = _context(db, tenant, lesson_id)
    if page < 1 or page > asset.page_count:
        raise HTTPException(422, "Cette page n'existe pas dans le document.")
    if event not in {"open", "confirm"}:
        raise HTTPException(422, "Événement de lecture inconnu.")
    db.get(EnrollmentRecord, enrollment.id, populate_existing=True, with_for_update=True)
    progress = _progress(db, tenant.organization_id, enrollment.id, lesson.id, asset)
    if progress is None:
        progress = LessonPdfProgressRecord(
            organization_id=tenant.organization_id,
            enrollment_id=enrollment.id,
            lesson_id=lesson.id,
            source_sha=asset.source_sha,
            viewed_pages=[],
        )
        db.add(progress)
    now = datetime.now(UTC)
    if event == "open":
        progress.last_page = page
        progress.active_page = page
        progress.active_since = now
    elif progress.active_page == page and progress.active_since is not None:
        opened = progress.active_since
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=UTC)
        if (now - opened).total_seconds() >= PDF_PAGE_MIN_SECONDS:
            progress.viewed_pages = sorted(set(progress.viewed_pages or []) | {page})
            complete_pdf_if_eligible(db, tenant.organization_id, lesson, enrollment, asset, progress)
    db.commit()
    return _view(db, tenant.organization_id, lesson, enrollment, asset, progress)


def complete_pdf_if_eligible(db: Session, organization_id: int, lesson: LessonRecord, enrollment: EnrollmentRecord, asset: LessonPdfAssetRecord, progress: LessonPdfProgressRecord | None = None) -> bool:
    progress = progress or _progress(db, organization_id, enrollment.id, lesson.id, asset)
    if viewed_pct(progress, asset.page_count) < PDF_READING_PCT or lesson.quiz_id is None:
        return False
    quiz = db.get(QuizRecord, lesson.quiz_id)
    if quiz is None or quiz.organization_id != organization_id or quiz.session_id != enrollment.session_id:
        return False
    scores = db.scalars(select(QuizAttemptRecord.score_pct).where(
        QuizAttemptRecord.organization_id == organization_id,
        QuizAttemptRecord.enrollment_id == enrollment.id,
        QuizAttemptRecord.quiz_id == quiz.id,
    )).all()
    if not scores or max(scores) < quiz.pass_pct:
        return False
    existing = db.scalar(select(LessonProgressRecord.id).where(
        LessonProgressRecord.organization_id == organization_id,
        LessonProgressRecord.enrollment_id == enrollment.id,
        LessonProgressRecord.lesson_id == lesson.id,
    ))
    if existing is None:
        db.add(LessonProgressRecord(
            organization_id=organization_id,
            enrollment_id=enrollment.id,
            lesson_id=lesson.id,
            completed_at=datetime.now(UTC),
        ))
    return True


async def store_pdf_asset(db: Session, tenant: TenantContext, file: UploadFile) -> LessonPdfAssetRecord:
    if not tenant.has_role("teacher") or tenant.support_mode:
        raise HTTPException(403, "Accès professeur requis.")
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(415, "Choisissez un fichier PDF.")
    raw = await file.read(PDF_MAX_BYTES + 1)
    if len(raw) > PDF_MAX_BYTES:
        raise HTTPException(413, "Le PDF dépasse 15 Mo.")
    if not raw.startswith(b"%PDF-"):
        raise HTTPException(415, "Le document n'est pas un PDF valide.")
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted or len(reader.pages) < 1:
            raise ValueError("unreadable PDF")
        page_count = len(reader.pages)
    except Exception as exc:
        raise HTTPException(422, "Le PDF est invalide ou protégé.") from exc
    key = f"schools/{tenant.organization_id}/lesson-pdfs/{uuid4().hex}.pdf"
    if settings.storage_provider == "b2":
        if not settings.b2_configured or not settings.b2_private_bucket_name or settings.b2_private_bucket_name == settings.b2_bucket_name:
            raise HTTPException(503, "Un bucket B2 privé distinct est requis pour les PDF.")
        client = b2_client()
        client.put_object(Bucket=settings.b2_private_bucket_name, Key=key, Body=raw, ContentType="application/pdf")
    else:
        if settings.environment == "production":
            raise HTTPException(503, "Le stockage local est désactivé en production.")
        path = Path(__file__).resolve().parents[2] / "private_uploads" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    asset = LessonPdfAssetRecord(
        organization_id=tenant.organization_id,
        source_url=f"school-pdf:pending:{uuid4().hex}",
        storage_key=key,
        source_sha=hashlib.sha256(raw).hexdigest(),
        page_count=page_count,
        uploaded_by_user_id=tenant.user.id,
    )
    db.add(asset)
    db.flush()
    asset.source_url = f"school-pdf:{asset.id}"
    db.commit()
    return asset


def pdf_bytes(db: Session, tenant: TenantContext, lesson_id: int) -> bytes:
    _lesson, _enrollment, asset = _context(db, tenant, lesson_id)
    if settings.storage_provider == "b2":
        client = b2_client()
        try:
            return client.get_object(Bucket=settings.b2_private_bucket_name, Key=asset.storage_key)["Body"].read()
        except Exception as exc:
            raise HTTPException(503, "Le PDF est indisponible.") from exc
    path = Path(__file__).resolve().parents[2] / "private_uploads" / asset.storage_key
    try:
        return path.read_bytes()
    except OSError as exc:
        raise HTTPException(503, "Le PDF est indisponible.") from exc
