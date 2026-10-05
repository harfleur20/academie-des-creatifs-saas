from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings


CATEGORY_LABELS = {
    "technical": "Problème technique",
    "billing": "Facturation",
    "account": "Compte et accès",
    "pedagogy": "Pédagogie",
    "other": "Autre",
}


def send_support_request_email(
    *,
    recipient: str,
    reference: str,
    requester_name: str,
    requester_email: str,
    organization_name: str,
    organization_id: int,
    category: str,
    priority: str,
    subject: str,
    message: str,
    page_url: str | None,
) -> None:
    category_label = CATEGORY_LABELS.get(category, category)
    priority_label = "Urgente" if priority == "urgent" else "Normale"
    mail_subject = f"[{reference}] {subject}"

    safe_message = html.escape(message).replace("\n", "<br>")
    safe_subject = html.escape(subject)
    safe_name = html.escape(requester_name)
    safe_email = html.escape(requester_email)
    safe_org = html.escape(organization_name)
    safe_page = html.escape(page_url or "Non renseignée")

    text_body = (
        f"Référence : {reference}\n"
        f"Priorité : {priority_label}\n"
        f"Catégorie : {category_label}\n"
        f"École : {organization_name} (#{organization_id})\n"
        f"Demandeur : {requester_name} <{requester_email}>\n"
        f"Page : {page_url or 'Non renseignée'}\n\n"
        f"Sujet : {subject}\n\n{message}\n"
    )

    html_body = f"""<!doctype html>
<html lang="fr">
  <body style="margin:0;background:#f5f7fb;font-family:Arial,sans-serif;color:#10233f">
    <table width="100%" cellpadding="0" cellspacing="0" style="padding:30px 12px">
      <tr><td align="center">
        <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#fff;border-radius:16px;overflow:hidden">
          <tr><td style="height:7px;background:#1f2559"></td></tr>
          <tr><td style="padding:28px 30px">
            <div style="font-size:12px;font-weight:700;color:#21a979;text-transform:uppercase;letter-spacing:.08em">Demande support {reference}</div>
            <h1 style="margin:10px 0 18px;font-size:23px;color:#10233f">{safe_subject}</h1>
            <table width="100%" cellpadding="6" cellspacing="0" style="font-size:13px;color:#526176;background:#f7f9fc;border-radius:10px">
              <tr><td><strong>Priorité</strong></td><td>{priority_label}</td></tr>
              <tr><td><strong>Catégorie</strong></td><td>{html.escape(category_label)}</td></tr>
              <tr><td><strong>École</strong></td><td>{safe_org} (#{organization_id})</td></tr>
              <tr><td><strong>Demandeur</strong></td><td>{safe_name} &lt;{safe_email}&gt;</td></tr>
              <tr><td><strong>Page</strong></td><td>{safe_page}</td></tr>
            </table>
            <div style="margin-top:22px;padding:18px;border:1px solid #e7ebf1;border-radius:12px;font-size:14px;line-height:1.7;color:#33435a">{safe_message}</div>
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""

    sender_name = settings.smtp_from_name or "Académie des Créatifs"

    if (
        settings.email_provider == "brevo"
        and settings.brevo_api_key
        and settings.smtp_from
    ):
        response = httpx.post(
            f"{settings.brevo_api_base_url}/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": settings.brevo_api_key,
                "content-type": "application/json",
            },
            json={
                "sender": {"name": sender_name, "email": settings.smtp_from},
                "to": [{"email": recipient}],
                "replyTo": {"email": requester_email, "name": requester_name},
                "subject": mail_subject,
                "htmlContent": html_body,
                "textContent": text_body,
            },
            timeout=settings.brevo_timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Brevo HTTP {response.status_code}: {response.text[:500]}"
            )
        return

    if settings.smtp_host and settings.smtp_from:
        mail = MIMEMultipart("alternative")
        mail["Subject"] = mail_subject
        mail["From"] = f"{sender_name} <{settings.smtp_from}>"
        mail["To"] = recipient
        mail["Reply-To"] = requester_email
        mail.attach(MIMEText(text_body, "plain", "utf-8"))
        mail.attach(MIMEText(html_body, "html", "utf-8"))

        if settings.smtp_port == 465:
            smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
            smtp.ehlo()
            smtp.starttls()
        with smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.sendmail(settings.smtp_from, [recipient], mail.as_string())
        return

    raise RuntimeError("Fournisseur e-mail non configuré.")
