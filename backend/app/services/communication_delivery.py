from __future__ import annotations

import html
import re
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import CommunicationOutboxRecord


WAPINO_FALLBACKS = (
    "/message/send-text",
    "/message/sendText",
    "/messages/send-text",
)


def _email_html(row: CommunicationOutboxRecord) -> str:
    snapshot = dict(row.branding_snapshot or {})
    primary = html.escape(str(snapshot.get("primary_color") or "#1768FF"))
    accent = html.escape(str(snapshot.get("accent_color") or "#10233F"))
    school = html.escape(str(snapshot.get("school_name") or "École"))
    logo = snapshot.get("logo_url")
    logo_html = (
        f'<img src="{html.escape(str(logo), quote=True)}" alt="{school}" '
        'style="max-height:56px;max-width:190px;display:block;margin:0 auto 10px;">'
        if logo
        else ""
    )
    body = html.escape(row.body).replace("\n", "<br>")
    return f"""<!doctype html>
<html lang="fr"><body style="margin:0;background:#f5f7fb;font-family:Arial,sans-serif;color:{accent}">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:14px;overflow:hidden">
<tr><td style="height:8px;background:{primary}"></td></tr>
<tr><td style="padding:24px;text-align:center">{logo_html}<strong style="font-size:18px">{school}</strong></td></tr>
<tr><td style="padding:8px 30px 30px;font-size:14px;line-height:1.65">{body}</td></tr>
<tr><td style="padding:16px 30px;text-align:center;border-top:1px solid #eef1f4;color:#94a3b8;font-size:10px">
Powered by Académie des Créatifs
</td></tr>
</table></td></tr></table></body></html>"""


def _send_email(row: CommunicationOutboxRecord) -> None:
    snapshot = dict(row.branding_snapshot or {})
    sender_name = str(snapshot.get("sender_name") or snapshot.get("school_name") or settings.smtp_from_name)
    reply_to = snapshot.get("reply_to_email")
    subject = row.subject or str(snapshot.get("school_name") or "Notification")
    html_body = _email_html(row)

    if (
        settings.email_provider == "brevo"
        and settings.brevo_api_key
        and settings.smtp_from
    ):
        payload: dict = {
            "sender": {"name": sender_name, "email": settings.smtp_from},
            "to": [{"email": row.recipient}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": row.body,
        }
        if reply_to:
            payload["replyTo"] = {
                "email": str(reply_to),
                "name": sender_name,
            }
        response = httpx.post(
            f"{settings.brevo_api_base_url}/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": settings.brevo_api_key,
                "content-type": "application/json",
            },
            json=payload,
            timeout=settings.brevo_timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Brevo HTTP {response.status_code}: {response.text[:500]}"
            )
        return

    if settings.smtp_host and settings.smtp_from:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{settings.smtp_from}>"
        message["To"] = row.recipient
        if reply_to:
            message["Reply-To"] = str(reply_to)
        message.attach(MIMEText(row.body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))
        if settings.smtp_port == 465:
            smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            smtp.ehlo()
            smtp.starttls()
        with smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, [row.recipient], message.as_string())
        return

    raise RuntimeError("Fournisseur e-mail non configuré.")


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if not 8 <= len(digits) <= 15:
        raise RuntimeError("Numéro WhatsApp invalide.")
    return digits


def _send_whatsapp(row: CommunicationOutboxRecord) -> None:
    if not settings.wapino_enabled:
        raise RuntimeError("Wapino est désactivé.")
    if not settings.wapino_api_key or not settings.wapino_instance:
        raise RuntimeError("Configuration Wapino incomplète.")

    number = _normalize_phone(row.recipient)
    payload = {
        "instance": settings.wapino_instance,
        "number": number,
        "text": row.body,
    }
    endpoints: list[str] = []
    for endpoint in (settings.wapino_text_endpoint, *WAPINO_FALLBACKS):
        normalized = "/" + endpoint.lstrip("/")
        if normalized not in endpoints:
            endpoints.append(normalized)

    last_error = ""
    for index, endpoint in enumerate(endpoints):
        response = httpx.post(
            f"{settings.wapino_base_url}{endpoint}",
            headers={
                "Authorization": f"Bearer {settings.wapino_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.wapino_timeout_seconds,
        )
        if response.status_code < 400:
            return
        body = response.text[:500]
        last_error = f"Wapino HTTP {response.status_code}: {body}"
        missing_route = (
            response.status_code == 404
            and (
                "cannot post" in body.lower()
                or "route not found" in body.lower()
                or "endpoint not found" in body.lower()
            )
        )
        if missing_route and index < len(endpoints) - 1:
            continue
        break
    raise RuntimeError(last_error or "Échec Wapino.")


def process_communication_outbox(
    db: Session,
    *,
    organization_id: int | None = None,
    limit: int = 100,
) -> dict[str, int]:
    query = (
        select(CommunicationOutboxRecord)
        .where(
            CommunicationOutboxRecord.status.in_(["pending", "failed"]),
            CommunicationOutboxRecord.attempts_count < 3,
        )
        .order_by(CommunicationOutboxRecord.created_at)
        .limit(max(1, min(limit, 500)))
    )
    if organization_id is not None:
        query = query.where(
            CommunicationOutboxRecord.organization_id == organization_id
        )
    rows = list(db.scalars(query).all())
    sent = failed = 0

    for row in rows:
        row.attempts_count += 1
        try:
            if row.channel == "email":
                _send_email(row)
            elif row.channel == "whatsapp":
                _send_whatsapp(row)
            else:
                raise RuntimeError(f"Canal non supporté : {row.channel}")
            row.status = "sent"
            row.last_error = None
            row.sent_at = datetime.now(UTC)
            sent += 1
        except Exception as exc:
            row.status = "failed"
            row.last_error = str(exc)[:2000]
            failed += 1
        db.add(row)
        db.commit()

    return {"processed": len(rows), "sent": sent, "failed": failed}
