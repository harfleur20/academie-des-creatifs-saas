from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import OrganizationTeacherProfileRecord, UserRecord
from app.models.teacher_onboarding import (
    OrganizationCharterAcceptanceRecord,
    OrganizationCharterRecord,
    TeacherProfessionalProfileRecord,
)
from app.schemas.workspace_onboarding import (
    OrganizationCharterRead,
    OrganizationCharterUpdate,
    PhoneCountryRead,
    TeacherProfessionalProfileRead,
    TeacherProfessionalProfileUpdate,
)
from app.services.phone_numbers import normalize_whatsapp_phone, supported_phone_countries
from app.services.teacher_readiness import teacher_profile_complete
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/workspace-onboarding", tags=["workspace-onboarding"])


DEFAULT_CHARTERS: dict[str, tuple[str, str]] = {
    "teacher": (
        "Charte de l’enseignant",
        """En rejoignant l’équipe pédagogique de l’école, je m’engage à :

• respecter les apprenants, l’équipe et les valeurs de l’établissement ;
• préparer mes interventions avec sérieux et respecter les horaires annoncés ;
• assurer un accompagnement pédagogique professionnel, bienveillant et équitable ;
• préserver la confidentialité des informations concernant les étudiants et l’école ;
• respecter la propriété intellectuelle des contenus, supports et travaux partagés ;
• utiliser les outils numériques de l’école de manière responsable et sécurisée ;
• signaler rapidement tout incident, difficulté pédagogique ou situation nécessitant l’intervention de l’administration ;
• maintenir mes informations professionnelles à jour.

Je reconnais que l’école peut faire évoluer cette charte. Une nouvelle validation pourra être demandée lorsqu’une nouvelle version est publiée.""",
    ),
    "student": (
        "Charte de l’étudiant",
        """En intégrant l’école et ses espaces numériques, je m’engage à :

• respecter les enseignants, les autres étudiants et l’équipe administrative ;
• adopter une communication respectueuse dans les cours, lives, messages et espaces communautaires ;
• respecter les horaires, consignes pédagogiques et règles de présence applicables à ma formation ;
• réaliser mes travaux avec honnêteté et ne pas présenter le travail d’une autre personne comme le mien ;
• ne pas diffuser sans autorisation les cours, ressources, identifiants, liens privés ou contenus protégés ;
• utiliser les outils de l’école de manière responsable et ne pas tenter de contourner les règles d’accès ;
• signaler à l’équipe tout problème important pouvant affecter mon apprentissage ou la sécurité de la plateforme.

Je reconnais que l’école peut faire évoluer cette charte. Une nouvelle validation pourra être demandée lorsqu’une nouvelle version est publiée.""",
    ),
}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_list(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value[:120])
        if len(result) >= limit:
            break
    return result


def _ensure_teacher_record(db: Session, tenant: TenantContext) -> TeacherProfessionalProfileRecord:
    require_organization_roles(tenant, "teacher")
    row = db.scalar(
        select(TeacherProfessionalProfileRecord).where(
            TeacherProfessionalProfileRecord.organization_id == tenant.organization_id,
            TeacherProfessionalProfileRecord.user_id == tenant.user.id,
        )
    )
    if row is None:
        row = TeacherProfessionalProfileRecord(
            organization_id=tenant.organization_id,
            user_id=tenant.user.id,
        )
        db.add(row)
        db.flush()
    return row


