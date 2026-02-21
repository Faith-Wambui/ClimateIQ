# email/email_sender.py
"""
Sends the HTML digest via SMTP (Gmail by default).
Supports multiple recipients and attaches the plain-text fallback.
"""

import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_recipients() -> list[str]:
    raw = os.getenv("EMAIL_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


# ──────────────────────────────────────────────────────────────────────────────
# Sender
# ──────────────────────────────────────────────────────────────────────────────

def send_digest(
    html_content: str,
    plain_content: str,
    subject: str | None = None,
    attachments: list[str] | None = None,
) -> bool:
    """
    Sends the digest email via SMTP.

    Args:
        html_content:  Full HTML body.
        plain_content: Plain-text fallback body.
        subject:       Email subject line (auto-generated if None).
        attachments:   Optional list of file paths to attach.

    Returns:
        True on success, False on failure.
    """
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    recipients = _get_recipients()

    if not sender or not password:
        log.error("❌  EMAIL_SENDER or EMAIL_PASSWORD not set in .env")
        return False

    if not recipients:
        log.error("❌  EMAIL_RECIPIENTS not set in .env")
        return False

    # ── Build subject ────────────────────────────────────────────────────────
    if not subject:
        date_str = datetime.now().strftime("%A, %B %d")
        subject = f"🌍 Climate IQ — {date_str}"

    # ── Compose message ──────────────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Climate IQ <{sender}>"
    msg["To"] = ", ".join(recipients)

    # Attach plain text first (fallback for email clients that don't support HTML)
    msg.attach(MIMEText(plain_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # ── Optional file attachments ────────────────────────────────────────────
    if attachments:
        outer = MIMEMultipart("mixed")
        outer["Subject"] = msg["Subject"]
        outer["From"] = msg["From"]
        outer["To"] = msg["To"]
        outer.attach(msg)

        for path in attachments:
            if not os.path.exists(path):
                log.warning(f"  ⚠  Attachment not found: {path}")
                continue
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(path)}"',
            )
            outer.attach(part)

        msg = outer

    # ── Send via SMTP ────────────────────────────────────────────────────────
    try:
        log.info(f"📧  Connecting to {smtp_host}:{smtp_port}…")
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        log.info(f"✅  Digest sent to: {', '.join(recipients)}")
        return True

    except smtplib.SMTPAuthenticationError:
        log.error(
            "❌  SMTP authentication failed.\n"
            "   For Gmail: enable 2FA and use an App Password.\n"
            "   https://support.google.com/accounts/answer/185833"
        )
    except smtplib.SMTPException as e:
        log.error(f"❌  SMTP error: {e}")
    except Exception as e:
        log.error(f"❌  Unexpected error sending email: {e}")

    return False


# ──────────────────────────────────────────────────────────────────────────────
# Test helper
# ──────────────────────────────────────────────────────────────────────────────

def send_test_email() -> bool:
    """Sends a simple test email to verify SMTP config is working."""
    html = """\
    <html><body>
      <h2 style="color:#2d6a4f;">✅ Climate Aggregator — Test Email</h2>
      <p>Your SMTP configuration is working correctly!</p>
      <p style="color:#888;font-size:12px;">Sent from AI Climate News Aggregator</p>
    </body></html>"""
    plain = "Climate Aggregator test email — SMTP config is working!"
    return send_digest(html, plain, subject="✅ Climate Aggregator — SMTP Test")