"""The transcript as a PDF, in the school's colours (app/services/transcripts.py)."""
from __future__ import annotations

import re
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.schemas.transcripts import TranscriptRead
from app.services.school_documents import _hex, _safe_asset_bytes, _wrap_lines

MUTED = colors.HexColor("#64748B")
LIGHT = colors.HexColor("#94A3B8")
INK = colors.HexColor("#131735")
LINE = colors.HexColor("#E2E8F0")
MARGIN = 46
BOTTOM = 70
MAX_ASSET_BYTES = 5 * 1024 * 1024


def _asset_bytes(url: str | None) -> bytes | None:
    """An uploaded asset, or one of the demo images served with the frontend (frontend/public/demo)."""
    raw = _safe_asset_bytes(url)
    if raw or not url:
        return raw
    path = urlparse(url).path
    if not path.startswith("/demo/"):
        return None
    roots = [Path(settings.frontend_dist_dir)] if settings.frontend_dist_dir else []
    roots.append(Path(__file__).resolve().parents[3] / "frontend" / "public")
    for root in roots:
        candidate = (root / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file() and candidate.stat().st_size <= MAX_ASSET_BYTES:
            return candidate.read_bytes()
    return None


def _draw_asset(pdf: canvas.Canvas, url: str | None, x: float, y: float, width: float, height: float) -> bool:
    raw = _asset_bytes(url)
    if not raw:
        return False
    try:
        pdf.drawImage(ImageReader(BytesIO(raw)), x, y, width=width, height=height,
                      preserveAspectRatio=True, mask="auto", anchor="sw")
        return True
    except Exception:
        return False


def _number(value: float, digits: int = 2) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _day(value) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def transcript_filename(transcript: TranscriptRead) -> str:
    base = f"releve-{transcript.student_code or transcript.student_name}-{transcript.formation_title}"
    ascii_name = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", ascii_name).strip("-").lower()[:90] + ".pdf"


class _Page:
    def __init__(self, transcript: TranscriptRead):
        self.t = transcript
        self.buffer = BytesIO()
        self.pdf = canvas.Canvas(self.buffer, pagesize=A4)
        self.pdf.setTitle(f"Relevé de notes · {transcript.student_name} · {transcript.formation_title}")
        self.width, self.height = A4
        self.primary = _hex(None, "#35409A")
        self.number = 0
        self.y = 0.0

    def colours(self, primary: str | None, secondary: str | None):
        self.primary = _hex(primary, "#35409A")
        self.secondary = _hex(secondary, "#0B8A83")

    def start(self, *, first: bool) -> None:
        pdf, width, height, t = self.pdf, self.width, self.height, self.t
        self.number += 1
        pdf.setFillColor(self.primary)
        pdf.rect(0, height - 8, width, 8, stroke=0, fill=1)
        if first:
            has_logo = _draw_asset(pdf, t.logo_url, MARGIN, height - 86, 120, 52)
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawRightString(width - MARGIN, height - 50, t.school_name)
            pdf.setFont("Helvetica", 8.5)
            pdf.setFillColor(MUTED)
            details = [item for item in (t.legal_name if t.legal_name != t.school_name else None, t.legal_address) if item]
            for index, line in enumerate(details[:2]):
                pdf.drawRightString(width - MARGIN, height - 64 - index * 11, line)
            if not has_logo:
                pdf.setFillColor(self.primary)
                pdf.setFont("Helvetica-Bold", 13)
                pdf.drawString(MARGIN, height - 50, t.school_name[:40])
            self.y = height - 128
        else:
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 8.5)
            pdf.drawString(MARGIN, height - 36, f"Relevé de notes · {t.student_name} · {t.formation_title}"[:110])
            self.y = height - 62
        self.footer()

    def footer(self) -> None:
        pdf, t = self.pdf, self.t
        pdf.setStrokeColor(LINE)
        pdf.setLineWidth(0.6)
        pdf.line(MARGIN, 52, self.width - MARGIN, 52)
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillColor(LIGHT)
        pdf.drawString(MARGIN, 40, f"Édité le {t.issued_at:%d/%m/%Y} · Page {self.number}")
        if not t.white_label:
            pdf.drawRightString(self.width - MARGIN, 40, "Édité avec Académie des Créatifs")

    def need(self, space: float) -> None:
        if self.y - space < BOTTOM:
            self.pdf.showPage()
            self.start(first=False)


