"""
Email Sender Utility
Sends strategy request notifications via SMTP (TLS).
"""
import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from loguru import logger
from app.config.settings import settings


def _send_smtp(subject: str, html_body: str, to_email: str):
    """Blocking SMTP send — run in executor."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, to_email, msg.as_string())


async def send_strategy_request_email(
    name: str,
    phone: str,
    email: str,
    description: str,
) -> bool:
    """
    Send a strategy request notification to the configured NOTIFY_EMAIL.
    Returns True on success, False on failure.
    """
    if not settings.smtp_user or settings.smtp_user == "your_gmail@gmail.com":
        logger.warning("SMTP not configured — skipping email send")
        return False

    subject = f"📈 New Strategy Request from {name}"
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;
                background:#0a0e1a;color:#e2e8f0;padding:32px;border-radius:12px;
                border:1px solid #1e293b;">
      <h2 style="color:#00d4ff;margin-top:0;">New Strategy Request</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:10px 0;color:#94a3b8;width:140px;">Name</td>
          <td style="padding:10px 0;font-weight:bold;">{name}</td>
        </tr>
        <tr>
          <td style="padding:10px 0;color:#94a3b8;">Phone</td>
          <td style="padding:10px 0;">{phone}</td>
        </tr>
        <tr>
          <td style="padding:10px 0;color:#94a3b8;">Email</td>
          <td style="padding:10px 0;"><a href="mailto:{email}" style="color:#00d4ff;">{email}</a></td>
        </tr>
        <tr>
          <td style="padding:10px 0;color:#94a3b8;vertical-align:top;">Strategy</td>
          <td style="padding:10px 0;white-space:pre-wrap;">{description}</td>
        </tr>
      </table>
      <hr style="border-color:#1e293b;margin:24px 0;"/>
      <p style="font-size:12px;color:#475569;margin:0;">
        Sent from Market Engine Dashboard
      </p>
    </div>
    """

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, _send_smtp, subject, html_body, settings.notify_email
        )
        logger.info(f"Strategy request email sent → {settings.notify_email}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
