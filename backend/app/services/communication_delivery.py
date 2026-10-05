from __future__ import annotations

import html
import re
import smtplib
from datetime import UTC, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import CommunicationOutboxRecord


WAPINO_FALLBACKS = (
    "/message/send-text",
    "/message/sendText",
    "/messages/send-text",
)


def _delivery_key(row: CommunicationOutboxRecord) -> str:
    return str(uuid5(NAMESPACE_URL, f"{settings.jwt_issuer}:communication:{row.id}"))


def _email_html(row: CommunicationOutboxRecord) -> str:
    snapshot = dict(row.branding_snapshot or {})
    primary = html.escape(str(snapshot.get("primary_color") or "#1F2559"))
    accent = html.escape(str(snapshot.get("accent_color") or "#131735"))
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
            "headers": {"Idempotency-Key": _delivery_key(row)},
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
        message["Message-ID"] = f"<{_delivery_key(row)}@notifications.local>"
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
    stale_before = datetime.now(UTC) - timedelta(minutes=10)
    stale = update(CommunicationOutboxRecord).where(
        CommunicationOutboxRecord.status == "sending",
        CommunicationOutboxRecord.claimed_at < stale_before,
    )
    if organization_id is not None:
        stale = stale.where(CommunicationOutboxRecord.organization_id == organization_id)
    db.execute(stale.values(
        status="needs_review",
        claim_token=None,
        last_error="Envoi interrompu : vérifier le fournisseur avant de réessayer.",
    ))
    db.commit()
    query = (
        select(CommunicationOutboxRecord.id)
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
    ids = list(db.scalars(query).all())
    sent = failed = 0

    processed = 0
    for row_id in ids:
        claim_token = str(uuid4())
        claimed = db.execute(
            update(CommunicationOutboxRecord)
            .where(
                CommunicationOutboxRecord.id == row_id,
                CommunicationOutboxRecord.status.in_(["pending", "failed"]),
                CommunicationOutboxRecord.attempts_count < 3,
            )
            .values(
                status="sending",
                claim_token=claim_token,
                claimed_at=datetime.now(UTC),
                attempts_count=CommunicationOutboxRecord.attempts_count + 1,
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if claimed.rowcount != 1:
            continue
        db.expire_all()
        row = db.get(CommunicationOutboxRecord, row_id)
        processed += 1
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
            # An HTTP timeout or worker crash may follow a successful send.
            # Only known local failures are safe to retry automatically.
            local_failure = isinstance(exc, RuntimeError) and (
                "non configuré" in str(exc)
                or "désactivé" in str(exc)
                or "incomplète" in str(exc)
                or "invalide" in str(exc)
            )
            row.status = "failed" if local_failure and row.attempts_count < 3 else "needs_review"
            row.last_error = str(exc)[:2000]
            failed += 1
        row.claim_token = None
        row.claimed_at = None
        db.add(row)
        db.commit()

    return {"processed": processed, "sent": sent, "failed": failed}
