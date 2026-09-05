import logging
from email.message import EmailMessage

import aiosmtplib

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MailService:
    """Sends emails via the SMTP server configured in settings."""

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logging.warning(
                f"SMTP not configured (SMTP_USER/SMTP_PASSWORD missing) – "
                f"email to {to} will not be sent, content is logged instead."
            )
            logging.info(f"--- Mail preview for {to} ---\nSubject: {subject}\n{html_body}")
            return False

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content("Your email client does not support HTML.")
        message.add_alternative(html_body, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_SERVER,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                start_tls=settings.SMTP_USE_TLS,
            )
            logging.info(f"Email successfully sent to {to}.")
            return True
        except Exception as e:
            logging.error(f"Error sending email to {to}: {e}")
            return False
