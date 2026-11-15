from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integrations import OrganizationIntegrationRecord
from app.models.platform_integrations import PlatformIntegrationPreferenceRecord


INTEGRATION_BADGE_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("openai", "connect"),
    ("claude", "connect"),
    ("imara", "connect"),
    ("google_analytics", "recommended"),
    ("search_console", "recommended"),
    ("meta_pixel", "recommended"),
    ("brevo", "recommended"),
    ("whatsapp", "recommended"),
    ("google_calendar", "connect"),
    ("make_zapier", "connect"),
)


def list_integration_badge_preferences(
    db: Session,
    *,
    organization_id: int | None = None,
) -> list[dict[str, str | bool]]:
    saved = {
        item.provider: item.badge_mode
        for item in db.scalars(select(PlatformIntegrationPreferenceRecord)).all()
    }
    connected_providers = set()
    if organization_id is not None:
        connected_providers = set(
            db.scalars(
                select(OrganizationIntegrationRecord.provider).where(
                    OrganizationIntegrationRecord.organization_id == organization_id,
                    OrganizationIntegrationRecord.status == "connected",
                )
            ).all()
        )
    return [
        {
            "provider": provider,
            "badge_mode": saved.get(provider, default),
            "connected": provider in connected_providers,
        }
        for provider, default in INTEGRATION_BADGE_DEFAULTS
    ]


def update_integration_badge_preference(
    db: Session,
    *,
    provider: str,
    badge_mode: str,
    actor_id: int,
) -> dict[str, str]:
    defaults = dict(INTEGRATION_BADGE_DEFAULTS)
    if provider not in defaults:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intégration introuvable.")
    if badge_mode not in {"connect", "recommended"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choix de badge invalide.")

    preference = db.get(PlatformIntegrationPreferenceRecord, provider)
    if preference is None:
        preference = PlatformIntegrationPreferenceRecord(provider=provider, badge_mode=badge_mode)
        db.add(preference)
    else:
        preference.badge_mode = badge_mode
    preference.updated_by_user_id = actor_id
    db.commit()
    return {"provider": provider, "badge_mode": badge_mode}
