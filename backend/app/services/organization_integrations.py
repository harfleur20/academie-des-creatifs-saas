from __future__ import annotations

import base64
import hashlib
import os
from datetime import UTC, datetime

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.integrations import OrganizationIntegrationRecord
from app.services.tenancy import TenantContext


OPENAI_API_BASE_URL = "https://api.openai.com/v1"
OPENAI_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-6-luna"


def _fernet() -> Fernet:
    explicit = os.getenv("INTEGRATION_ENCRYPTION_KEY", "").strip()
    if explicit:
        try:
            return Fernet(explicit.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("INTEGRATION_ENCRYPTION_KEY doit être une clé Fernet valide.") from exc

    digest = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Impossible de déchiffrer le secret de l’intégration.") from exc


def get_integration(
    db: Session,
    tenant: TenantContext,
    provider: str,
) -> OrganizationIntegrationRecord | None:
    return db.scalar(
        select(OrganizationIntegrationRecord).where(
            OrganizationIntegrationRecord.organization_id == tenant.organization_id,
            OrganizationIntegrationRecord.provider == provider,
        )
    )


def _openai_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _connection_error(response: httpx.Response, *, model: str | None = None) -> str:
    if response.status_code == 401:
        return "Clé API OpenAI invalide ou révoquée."
    if response.status_code == 403:
        return "Cette clé OpenAI n’autorise pas cet accès."
    if response.status_code == 404 and model:
        return f"Le modèle OpenAI « {model} » n’est pas disponible pour cette clé."
    if response.status_code == 429:
        return "OpenAI refuse temporairement la requête (quota ou limite atteinte)."
    return f"OpenAI a répondu avec le statut {response.status_code}."


def test_openai_key(api_key: str, model: str | None = None) -> None:
    endpoint = f"{OPENAI_API_BASE_URL}/models/{model}" if model else f"{OPENAI_API_BASE_URL}/models"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(endpoint, headers=_openai_headers(api_key))
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de joindre OpenAI pour tester la connexion.",
        ) from exc
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_connection_error(response, model=model),
        )


def save_openai_integration(
    db: Session,
    tenant: TenantContext,
    *,
    api_key: str,
    model: str,
) -> OrganizationIntegrationRecord:
    normalized_key = api_key.strip()
    normalized_model = model.strip() or DEFAULT_OPENAI_MODEL
    test_openai_key(normalized_key, normalized_model)
    now = datetime.now(UTC)
    record = get_integration(db, tenant, OPENAI_PROVIDER)
    if record is None:
        record = OrganizationIntegrationRecord(
            organization_id=tenant.organization_id,
            provider=OPENAI_PROVIDER,
            status="connected",
            secret_ciphertext=encrypt_secret(normalized_key),
            model=normalized_model,
            connected_at=now,
            last_tested_at=now,
            last_error=None,
        )
        db.add(record)
    else:
        record.secret_ciphertext = encrypt_secret(normalized_key)
        record.model = normalized_model
        record.status = "connected"
        record.connected_at = now
        record.last_tested_at = now
        record.last_error = None
    db.commit()
    db.refresh(record)
    return record


def test_saved_openai_integration(
    db: Session,
    tenant: TenantContext,
) -> OrganizationIntegrationRecord:
    record = get_integration(db, tenant, OPENAI_PROVIDER)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OpenAI n’est pas connecté pour cette école.",
        )
    try:
        test_openai_key(decrypt_secret(record.secret_ciphertext), record.model)
    except HTTPException as exc:
        record.status = "error"
        record.last_tested_at = datetime.now(UTC)
        record.last_error = str(exc.detail)[:500]
        db.commit()
        raise
    record.status = "connected"
    record.last_tested_at = datetime.now(UTC)
    record.last_error = None
    db.commit()
    db.refresh(record)
    return record


def delete_openai_integration(db: Session, tenant: TenantContext) -> None:
    record = get_integration(db, tenant, OPENAI_PROVIDER)
    if record is None:
        return
    db.delete(record)
    db.commit()


def openai_credentials(
    db: Session,
    tenant: TenantContext,
) -> tuple[str, str, OrganizationIntegrationRecord]:
    record = get_integration(db, tenant, OPENAI_PROVIDER)
    if record is None or record.status != "connected":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="L’école doit connecter OpenAI dans Connect avant d’utiliser l’IA.",
        )
    try:
        api_key = decrypt_secret(record.secret_ciphertext)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La connexion OpenAI de l’école doit être reconfigurée.",
        ) from exc
    return api_key, record.model or DEFAULT_OPENAI_MODEL, record
