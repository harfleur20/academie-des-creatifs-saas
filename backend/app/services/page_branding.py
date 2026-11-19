"""The first HTML of a page already carries its school's name, icon and description.

The app applies a school's identity once its code runs; until then the browser shows what
the HTML says, which was the platform's name and icon for one to three seconds on every
school page. Writing the school in the HTML removes that, and link previews (WhatsApp,
Facebook…) show the school too. Read only: a page load never writes to the database.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hmac
import html
import logging
import re
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    CertificateRecord,
    OrganizationInvitationRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
)
from app.services.class_certificates import _verification_token
from app.services.organization_domains import resolve_organization_for_hostname
from app.services.organization_management import _token_hash
from app.services.public_school_slug import resolve_public_organization

logger = logging.getLogger(__name__)

# The workspaces' titles, as the app writes them: "<school> - Enseignant".
WORKSPACE_SECTIONS = (("/app/teacher", "Enseignant"), ("/app/student", "Étudiant"))
# Pages that belong to a school whose name is not known here: no platform name on them.
SCHOOL_ONLY_PREFIXES = ("/app", "/invite/", "/certificates/")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class PageHead:
    title: str
    icon: str | None = None
    description: str | None = None
    image: str | None = None
    locale: str | None = None
    # Tells the app the page already carries a school: it shows no placeholder over it.
    school: str | None = None


NEUTRAL = PageHead(title="")


def _display_name(org: OrganizationRecord, site: OrganizationPublicSiteRecord | None) -> str:
    return (site.site_name if site else "") or org.name


def _site(db: Session, org: OrganizationRecord) -> OrganizationPublicSiteRecord | None:
    return db.scalar(select(OrganizationPublicSiteRecord).where(OrganizationPublicSiteRecord.organization_id == org.id))


def school_head(db: Session, org: OrganizationRecord, *, path: str = "/") -> PageHead:
    site = _site(db, org)
    name = _display_name(org, site)
    title = name
    if path.startswith("/app"):
        section = next((label for prefix, label in WORKSPACE_SECTIONS if path.startswith(prefix)), "Gestion")
        title = f"{name} - {section}"
    description = ((site.seo_description or site.tagline) if site else "") or name
    return PageHead(
        title=title,
        icon=(site.favicon_url if site else None) or org.logo_url,
        description=description,
        image=org.logo_url,
        locale=org.locale,
        school=org.slug,
    )


def _invitation_school(db: Session, token: str) -> OrganizationRecord | None:
    invitation = db.scalar(
        select(OrganizationInvitationRecord).where(OrganizationInvitationRecord.token_hash == _token_hash(token))
    )
    return db.get(OrganizationRecord, invitation.organization_id) if invitation else None


def _certificate_head(db: Session, token: str) -> PageHead | None:
    try:
        certificate_id = int(token.split(".", 1)[0])
    except ValueError:
        return None
    row = db.get(CertificateRecord, certificate_id)
    if row is None or row.status != "valid" or not hmac.compare_digest(_verification_token(row), token):
        return None
    # As the verification page shows it: the school as it was when the certificate was issued.
    snapshot = dict(row.branding_snapshot or {})
    org = db.get(OrganizationRecord, row.organization_id)
    name = str(snapshot.get("school_name") or (org.name if org else ""))
    if not name:
        return None
    logo = snapshot.get("logo_url") or None
    return PageHead(title=name, icon=logo, description=name, image=logo, locale=org.locale if org else None,
                    school=org.slug if org else None)


def _invitation_token(path: str, query: Mapping[str, str]) -> str | None:
    if path.startswith("/invite/"):
        return path.removeprefix("/invite/").strip("/") or None
    # The login page an invitation sends to: /login?return=/invite/<token>
    back = query.get("return", "") if path == "/login" else ""
    if not back.startswith("/invite/"):
        return None
    return back.removeprefix("/invite/").split("?", 1)[0].strip("/") or None


def _host_school(db: Session, host: str) -> OrganizationRecord | None:
    platform_host = (urlsplit(settings.frontend_url).hostname or "").lower()
    if not host or host in LOCAL_HOSTS or host == platform_host:
        return None
    try:
        resolved = resolve_organization_for_hostname(db, hostname=host)
    except Exception:  # an address the domain rules refuse is simply not a school's
        return None
    return resolved[0] if resolved else None


def page_head(db: Session, *, host: str, path: str, query: Mapping[str, str]) -> PageHead | None:
    """The head a page's first HTML gets; None keeps the platform's own."""
    token = _invitation_token(path, query)
    if token:
        org = _invitation_school(db, token)
        return school_head(db, org) if org else NEUTRAL
    if path.startswith("/certificates/verify/"):
        return _certificate_head(db, path.removeprefix("/certificates/verify/").strip("/")) or NEUTRAL

    key = query.get("school", "") if path == "/login" else ""
    if not key and path.startswith("/school/"):
        key = path.split("/")[2]
    if key:
        org = resolve_public_organization(db, key)
        if org is not None:
            return school_head(db, org)

    org = _host_school(db, host.lower())
    if org is not None:
        return school_head(db, org, path=path)
    if path.startswith(SCHOOL_ONLY_PREFIXES):
        return NEUTRAL
    return None


def _set(pattern: str, replacement: str, document: str) -> str:
    # A function as the replacement: a school's name is never read as a regex group.
    return re.sub(pattern, lambda _match: replacement, document, count=1, flags=re.S)


def render_head(document: str, head: PageHead) -> str:
    def attr(value: str) -> str:
        return html.escape(value, quote=True)

    document = _set(r"<title>.*?</title>", f"<title>{html.escape(head.title)}</title>", document)
    # No icon at all rather than the platform's: "data:," also spares a /favicon.ico request.
    icon = f'<link rel="icon" href="{attr(head.icon)}" />' if head.icon else '<link rel="icon" href="data:," />'
    document = _set(r'<link\s+rel="icon"[^>]*>', icon, document)
    if head.description:
        document = _set(r'<meta\s+name="description"[^>]*>', f'<meta name="description" content="{attr(head.description)}" />', document)
    if head.locale:
        document = _set(r'<html lang="[^"]*"', f'<html lang="{attr(head.locale)}"', document)

    extra = []
    if head.school:
        extra.append(f'<meta name="academie-school" content="{attr(head.school)}" />')
        extra.append('<meta property="og:type" content="website" />')
        extra.append(f'<meta property="og:title" content="{attr(head.title)}" />')
        if head.description:
            extra.append(f'<meta property="og:description" content="{attr(head.description)}" />')
        if head.image and head.image.startswith(("https://", "http://")):
            extra.append(f'<meta property="og:image" content="{attr(head.image)}" />')
    if extra:
        document = _set(r"</head>", "\n    ".join(extra) + "\n  </head>", document)
    return document


def branded_index(
    document: str,
    *,
    host: str,
    path: str,
    query: Mapping[str, str],
    session_factory: Callable[[], Session],
) -> str:
    """index.html for this page. Branding never blocks a page: any failure serves it as built."""
    try:
        with session_factory() as db:
            head = page_head(db, host=host, path=path, query=query)
    except Exception:
        logger.exception("School branding of %s%s failed", host, path)
        return document
    return document if head is None else render_head(document, head)
