from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings


def _password_reset_html(reset_url: str) -> str:
    safe_url = html.escape(reset_url, quote=True)
    return f"""<!doctype html>
<html lang="fr">
  <body style="margin:0;background:#f5f7fb;font-family:Arial,sans-serif;color:#10233f">
    <table width="100%" cellpadding="0" cellspacing="0" style="padding:32px 12px">
      <tr><td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:16px;overflow:hidden">
          <tr><td style="height:8px;background:#1f2559"></td></tr>
          <tr><td style="padding:30px 32px 8px;text-align:center">
            <strong style="font-size:22px;color:#10233f">Académie des Créatifs</strong>
          </td></tr>
          <tr><td style="padding:12px 32px 32px;font-size:14px;line-height:1.7;color:#42526a">
            <h1 style="margin:0 0 14px;font-size:24px;color:#10233f">Réinitialisez votre mot de passe</h1>
            <p>Une demande de réinitialisation a été reçue pour votre compte.</p>
            <p>Ce lien est valable pendant <strong>30 minutes</strong> et ne pourra plus être utilisé après la modification du mot de passe.</p>
            <p style="margin:26px 0;text-align:center">
              <a href="{safe_url}" style="display:inline-block;padding:13px 22px;border-radius:10px;background:#1f2559;color:#fff;text-decoration:none;font-weight:700">Choisir un nouveau mot de passe</a>
            </p>
            <p style="font-size:12px;color:#708096">Si vous n’êtes pas à l’origine de cette demande, vous pouvez ignorer cet email. Votre mot de passe actuel restera inchangé.</p>
          </td></tr>
          <tr><td style="padding:16px 30px;text-align:center;border-top:1px solid #eef1f4;color:#94a3b8;font-size:10px">
            Académie des Créatifs SaaS
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    subject = "Réinitialisation de votre mot de passe"
    text_body = (
        "Vous avez demandé à réinitialiser votre mot de passe.\n\n"
        f"Ouvrez ce lien dans les 30 prochaines minutes :\n{reset_url}\n\n"
        "Si vous n’êtes pas à l’origine de cette demande, ignorez cet email."
    )
    html_body = _password_reset_html(reset_url)
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
                "subject": subject,
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
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{settings.smtp_from}>"
        message["To"] = recipient
        message.attach(MIMEText(text_body, "plain", "utf-8"))
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
            smtp.sendmail(settings.smtp_from, [recipient], message.as_string())
        return

    raise RuntimeError("Fournisseur e-mail non configuré.")
