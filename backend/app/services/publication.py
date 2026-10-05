from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord, FormationSessionRecord, OrganizationLegalProfileRecord, OrganizationPublicSiteRecord, OrganizationRecord


def valid_cover_url(value: str | None) -> bool:
    if not value or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and parsed.path.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        )
    except ValueError:
        return False


def formation_content_issues(formation: FormationRecord) -> list[str]:
    issues: list[str] = []
    if not formation.description.strip():
        issues.append("Ajoutez une description.")
    if not valid_cover_url(formation.cover_image_url):
        issues.append("Ajoutez une photo de couverture.")
    if formation.price_cents <= 0:
        issues.append("Définissez un prix supérieur à zéro.")
    if not formation.public_program.strip():
        issues.append("Renseignez le programme public.")
    return issues


def formation_publication_issues(db: Session, formation: FormationRecord) -> list[str]:
    issues = formation_content_issues(formation)
    if formation.format_type in {"live", "presentiel"}:
        has_session = db.scalar(
            select(FormationSessionRecord.id).where(
                FormationSessionRecord.organization_id == formation.organization_id,
                FormationSessionRecord.formation_id == formation.id,
                FormationSessionRecord.status.in_(["planned", "open"]),
                FormationSessionRecord.end_date >= datetime.now(UTC).date(),
            ).limit(1)
        ) is not None
        if not has_session:
            issues.append("Créez une session à venir.")
    return issues


def billing_readiness_issues(legal: OrganizationLegalProfileRecord) -> list[str]:
    issues: list[str] = []
    if not legal.legal_name.strip():
        issues.append("Renseignez la raison sociale pour les factures.")
    if not legal.legal_address.strip():
        issues.append("Renseignez l'adresse légale pour les factures.")
    if not (legal.invoice_email or "").strip():
        issues.append("Renseignez l'email de facturation.")
    if len(legal.default_currency.strip()) != 3 or not legal.default_currency.isalpha():
        issues.append("Choisissez une devise de facturation valide.")
    return issues


def site_publication_issues(site: OrganizationPublicSiteRecord, legal: OrganizationLegalProfileRecord, org: OrganizationRecord) -> list[str]:
    fields = (
        ("legal_notice", "Renseignez les mentions légales."),
        ("sales_terms", "Renseignez les conditions générales de vente."),
        ("privacy_policy", "Renseignez la politique de confidentialité."),
        ("refund_policy", "Renseignez la politique de remboursement."),
    )
    issues = [message for key, message in fields if not getattr(site, key).strip()]
    if not (org.contact_email or "").strip():
        issues.append("Renseignez l'email de contact de l'école.")
    if not (org.subdomain or "").strip():
        issues.append("Configurez le sous-domaine de l'école.")
    if not site.student_code_prefix.strip() or not site.student_code_prefix_confirmed_at:
        issues.append("Confirmez le préfixe des matricules.")
    issues.extend(billing_readiness_issues(legal))
    return issues