def _teacher_profile_read(
    db: Session,
    tenant: TenantContext,
    row: TeacherProfessionalProfileRecord,
    *,
    user: UserRecord | None = None,
) -> TeacherProfessionalProfileRead:
    target_user = user or tenant.user
    code = db.scalar(
        select(OrganizationTeacherProfileRecord.teacher_code).where(
            OrganizationTeacherProfileRecord.organization_id == tenant.organization_id,
            OrganizationTeacherProfileRecord.user_id == target_user.id,
        )
    )
    return TeacherProfessionalProfileRead(
        organization_id=tenant.organization_id,
        organization_name=tenant.organization.name,
        user_id=target_user.id,
        full_name=target_user.full_name,
        email=target_user.email,
        phone=target_user.phone,
        avatar_url=target_user.avatar_url,
        teacher_code=code,
        professional_title=row.professional_title,
        experience_years=row.experience_years,
        activity_domains=list(row.activity_domains or []),
        bio=row.bio,
        skills=list(row.skills or []),
        portfolio_url=row.portfolio_url,
        portfolio_file_name=row.portfolio_file_name,
        cv_file_name=row.cv_file_name,
        linkedin_url=row.linkedin_url,
        behance_url=row.behance_url,
        github_url=row.github_url,
        website_url=row.website_url,
        city=row.city,
        country=row.country,
        languages=list(row.languages or []),
        whatsapp_phone=row.whatsapp_phone,
        whatsapp_country=row.whatsapp_country,
        whatsapp_phone_legacy=row.whatsapp_phone_legacy,
        whatsapp_phone_verified_at=row.whatsapp_phone_verified_at,
        profile_completed_at=row.profile_completed_at,
        is_complete=teacher_profile_complete(row),
    )


def _can_manage_teacher_profiles(tenant: TenantContext) -> bool:
    return bool(
        tenant.organization_roles.intersection({"owner", "admin", "manager"})
        or tenant.user.platform_role == "super_admin"
    )


def _require_teacher_profile_access(tenant: TenantContext, user_id: int) -> None:
    if user_id == tenant.user.id and tenant.has_role("teacher"):
        return
    if _can_manage_teacher_profiles(tenant):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès à cette fiche enseignant refusé.")


