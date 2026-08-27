import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # "dev" für lokale Entwicklung ohne Mail-Zwang, "prod" für echten Betrieb
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")
    
    # Geheimschlüssel für die JWT-Verschlüsselung (In Prod unbedingt ändern!)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-for-local-testing")
    JWT_ALGORITHM: str = "HS256"
    
    # Mail-Server-Konfiguration (nur für Prod relevant)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "mail.fh-swf.de")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "PaperScout <noreply@paperscout.local>")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Basis-URL des Frontends, für Links in E-Mails
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Basis-URL des Backends, für Download-Links in E-Mails (muss von außen erreichbar sein)
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # Cron-Ausdruck für den monatlichen Digest-Versand (Standard: 1. jedes Monats, 07:00 Uhr)
    DIGEST_CRON: str = os.getenv("DIGEST_CRON", "0 7 1 * *")

    # Gültigkeitsdauer der PDF-Download-Links in den Digest-Mails (in Tagen)
    DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS: int = int(
        os.getenv("DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS", "90")
    )

    # OpenAlex API-Konfiguration
    OPENALEX_API_KEY: str = os.getenv("API_KEY", "")

settings = Settings()