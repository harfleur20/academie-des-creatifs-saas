from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import (
    OrganizationCertificationProfileRecord,
    OrganizationCommunicationProfileRecord,
    OrganizationLegalProfileRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
)
from app.schemas.commerce import (
    CertificationProfilePayload,
    CommunicationProfilePayload,
    LegalProfilePayload,
    PublicSiteConfigPayload,
    SchoolIdentityPayload,
    SchoolIdentityRead,
)
from app.services.tenancy import TenantContext
from app.services.publication import site_publication_issues
from app.services.school_setup import require_identity_address


DEFAULT_PRIMARY = "#1F2559"
DEFAULT_SECONDARY = "#18A7A3"
DEFAULT_ACCENT = "#131735"
SUPPORTED_DEFAULT_CURRENCIES = frozenset({
    "XAF", "XOF", "EUR", "USD", "GBP", "CAD", "CHF", "MAD", "NGN", "ZAR", "GHS", "AUD", "CNY", "JPY",
})


def _prefix_from_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.upper()).encode("ascii", "ignore").decode("ascii")
    words = [part for part in re.split(r"[^A-Z]+", normalized) if part]
    if not words:
        return "AC"
    if len(words) >= 2:
        return words[0][0] + words[1][0]
    return words[0][:2] if len(words[0]) >= 2 else "AC"


def _public_site_defaults(org: OrganizationRecord) -> dict:
    return {
        "site_name": org.name,
        "tagline": "Formez-vous. Créez. Évoluez.",
        "seo_description": "",
        "favicon_url": None,
        "hero_title": f"Bienvenue chez {org.name}",
        "hero_subtitle": "Découvrez nos formations et rejoignez la prochaine session.",
        "hero_cta_label": "Découvrir nos formations",
        "hero_image_url": None,
        "auth_background_image_url": None,
        "auth_show_school_name": True,
        "announcement_enabled": False,
        "announcement_text": "",
        "announcement_background_color": "#FFF4E7",
        "announcement_text_color": "#7C4200",
        "about_title": f"À propos de {org.name}",
        "about_text": "",
        "contact_phone": None,
        "contact_email": org.contact_email,
        "contact_address": None,
        "social_links": {},
        "footer_text": "",
        "legal_notice": "",
        "sales_terms": "",
        "privacy_policy": "",
        "refund_policy": "",
        "font_heading": "Inter",
        "font_body": "Inter",
        "font_size_scale": 100,
        "heading_size_scale": 100,
        "subtitle_size_scale": 100,
        "student_code_prefix": _prefix_from_name(org.name),
        "is_published": False,
    }


def _legal_defaults(org: OrganizationRecord) -> dict:
    return {
        "legal_name": org.name,
        "legal_address": "",
        "registration_number": "",
        "tax_number": "",
        "invoice_email": org.contact_email,
        "invoice_phone": None,
        "default_currency": "XAF",
        "invoice_footer": "",
    }


def _communication_defaults(org: OrganizationRecord) -> dict:
    return {
        "sender_name": org.name,
        "reply_to_email": org.contact_email,
        "email_signature": f"L'équipe {org.name}",
        "whatsapp_signature": org.name,
        "whatsapp_phone": None,
    }


def _certification_defaults(org: OrganizationRecord) -> dict:
    return {
        "signer_name": "",
        "signer_title": "",
        "signature_url": None,
        "stamp_url": None,
        "certificate_footer": "",
    }


IdentityRecord = (
    OrganizationPublicSiteRecord
    | OrganizationLegalProfileRecord
    | OrganizationCommunicationProfileRecord
    | OrganizationCertificationProfileRecord
)

IDENTITY_RECORDS = (
    (OrganizationPublicSiteRecord, _public_site_defaults),
    (OrganizationLegalProfileRecord, _legal_defaults),
    (OrganizationCommunicationProfileRecord, _communication_defaults),
    (OrganizationCertificationProfileRecord, _certification_defaults),
)


def _find_identity_record(db: Session, model: type[IdentityRecord], organization_id: int) -> IdentityRecord | None:
    return db.scalar(select(model).where(model.organization_id == organization_id))


def _get_or_create_identity_record(
    db: Session,
    model: type[IdentityRecord],
    org: OrganizationRecord,
    defaults,
) -> tuple[IdentityRecord, bool]:
    record = _find_identity_record(db, model, org.id)
    if record is not None:
        return record, False
    try:
        # The first pages of a new school load in parallel and may all find the record missing.
        # A savepoint lets the loser keep its pending work and reuse the winner's row.
        with db.begin_nested():
            record = model(organization_id=org.id, **defaults(org))
            db.add(record)
    except IntegrityError:
        record = _find_identity_record(db, model, org.id)
        if record is None:
            raise
        return record, False
    return record, True