def _get_teacher_profile_row(db: Session, tenant: TenantContext, user_id: int) -> TeacherProfessionalProfileRecord:
    row = db.scalar(
        select(TeacherProfessionalProfileRecord).where(
            TeacherProfessionalProfileRecord.organization_id == tenant.organization_id,
            TeacherProfessionalProfileRecord.user_id == user_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Cet enseignant n’a pas encore commencé sa fiche professionnelle.")
    return row


def _ensure_charter(
    db: Session,
    tenant: TenantContext,
    audience: str,
) -> OrganizationCharterRecord:
    if audience not in DEFAULT_CHARTERS:
        raise HTTPException(status_code=404, detail="Charte introuvable.")
    charter = db.scalar(
        select(OrganizationCharterRecord).where(
            OrganizationCharterRecord.organization_id == tenant.organization_id,
            OrganizationCharterRecord.audience == audience,
        )
    )
    if charter is None:
        title, content = DEFAULT_CHARTERS[audience]
        charter = OrganizationCharterRecord(
            organization_id=tenant.organization_id,
            audience=audience,
            title=title,
            content=content,
            is_enabled=True,
            version=1,
            updated_by_user_id=tenant.user.id,
        )
        db.add(charter)
        db.commit()
        db.refresh(charter)
    return charter


def _charter_access(tenant: TenantContext, audience: str) -> None:
    if tenant.organization_roles.intersection({"owner", "admin", "manager"}) or tenant.user.platform_role == "super_admin":
        return
    require_organization_roles(tenant, audience)


def _charter_read(
    db: Session,
    tenant: TenantContext,
    charter: OrganizationCharterRecord,
) -> OrganizationCharterRead:
    acceptance = db.scalar(
        select(OrganizationCharterAcceptanceRecord).where(
            OrganizationCharterAcceptanceRecord.organization_id == tenant.organization_id,
            OrganizationCharterAcceptanceRecord.charter_id == charter.id,
            OrganizationCharterAcceptanceRecord.user_id == tenant.user.id,
            OrganizationCharterAcceptanceRecord.version == charter.version,
        )
    )
    return OrganizationCharterRead(
        id=charter.id,
        organization_id=tenant.organization_id,
        audience=charter.audience,
        title=charter.title,
        content=charter.content,
        is_enabled=charter.is_enabled,
        version=charter.version,
        accepted_current_version=(not charter.is_enabled) or acceptance is not None,
        accepted_at=acceptance.accepted_at if acceptance else None,
    )


@router.get("/phone-countries", response_model=list[PhoneCountryRead])
def get_phone_countries(
    tenant: TenantContext = Depends(get_tenant_context),
):
    if not tenant.has_role("teacher") and not _can_manage_teacher_profiles(tenant):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
    return supported_phone_countries()


@router.get("/teacher-profile", response_model=TeacherProfessionalProfileRead)
def get_teacher_professional_profile(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    row = _ensure_teacher_record(db, tenant)
    if row.id is None:
        db.commit()
        db.refresh(row)
    return _teacher_profile_read(db, tenant, row)


@router.get("/teacher-profiles/{user_id}", response_model=TeacherProfessionalProfileRead)
def get_teacher_professional_profile_for_school(
    user_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    _require_teacher_profile_access(tenant, user_id)
    row = _get_teacher_profile_row(db, tenant, user_id)
    user = db.get(UserRecord, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Enseignant introuvable.")
    return _teacher_profile_read(db, tenant, row, user=user)


@router.put("/teacher-profile", response_model=TeacherProfessionalProfileRead)
def update_teacher_professional_profile(
    payload: TeacherProfessionalProfileUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    row = _ensure_teacher_record(db, tenant)
    try:
        whatsapp_phone, is_legacy = normalize_whatsapp_phone(
            payload.whatsapp_phone,
            payload.whatsapp_country,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    previous_whatsapp_phone = row.whatsapp_phone
    row.professional_title = payload.professional_title.strip()
    row.experience_years = payload.experience_years
    row.activity_domains = _clean_list(payload.activity_domains, limit=20)
    row.bio = payload.bio.strip()
    row.skills = _clean_list(payload.skills, limit=40)
    row.portfolio_url = _clean_text(payload.portfolio_url)
    row.linkedin_url = _clean_text(payload.linkedin_url)
    row.behance_url = _clean_text(payload.behance_url)
    row.github_url = _clean_text(payload.github_url)
    row.website_url = _clean_text(payload.website_url)
    row.city = payload.city.strip()
    row.country = payload.country.strip()
    row.languages = _clean_list(payload.languages, limit=20)
    row.whatsapp_phone = whatsapp_phone
    row.whatsapp_country = payload.whatsapp_country.strip().upper()
    row.whatsapp_phone_legacy = is_legacy
    if previous_whatsapp_phone != whatsapp_phone:
        row.whatsapp_phone_verified_at = None
    row.profile_completed_at = datetime.now(UTC) if teacher_profile_complete(row) else None
    db.commit()
    db.refresh(row)
    return _teacher_profile_read(db, tenant, row)


@router.post("/teacher-profile/documents/{document_kind}", response_model=TeacherProfessionalProfileRead)
async def upload_teacher_professional_document(
    document_kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if document_kind not in {"portfolio", "cv"}:
        raise HTTPException(status_code=404, detail="Type de document inconnu.")
    row = _ensure_teacher_record(db, tenant)
    original_name = Path(file.filename or "document.pdf").name
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Seuls les fichiers PDF sont autorisés.")
    raw = await file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Le document ne doit pas dépasser 10 Mo.")
    if not raw.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Le fichier fourni n’est pas un PDF valide.")

    key = f"schools/{tenant.organization_id}/teacher-profiles/{tenant.user.id}/{document_kind}-{uuid4().hex}.pdf"
    if settings.storage_provider == "r2":
        if not settings.r2_configured or not settings.r2_private_bucket_name:
            raise HTTPException(status_code=503, detail="Stockage privé R2 non configuré.")
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        client.put_object(
            Bucket=settings.r2_private_bucket_name,
            Key=key,
            Body=raw,
            ContentType="application/pdf",
        )
    else:
        if settings.environment == "production":
            raise HTTPException(status_code=503, detail="Le stockage local est désactivé en production.")
        destination = Path(__file__).resolve().parents[3] / "private_uploads" / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)

    if document_kind == "portfolio":
        row.portfolio_file_key = key
        row.portfolio_file_name = original_name
    else:
        row.cv_file_key = key
        row.cv_file_name = original_name
    row.profile_completed_at = datetime.now(UTC) if teacher_profile_complete(row) else None
    db.commit()
    db.refresh(row)
    return _teacher_profile_read(db, tenant, row)


@router.get("/teacher-profiles/{user_id}/documents/{document_kind}")
def preview_teacher_professional_document(
    user_id: int,
    document_kind: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if document_kind not in {"portfolio", "cv"}:
        raise HTTPException(status_code=404, detail="Type de document inconnu.")
    _require_teacher_profile_access(tenant, user_id)
    row = _get_teacher_profile_row(db, tenant, user_id)
    key = row.portfolio_file_key if document_kind == "portfolio" else row.cv_file_key
    if not key:
        raise HTTPException(status_code=404, detail="Ce document n’a pas été importé.")

    headers = {"Content-Disposition": "inline"}
    if settings.storage_provider == "r2":
        if not settings.r2_configured or not settings.r2_private_bucket_name:
            raise HTTPException(status_code=503, detail="Stockage privé R2 non configuré.")
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        try:
            stored = client.get_object(Bucket=settings.r2_private_bucket_name, Key=key)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Document introuvable dans le stockage.") from exc
        return Response(content=stored["Body"].read(), media_type="application/pdf", headers=headers)

    destination = Path(__file__).resolve().parents[3] / "private_uploads" / key
    if not destination.is_file():
        raise HTTPException(status_code=404, detail="Document introuvable dans le stockage.")
    return FileResponse(destination, media_type="application/pdf", headers=headers)


@router.get("/charters/{audience}", response_model=OrganizationCharterRead)
def get_organization_charter(
    audience: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    _charter_access(tenant, audience)
    charter = _ensure_charter(db, tenant, audience)
    return _charter_read(db, tenant, charter)


@router.put("/charters/{audience}", response_model=OrganizationCharterRead)
def update_organization_charter(
    audience: str,
    payload: OrganizationCharterUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    charter = _ensure_charter(db, tenant, audience)
    new_title = payload.title.strip()
    new_content = payload.content.strip()
    content_changed = charter.title != new_title or charter.content != new_content
    charter.title = new_title
    charter.content = new_content
    charter.is_enabled = payload.is_enabled
    charter.updated_by_user_id = tenant.user.id
    if content_changed:
        charter.version += 1
    db.commit()
    db.refresh(charter)
    return _charter_read(db, tenant, charter)


@router.post("/charters/{audience}/accept", response_model=OrganizationCharterRead, status_code=status.HTTP_201_CREATED)
def accept_organization_charter(
    audience: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, audience)
    charter = _ensure_charter(db, tenant, audience)
    if charter.is_enabled:
        existing = db.scalar(
            select(OrganizationCharterAcceptanceRecord).where(
                OrganizationCharterAcceptanceRecord.charter_id == charter.id,
                OrganizationCharterAcceptanceRecord.user_id == tenant.user.id,
                OrganizationCharterAcceptanceRecord.version == charter.version,
            )
        )
        if existing is None:
            db.add(
                OrganizationCharterAcceptanceRecord(
                    organization_id=tenant.organization_id,
                    charter_id=charter.id,
                    user_id=tenant.user.id,
                    audience=audience,
                    version=charter.version,
                )
            )
            db.commit()
    return _charter_read(db, tenant, charter)
