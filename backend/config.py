import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # "dev" for local development without mail requirements, "prod" for real operation
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")

    # Secret key for JWT signing (make sure to change this in prod!)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-for-local-testing")
    JWT_ALGORITHM: str = "HS256"

    # Mail server configuration (only relevant for prod)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "mail.fh-swf.de")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "PaperScout <noreply@paperscout.local>")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Base URL of the frontend, for links in emails
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Comma-separated list of allowed CORS origins (in addition to FRONTEND_URL)
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    # Regex for additional allowed origins (e.g. Cloudflare quick tunnels)
    CORS_ORIGIN_REGEX: str = os.getenv(
        "CORS_ORIGIN_REGEX", r"https://.*\.trycloudflare\.com"
    )

    # Base URL of the backend, for download links in emails (must be reachable from outside)
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    # Cron expression for the monthly digest send (default: 1st of every month, 07:00)
    DIGEST_CRON: str = os.getenv("DIGEST_CRON", "0 7 1 * *")

    # Validity period of the PDF download links in digest emails (in days)
    DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS: int = int(
        os.getenv("DIGEST_DOWNLOAD_LINK_EXPIRE_DAYS", "90")
    )

    # Validity period of the email confirmation link during registration (in hours)
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = int(
        os.getenv("EMAIL_VERIFICATION_EXPIRE_HOURS", "24")
    )

    # OpenAlex API configuration
    OPENALEX_API_KEY: str = os.getenv("API_KEY", "")

settings = Settings()