def get_or_create_identity_records(
    db: Session,
    org: OrganizationRecord,
) -> tuple[
    OrganizationPublicSiteRecord,
    OrganizationLegalProfileRecord,
    OrganizationCommunicationProfileRecord,
    OrganizationCertificationProfileRecord,
]:
    records = []
    created = False
    for model, defaults in IDENTITY_RECORDS:
        record, inserted = _get_or_create_identity_record(db, model, org, defaults)
        records.append(record)
        created = created or inserted
    if created:
        db.commit()
        for record in records:
            db.refresh(record)
    site, legal, comm, cert = records
    return site, legal, comm, cert


def _identity_read(
    org: OrganizationRecord,
    site: OrganizationPublicSiteRecord,
    legal: OrganizationLegalProfileRecord,
    comm: OrganizationCommunicationProfileRecord,
    cert: OrganizationCertificationProfileRecord,
) -> SchoolIdentityRead:
    return SchoolIdentityRead(
        organization_id=org.id,
        organization_name=org.name,
        slug=org.slug,
        subdomain=org.subdomain,
        public_site=PublicSiteConfigPayload(
            site_name=site.site_name,
            tagline=site.tagline,
            seo_description=site.seo_description,
            logo_url=org.logo_url,
            favicon_url=site.favicon_url,
            primary_color=org.primary_color,
            secondary_color=org.secondary_color,
            accent_color=org.accent_color,
            font_heading=site.font_heading,
            font_body=site.font_body,
            font_size_scale=site.font_size_scale,
            heading_size_scale=site.heading_size_scale,
            subtitle_size_scale=site.subtitle_size_scale,
            hero_title=site.hero_title,
            hero_subtitle=site.hero_subtitle,
            hero_cta_label=site.hero_cta_label,
            hero_image_url=site.hero_image_url,
            auth_background_image_url=site.auth_background_image_url,
            auth_show_school_name=site.auth_show_school_name,
            announcement_enabled=site.announcement_enabled,
            announcement_text=site.announcement_text,
            announcement_background_color=site.announcement_background_color,
            announcement_text_color=site.announcement_text_color,
            about_title=site.about_title,
            about_text=site.about_text,
            contact_phone=site.contact_phone,
            contact_email=site.contact_email,
            contact_address=site.contact_address,
            social_links=site.social_links or {},
            footer_text=site.footer_text,
            legal_notice=site.legal_notice,
            sales_terms=site.sales_terms,
            privacy_policy=site.privacy_policy,
            refund_policy=site.refund_policy,
            student_code_prefix=site.student_code_prefix,
            student_code_prefix_confirmed=bool(site.student_code_prefix_confirmed_at),
            is_published=site.is_published,
        ),
        legal=LegalProfilePayload(
            legal_name=legal.legal_name,
            legal_address=legal.legal_address,
            registration_number=legal.registration_number,
            tax_number=legal.tax_number,
            invoice_email=legal.invoice_email,
            invoice_phone=legal.invoice_phone,
            default_currency=legal.default_currency,
            invoice_footer=legal.invoice_footer,
        ),
        communications=CommunicationProfilePayload(
            sender_name=comm.sender_name,
            reply_to_email=comm.reply_to_email,
            email_signature=comm.email_signature,
            whatsapp_signature=comm.whatsapp_signature,
            whatsapp_phone=comm.whatsapp_phone,
        ),
        certification=CertificationProfilePayload(
            signer_name=cert.signer_name,
            signer_title=cert.signer_title,
            signature_url=cert.signature_url,
            stamp_url=cert.stamp_url,
            certificate_footer=cert.certificate_footer,
        ),
    )


def get_school_identity(
    db: Session,
    tenant: TenantContext,
) -> SchoolIdentityRead:
    if not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès gestion requis.")
    site, legal, comm, cert = get_or_create_identity_records(
        db,
        tenant.organization,
    )
    return _identity_read(tenant.organization, site, legal, comm, cert)


