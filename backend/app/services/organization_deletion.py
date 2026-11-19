from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import OrganizationRecord, StudentOrderRecord
from app.services.object_storage import b2_client

logger = logging.getLogger(__name__)

DELETION_GRACE_DAYS = 20
DELETION_BATCH_SIZE = 25


def _utc_now() -> datetime:
    return datetime.now(UTC)


def request_organization_deletion(
    db: Session,
    organization: OrganizationRecord,
) -> OrganizationRecord:
    if organization.status == "deletion_pending":
        return organization
    now = _utc_now()
    organization.status = "deletion_pending"
    organization.deletion_requested_at = now
    organization.deletion_scheduled_at = now + timedelta(days=DELETION_GRACE_DAYS)
    db.commit()
    db.refresh(organization)
    return organization


def cancel_organization_deletion(
    db: Session,
    organization: OrganizationRecord,
) -> OrganizationRecord:
    if organization.status != "deletion_pending":
        return organization
    scheduled_at = organization.deletion_scheduled_at
    if scheduled_at is not None:
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=UTC)
        if scheduled_at <= _utc_now():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Le délai de 20 jours est expiré; la suppression ne peut plus être annulée.",
            )
    organization.status = "active"
    organization.deletion_requested_at = None
    organization.deletion_scheduled_at = None
    db.commit()
    db.refresh(organization)
    return organization


def _delete_cloudinary_assets(organization_id: int) -> None:
    if settings.public_asset_provider != "cloudinary":
        return
    if not settings.cloudinary_configured:
        if settings.environment == "production":
            raise RuntimeError("Cloudinary n'est pas configuré pour supprimer les médias de l'école.")
        return

    import cloudinary
    from cloudinary import api

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    prefix = f"schools/{organization_id}/"
    for resource_type in ("image", "video", "raw"):
        cursor: str | None = None
        while True:
            options: dict[str, str | bool] = {
                "resource_type": resource_type,
                "type": "upload",
                "invalidate": True,
            }
            if cursor:
                options["next_cursor"] = cursor
            result = api.delete_resources_by_prefix(prefix, **options)
            cursor = result.get("next_cursor")
            if not cursor:
                break


def _delete_b2_prefix(bucket: str, prefix: str) -> None:
    client = b2_client()
    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = [
            {"Key": entry["Key"], "VersionId": entry["VersionId"]}
            for entry in (*page.get("Versions", []), *page.get("DeleteMarkers", []))
        ]
        for offset in range(0, len(objects), 1000):
            response = client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": objects[offset:offset + 1000], "Quiet": True},
            )
            if response.get("Errors"):
                raise RuntimeError(f"B2 n'a pas supprimé tous les objets du bucket {bucket}.")


def _delete_school_files(organization_id: int) -> None:
    if settings.storage_provider == "b2":
        if not settings.b2_configured:
            if settings.environment == "production":
                raise RuntimeError("B2 n'est pas configuré pour supprimer les fichiers de l'école.")
        else:
            buckets = {
                bucket
                for bucket in (settings.b2_private_bucket_name, settings.b2_bucket_name)
                if bucket
            }
            for bucket in buckets:
                _delete_b2_prefix(bucket, f"schools/{organization_id}/")

    backend_root = Path(__file__).resolve().parents[2]
    for folder in ("uploads", "private_uploads"):
        school_folder = backend_root / folder / "schools" / str(organization_id)
        if school_folder.is_dir():
            shutil.rmtree(school_folder)


def _delete_organization_data(db: Session, organization: OrganizationRecord) -> None:
    organization_id = organization.id
    # Student orders reference formations and sessions with RESTRICT constraints.
    db.execute(
        delete(StudentOrderRecord).where(
            StudentOrderRecord.organization_id == organization_id
        )
    )
    db.delete(organization)
    db.commit()


def purge_expired_organizations(db: Session) -> dict[str, int]:
    now = _utc_now()
    organization_ids = list(
        db.scalars(
            select(OrganizationRecord.id)
            .where(
                OrganizationRecord.status == "deletion_pending",
                OrganizationRecord.deletion_scheduled_at <= now,
            )
            .order_by(OrganizationRecord.deletion_scheduled_at)
            .limit(DELETION_BATCH_SIZE)
        ).all()
    )
    deleted = 0
    failures = 0
    for organization_id in organization_ids:
        organization = db.scalar(
            select(OrganizationRecord)
            .where(OrganizationRecord.id == organization_id)
            .with_for_update()
        )
        if organization is None:
            continue
        try:
            _delete_cloudinary_assets(organization_id)
            _delete_school_files(organization_id)
            _delete_organization_data(db, organization)
            deleted += 1
        except Exception:
            db.rollback()
            failures += 1
            logger.exception(
                "Échec de la purge définitive de l'école %s; elle sera retentée au prochain cycle.",
                organization_id,
            )
    return {"due": len(organization_ids), "deleted": deleted, "failures": failures}
