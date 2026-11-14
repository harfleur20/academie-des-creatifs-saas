from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.money import money_label
from app.models.entities import (
    CertificateRecord,
    FormationRecord,
    FormationSessionRecord,
    OrderInvoiceRecord,
    OrganizationStudentProfileRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.services.class_certificates import _verification_token


def _hex(value: str | None, fallback: str) -> HexColor:
    try:
        return HexColor(value or fallback)
    except Exception:
        return HexColor(fallback)


def _money(amount: int, currency: str) -> str:
    return money_label(amount, currency)


def _safe_asset_bytes(url: str | None) -> bytes | None:
    if not url:
        return None
    backend_prefix = settings.backend_public_url.rstrip("/") + "/uploads/"
    if url.startswith(backend_prefix):
        relative = url[len(backend_prefix):].lstrip("/")
        root = Path(__file__).resolve().parents[2] / "uploads"
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            return None
        if path.is_file():
            return path.read_bytes()
        return None

    r2 = settings.r2_public_base_url.rstrip("/")
    if r2 and url.startswith(r2 + "/"):
        try:
            response = httpx.get(url, timeout=5.0, follow_redirects=False)
            if response.status_code < 400 and len(response.content) <= 5 * 1024 * 1024:
                return response.content
        except Exception:
            return None
    return None


def _draw_image(
    pdf: canvas.Canvas,
    url: str | None,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    raw = _safe_asset_bytes(url)
    if not raw:
        return
    try:
        pdf.drawImage(
            ImageReader(BytesIO(raw)),
            x,
            y,
            width=width,
            height=height,
            preserveAspectRatio=True,
            mask="auto",
            anchor="c",
        )
    except Exception:
        return


def _wrap_lines(text: str, *, font: str, size: float, max_width: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_wrapped(
    pdf: canvas.Canvas,
    text: str,
    *,
    x: float,
    y: float,
    max_width: float,
    font: str = "Helvetica",
    size: float = 10,
    leading: float = 14,
    color=colors.black,
) -> float:
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    for line in _wrap_lines(text, font=font, size=size, max_width=max_width):
        pdf.drawString(x, y, line)
        y -= leading
    return y


def build_invoice_pdf(
    db: Session,
    invoice: OrderInvoiceRecord,
) -> tuple[str, bytes]:
    order = db.get(StudentOrderRecord, invoice.order_id)
    if order is None:
        raise HTTPException(404, "Commande introuvable.")
    user = db.get(UserRecord, order.user_id)
    formation = db.get(FormationRecord, order.formation_id)
    session = db.get(FormationSessionRecord, order.session_id)
    profile = db.scalar(
        select(OrganizationStudentProfileRecord).where(
            OrganizationStudentProfileRecord.organization_id == order.organization_id,
            OrganizationStudentProfileRecord.user_id == order.user_id,
        )
    )
    snapshot = dict(invoice.branding_snapshot or {})
    primary = _hex(snapshot.get("primary_color"), "#1F2559")
    accent = _hex(snapshot.get("accent_color"), "#131735")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFillColor(primary)
    pdf.rect(0, height - 92, width, 92, stroke=0, fill=1)
    _draw_image(pdf, snapshot.get("logo_url"), 38, height - 82, 110, 64)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawRightString(width - 38, height - 46, str(snapshot.get("school_name") or "École"))
    pdf.setFont("Helvetica", 8.5)
    pdf.drawRightString(width - 38, height - 62, str(snapshot.get("contact_email") or ""))
    pdf.drawRightString(width - 38, height - 76, str(snapshot.get("contact_phone") or ""))

    y = height - 126
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 21)
    pdf.drawString(38, y, "FACTURE / REÇU")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(width - 38, y + 2, invoice.invoice_number)
    y -= 30

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.drawString(38, y, f"Émise le {invoice.issued_at:%d/%m/%Y}")
    pdf.drawRightString(width - 38, y, f"Commande {order.order_number}")
    y -= 30

    pdf.setFillColor(colors.HexColor("#F7F9FC"))
    pdf.roundRect(38, y - 88, width - 76, 88, 8, stroke=0, fill=1)
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(52, y - 20, "ÉTUDIANT")
    pdf.drawString(width / 2 + 4, y - 20, "FORMATION")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(52, y - 39, user.full_name if user else "—")
    pdf.drawString(52, y - 54, user.email if user else "—")
    pdf.drawString(52, y - 69, f"Matricule : {profile.student_code if profile else '—'}")
    pdf.drawString(width / 2 + 4, y - 39, formation.title if formation else "—")
    pdf.drawString(width / 2 + 4, y - 54, f"Session : {session.label if session else '—'}")
    if session:
        pdf.drawString(
            width / 2 + 4,
            y - 69,
            f"{session.start_date:%d/%m/%Y} - {session.end_date:%d/%m/%Y}",
        )
    y -= 118

    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.drawString(38, y, "LIBELLÉ")
    pdf.drawRightString(width - 38, y, "MONTANT")
    y -= 12
    pdf.setStrokeColor(colors.HexColor("#E2E8F0"))
    pdf.line(38, y, width - 38, y)
    y -= 23

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 10)
    label = formation.title if formation else "Formation"
    if invoice.installment_id:
        label += " - échéance"
    pdf.drawString(38, y, label[:70])
    pdf.drawRightString(width - 38, y, _money(invoice.amount_cents, invoice.currency))
    y -= 30

    pdf.setStrokeColor(colors.HexColor("#E2E8F0"))
    pdf.line(width - 245, y, width - 38, y)
    y -= 22
    pdf.setFont("Helvetica-Bold", 13)
    pdf.setFillColor(primary)
    pdf.drawRightString(width - 38, y, f"PAYÉ : {_money(invoice.amount_cents, invoice.currency)}")
    y -= 44

    legal_lines = [
        str(snapshot.get("legal_name") or snapshot.get("school_name") or ""),
        str(snapshot.get("legal_address") or ""),
    ]
    reg = snapshot.get("registration_number")
    tax = snapshot.get("tax_number")
    if reg:
        legal_lines.append(f"Immatriculation : {reg}")
    if tax:
        legal_lines.append(f"Identifiant fiscal : {tax}")
    legal_text = "\n".join(line for line in legal_lines if line)
    for line in legal_text.splitlines():
        y = _draw_wrapped(
            pdf,
            line,
            x=38,
            y=y,
            max_width=width - 76,
            size=8.5,
            leading=12,
            color=colors.HexColor("#64748B"),
        )

    footer = str(snapshot.get("invoice_footer") or "")
    if footer:
        y -= 6
        _draw_wrapped(
            pdf,
            footer,
            x=38,
            y=y,
            max_width=width - 76,
            size=8,
            leading=11,
            color=colors.HexColor("#64748B"),
        )

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(colors.HexColor("#94A3B8"))
    pdf.drawCentredString(
        width / 2,
        24,
        f"Document émis par {snapshot.get('school_name') or 'l’école'} - Powered by Académie des Créatifs",
    )
    pdf.showPage()
    pdf.save()
    return f"{invoice.invoice_number}.pdf", buffer.getvalue()


def build_certificate_pdf(
    certificate: CertificateRecord,
) -> tuple[str, bytes]:
    snapshot = dict(certificate.branding_snapshot or {})
    document = dict(snapshot.get("document") or {})
    primary = _hex(snapshot.get("primary_color"), "#1F2559")
    secondary = _hex(snapshot.get("secondary_color"), "#18A7A3")
    accent = _hex(snapshot.get("accent_color"), "#131735")

    buffer = BytesIO()
    page = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=page)
    width, height = page

    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setStrokeColor(primary)
    pdf.setLineWidth(8)
    pdf.rect(18, 18, width - 36, height - 36, stroke=1, fill=0)
    pdf.setStrokeColor(secondary)
    pdf.setLineWidth(2)
    pdf.rect(28, 28, width - 56, height - 56, stroke=1, fill=0)

    _draw_image(pdf, snapshot.get("logo_url"), 54, height - 116, 150, 68)
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(width - 54, height - 72, str(snapshot.get("school_name") or "École"))

    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawCentredString(width / 2, height - 148, "CERTIFICAT DE FIN DE FORMATION")
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, height - 173, "Nous certifions que")

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(width / 2, height - 218, certificate.student_name.upper())

    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, height - 247, "a suivi et validé avec succès la formation")

    pdf.setFillColor(primary)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(width / 2, height - 286, certificate.formation_title)

    session_label = document.get("session_label")
    dates = ""
    if document.get("session_start_date") and document.get("session_end_date"):
        dates = f"{document['session_start_date']} - {document['session_end_date']}"
    details = " · ".join(item for item in [session_label, dates] if item)
    if details:
        pdf.setFillColor(colors.HexColor("#64748B"))
        pdf.setFont("Helvetica", 10)
        pdf.drawCentredString(width / 2, height - 312, details)

    code = document.get("student_code")
    info_y = 108
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(54, info_y + 42, f"N° certificat : {certificate.certificate_number}")
    if code:
        pdf.drawString(54, info_y + 26, f"Matricule : {code}")
    if document.get("training_hours"):
        pdf.drawString(54, info_y + 10, f"Volume de formation : {document['training_hours']} h")
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.drawString(54, info_y - 7, f"Émis le {certificate.issued_at:%d/%m/%Y}")

    signature_x = width - 300
    _draw_image(pdf, snapshot.get("signature_url"), signature_x, 90, 105, 48)
    _draw_image(pdf, snapshot.get("stamp_url"), width - 174, 76, 90, 68)
    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(signature_x + 52, 75, str(snapshot.get("signer_name") or ""))
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.drawCentredString(signature_x + 52, 62, str(snapshot.get("signer_title") or ""))

    verification_url = (
        f"{settings.frontend_url}/certificates/verify/"
        f"{_verification_token(certificate)}"
    )
    widget = qr.QrCodeWidget(verification_url)
    bounds = widget.getBounds()
    qr_size = 74
    scale_x = qr_size / (bounds[2] - bounds[0])
    scale_y = qr_size / (bounds[3] - bounds[1])
    drawing = Drawing(qr_size, qr_size, transform=[scale_x, 0, 0, scale_y, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, width / 2 - qr_size / 2, 52)
    pdf.setFillColor(colors.HexColor("#64748B"))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawCentredString(width / 2, 44, "Scanner pour vérifier l’authenticité")

    footer = str(snapshot.get("certificate_footer") or "")
    if footer:
        _draw_wrapped(
            pdf,
            footer,
            x=54,
            y=46,
            max_width=250,
            size=7,
            leading=9,
            color=colors.HexColor("#64748B"),
        )

    pdf.setFont("Helvetica", 6.5)
    pdf.setFillColor(colors.HexColor("#94A3B8"))
    pdf.drawRightString(width - 54, 36, "Powered by Académie des Créatifs")

    pdf.showPage()
    pdf.save()
    return f"{certificate.certificate_number}.pdf", buffer.getvalue()