def update_school_identity(
    db: Session,
    tenant: TenantContext,
    payload: SchoolIdentityPayload,
) -> SchoolIdentityRead:
    if tenant.support_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Le mode support est en lecture seule.")
    if not tenant.organization_roles.intersection({"owner", "admin"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seuls le propriétaire ou un administrateur peuvent modifier l'identité.")
    if payload.legal.default_currency.strip().upper() not in SUPPORTED_DEFAULT_CURRENCIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Cette devise n’est pas prise en charge pour l’affichage du site public.",
        )

    org = tenant.organization
    site, legal, comm, cert = get_or_create_identity_records(db, org)
    p = payload.public_site
    allowed_fonts = {"Inter", "Arial", "Georgia", "Verdana", "Trebuchet MS", "Times New Roman"}
    if p.font_heading not in allowed_fonts or p.font_body not in allowed_fonts:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choisissez les polices dans la liste proposée.")
    if p.announcement_enabled and not p.announcement_text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Renseignez le texte du bandeau avant de l'activer.")

    next_prefix = (p.student_code_prefix.strip() or _prefix_from_name(org.name)).upper()
    if p.student_code_prefix_confirmed and not p.student_code_prefix.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Renseignez le préfixe des matricules.")
    prefix_is_being_changed = next_prefix != site.student_code_prefix
    prefix_is_being_confirmed = p.student_code_prefix_confirmed and not site.student_code_prefix_confirmed_at
    if (prefix_is_being_changed or prefix_is_being_confirmed) and not re.fullmatch(r"[A-Z]{2}", next_prefix):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Le préfixe des matricules doit contenir exactement deux lettres.",
        )
    if p.student_code_prefix_confirmed and not site.student_code_prefix_confirmed_at:
        require_identity_address(org)
    if site.student_code_prefix_confirmed_at and next_prefix != site.student_code_prefix:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Le préfixe est définitif après confirmation et ne peut plus être modifié.",
        )

    org.logo_url = p.logo_url.strip() if p.logo_url else None
    org.primary_color = p.primary_color.upper()
    org.secondary_color = p.secondary_color.upper()
    org.accent_color = p.accent_color.upper()

    site_values = p.model_dump(
        exclude={"logo_url", "primary_color", "secondary_color", "accent_color", "student_code_prefix_confirmed"}
    )
    for key, value in site_values.items():
        if isinstance(value, str):
            value = value.strip()
        if key in {"announcement_background_color", "announcement_text_color"}:
            value = value.upper()
        if key == "student_code_prefix":
            value = next_prefix
        setattr(site, key, value)

    if p.student_code_prefix_confirmed and not site.student_code_prefix_confirmed_at:
        site.student_code_prefix_confirmed_at = datetime.now(UTC)

    for record, values in (
        (legal, payload.legal.model_dump()),
        (comm, payload.communications.model_dump()),
        (cert, payload.certification.model_dump()),
    ):
        for key, value in values.items():
            if isinstance(value, str):
                value = value.strip()
            if key == "default_currency" and value:
                value = value.upper()
            setattr(record, key, value)

    if site.is_published:
        issues = site_publication_issues(site, legal, org)
        if issues:
            db.rollback()
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Publication du site impossible : " + " ".join(issues))

    db.commit()
    return _identity_read(org, site, legal, comm, cert)


def branding_snapshot(
    db: Session,
    org: OrganizationRecord,
) -> dict:
    site, legal, comm, cert = get_or_create_identity_records(db, org)
    return {
        "organization_id": org.id,
        "school_name": site.site_name or org.name,
        "organization_name": org.name,
        "logo_url": org.logo_url,
        "primary_color": org.primary_color or DEFAULT_PRIMARY,
        "secondary_color": org.secondary_color or DEFAULT_SECONDARY,
        "accent_color": org.accent_color or DEFAULT_ACCENT,
        "contact_email": site.contact_email or org.contact_email,
        "contact_phone": site.contact_phone,
        "contact_address": site.contact_address,
        "legal_name": legal.legal_name or org.name,
        "legal_address": legal.legal_address,
        "registration_number": legal.registration_number,
        "tax_number": legal.tax_number,
        "invoice_email": legal.invoice_email,
        "invoice_phone": legal.invoice_phone,
        "invoice_footer": legal.invoice_footer,
        "sender_name": comm.sender_name or org.name,
        "reply_to_email": comm.reply_to_email,
        "email_signature": comm.email_signature,
        "whatsapp_signature": comm.whatsapp_signature,
        "signer_name": cert.signer_name,
        "signer_title": cert.signer_title,
        "signature_url": cert.signature_url,
        "stamp_url": cert.stamp_url,
        "certificate_footer": cert.certificate_footer,
        "student_code_prefix": site.student_code_prefix or _prefix_from_name(org.name),
        "captured_at": datetime.now(UTC).isoformat(),
    }
