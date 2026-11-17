"""SMTP delivery. Credentials come from :class:`~quant_research.config.Settings`, never from code."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from quant_research.config import Settings

log = logging.getLogger(__name__)


class EmailNotConfigured(RuntimeError):
    """Raised when SENDER_EMAIL / EMAIL_PASSWORD are missing."""


def build_message(
    sender: str, recipient: str, subject: str, text_body: str, html_body: str | None = None
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(text_body, "plain"))
    if html_body is not None:
        msg.attach(MIMEText(html_body, "html"))
    return msg


def send_email(
    settings: Settings,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    recipient: str | None = None,
    ssl_fallback: bool = False,
    timeout: float = 20,
) -> None:
    """Send one message over STARTTLS (optionally retrying over implicit TLS on port 465).

    ``recipient`` defaults to ``RECIPIENT_EMAIL``. Raises :class:`EmailNotConfigured`
    if credentials are missing, or the underlying ``smtplib`` error on failure.
    """
    if not settings.email_configured:
        raise EmailNotConfigured("SENDER_EMAIL and EMAIL_PASSWORD must be set")
    to = recipient or settings.recipient_email
    if not to:
        raise EmailNotConfigured("No recipient: set RECIPIENT_EMAIL or pass recipient=")

    raw = build_message(settings.sender_email, to, subject, text_body, html_body).as_string()
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(settings.sender_email, settings.email_password)
            srv.sendmail(settings.sender_email, [to], raw)
    except Exception as starttls_exc:
        if not ssl_fallback:
            raise
        log.warning("STARTTLS send failed (%s); retrying over SSL", starttls_exc)
        with smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=timeout) as srv:
            srv.login(settings.sender_email, settings.email_password)
            srv.sendmail(settings.sender_email, [to], raw)