def build_transcript_pdf(transcript: TranscriptRead, *, primary_color: str | None = None,
                         secondary_color: str | None = None, signature_url: str | None = None,
                         stamp_url: str | None = None) -> tuple[str, bytes]:
    page = _Page(transcript)
    page.colours(primary_color, secondary_color)
    page.start(first=True)
    pdf, t, width = page.pdf, transcript, page.width
    final = t.status == "final"

    # Title and status.
    pdf.setFillColor(page.primary)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(MARGIN, page.y, "RELEVÉ DE NOTES")
    status_text = "DÉFINITIF" if final else "PROVISOIRE"
    status_colour = page.secondary if final else colors.HexColor("#B45309")
    pdf.setFont("Helvetica-Bold", 8.5)
    chip_width = pdf.stringWidth(status_text, "Helvetica-Bold", 8.5) + 18
    pdf.setFillColor(status_colour)
    pdf.roundRect(width - MARGIN - chip_width, page.y - 2, chip_width, 18, 9, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.drawCentredString(width - MARGIN - chip_width / 2, page.y + 3.5, status_text)
    page.y -= 30

    # Who and what.
    identity = [
        ("Étudiant", t.student_name), ("Matricule", t.student_code or "—"),
        ("Formation", t.formation_title), ("Format", t.format_label),
        ("Session", t.session_label), ("Dates", f"{_day(t.session_start)} – {_day(t.session_end)}"),
    ]
    if t.training_hours:
        identity.append(("Volume", f"{t.training_hours} h"))
    column = (width - 2 * MARGIN) / 2
    for index, (label, value) in enumerate(identity):
        x = MARGIN + (index % 2) * column
        if index % 2 == 0 and index:
            page.y -= 30
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillColor(MUTED)
        pdf.drawString(x, page.y, label.upper())
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(INK)
        pdf.drawString(x, page.y - 13, (_wrap_lines(value, font="Helvetica-Bold", size=10, max_width=column - 12) or [""])[0])
    page.y -= 44

    # The three figures.
    boxes = [
        ("Moyenne générale", f"{_number(t.average_20)} / 20" if t.average_20 is not None else "—", t.mention or ("Pas encore de note" if t.average_20 is None else "Sans mention")),
        ("Assiduité", f"{t.attended_sessions} / {t.counted_sessions} séances" if t.counted_sessions else "—",
         f"{_number(t.attendance_pct, 1)} % de présence" if t.attendance_pct is not None else "Aucune séance comptée"),
        ("Badge", t.badge_label or "—", "Niveau atteint"),
    ]
    gap = 10
    box_width = (width - 2 * MARGIN - 2 * gap) / 3
    for index, (label, value, detail) in enumerate(boxes):
        x = MARGIN + index * (box_width + gap)
        pdf.setFillColor(colors.HexColor("#F4F6FB"))
        pdf.roundRect(x, page.y - 52, box_width, 58, 8, stroke=0, fill=1)
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillColor(MUTED)
        pdf.drawString(x + 12, page.y - 8, label.upper())
        pdf.setFont("Helvetica-Bold", 14)
        pdf.setFillColor(page.primary)
        pdf.drawString(x + 12, page.y - 27, value)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(MUTED)
        pdf.drawString(x + 12, page.y - 42, detail)
    page.y -= 78

    # The grades, by kind.
    columns = [(MARGIN, "Évaluation"), (MARGIN + 238, "Date"), (MARGIN + 300, "Note /20"), (MARGIN + 356, "Barème"), (MARGIN + 404, "Commentaire")]
    if not t.groups:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(MUTED)
        pdf.drawString(MARGIN, page.y, "Aucune note pour le moment.")
        page.y -= 20
    for group in t.groups:
        page.need(58)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.setFillColor(INK)
        pdf.drawString(MARGIN, page.y, group.label)
        page.y -= 10
        pdf.setFillColor(colors.HexColor("#EEF1F8"))
        pdf.rect(MARGIN, page.y - 14, width - 2 * MARGIN, 16, stroke=0, fill=1)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.setFillColor(MUTED)
        for x, title in columns:
            pdf.drawString(x + 6, page.y - 9, title.upper())
        page.y -= 16
        for line in group.lines:
            label_lines = _wrap_lines(line.label, font="Helvetica", size=9, max_width=226)[:2] or [""]
            note_lines = _wrap_lines(line.note, font="Helvetica", size=8, max_width=width - MARGIN - columns[4][0] - 10)[:3]
            height = 8 + 12 * max(len(label_lines), len(note_lines), 1)
            page.need(height)
            ink = INK if line.counted else LIGHT
            pdf.setFont("Helvetica", 9)
            pdf.setFillColor(ink)
            for index, text in enumerate(label_lines):
                pdf.drawString(columns[0][0] + 6, page.y - 12 - index * 12, text)
            pdf.drawString(columns[1][0] + 6, page.y - 12, _day(line.date))
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(columns[2][0] + 6, page.y - 12, _number(line.score_20))
            pdf.setFont("Helvetica", 8.5)
            pdf.drawString(columns[3][0] + 6, page.y - 12, f"{_number(line.score)}/{_number(line.max_score)}")
            pdf.setFont("Helvetica", 8)
            pdf.setFillColor(MUTED)
            for index, text in enumerate(note_lines):
                pdf.drawString(columns[4][0] + 6, page.y - 12 - index * 12, text)
            page.y -= height
            pdf.setStrokeColor(LINE)
            pdf.setLineWidth(0.5)
            pdf.line(MARGIN, page.y, width - MARGIN, page.y)
        page.y -= 18

    # How the average is made, then who signs.
    page.need(110)
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(MUTED)
    rule = ("Moyenne : toutes les notes ramenées sur 20, à poids égal. Les quiz automatiques sont affichés "
            "mais ne comptent pas. Mentions : Passable dès 10, Assez bien dès 12, Bien dès 14, Très bien dès 16.")
    for text in _wrap_lines(rule, font="Helvetica", size=8, max_width=width - 2 * MARGIN):
        pdf.drawString(MARGIN, page.y, text)
        page.y -= 11
    if not final:
        pdf.setFillColor(colors.HexColor("#B45309"))
        pdf.drawString(MARGIN, page.y, "Relevé provisoire : la session est en cours, les notes peuvent encore évoluer.")
        page.y -= 11
    # Only a final transcript is signed, with the signature and stamp of the certificates.
    if final:
        page.y -= 14
        signer_x = width - MARGIN - 170
        _draw_asset(pdf, signature_url, signer_x, page.y - 52, 100, 46)
        _draw_asset(pdf, stamp_url, signer_x + 100, page.y - 58, 70, 56)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(INK)
        pdf.drawString(signer_x, page.y - 66, t.signer_name or t.school_name)
        if t.signer_title:
            pdf.setFont("Helvetica", 8)
            pdf.setFillColor(MUTED)
            pdf.drawString(signer_x, page.y - 78, t.signer_title)

    pdf.showPage()
    pdf.save()
    return transcript_filename(t), page.buffer.getvalue()
