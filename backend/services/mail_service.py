import logging
from email.message import EmailMessage

import aiosmtplib
from config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MailService:
    """Versendet E-Mails über den in der Konfiguration hinterlegten SMTP-Server."""

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logging.warning(
                f"SMTP nicht konfiguriert (SMTP_USER/SMTP_PASSWORD fehlen) – "
                f"E-Mail an {to} wird nicht gesendet, Inhalt wird stattdessen geloggt."
            )
            logging.info(f"--- Mail-Vorschau für {to} ---\nBetreff: {subject}\n{html_body}")
            return False

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content("Ihr E-Mail-Client unterstützt kein HTML.")
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
            logging.info(f"E-Mail erfolgreich an {to} gesendet.")
            return True
        except Exception as e:
            logging.error(f"Fehler beim Senden der E-Mail an {to}: {e}")
            return False
