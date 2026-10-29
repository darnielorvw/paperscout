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

    # Base URL of the frontend, for links in emails. Frontend and backend are
    # deployed as one Vercel project (see vercel.json) and therefore share a
    # domain - if FRONTEND_URL isn't explicitly overridden, fall back to the
    # current deployment's own VERCEL_URL instead of localhost, so Previews
    # don't need this env var set by hand for every deployment.
    FRONTEND_URL: str = os.getenv(
        "FRONTEND_URL",
        f"https://{os.environ['VERCEL_URL']}"
        if os.getenv("VERCEL_URL")
        else "http://localhost:5173",
    )

    # Comma-separated list of allowed CORS origins (in addition to FRONTEND_URL)
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    # Regex for additional allowed origins (e.g. Cloudflare quick tunnels)
    CORS_ORIGIN_REGEX: str = os.getenv("CORS_ORIGIN_REGEX", r"")

    # Base URL of the backend, for the verification links in emails (must be reachable from outside).
    # On Vercel, VERCEL_URL is set automatically to the current deployment's own
    # URL (a new one for every Preview deployment) - if BACKEND_URL isn't
    # explicitly overridden, fall back to that instead of localhost, so Previews
    # don't need this env var set by hand for every deployment.
    BACKEND_URL: str = os.getenv(
        "BACKEND_URL",
        f"https://{os.environ['VERCEL_URL']}"
        if os.getenv("VERCEL_URL")
        else "http://localhost:8000",
    )

    # Cron expression for the monthly digest send (default: 1st of every month, 07:00)
    DIGEST_CRON: str = os.getenv("DIGEST_CRON", "0 7 1 * *")

    # Only people with an email at one of these domains (or a subdomain, e.g.
    # stud.fh-swf.de) can register.
    ALLOWED_EMAIL_DOMAINS: list[str] = [
        domain.strip().lower()
        for domain in os.getenv("ALLOWED_EMAIL_DOMAINS", "uni-muenster.de,fh-swf.de").split(",")
        if domain.strip()
    ]

    # Validity period of the email confirmation link during registration (in hours)
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = int(os.getenv("EMAIL_VERIFICATION_EXPIRE_HOURS", "24"))

    # Contact address sent to Crossref for the "polite pool" (falls back to SMTP_FROM).
    CROSSREF_MAILTO: str = os.getenv("CROSSREF_MAILTO", "")

    # Library OpenURL resolver; every result links to it so users reach the full
    # text through their institution's subscriptions.
    OPENURL_RESOLVER: str = os.getenv(
        "OPENURL_RESOLVER", "https://kai.fh-swf.de/openurl/49HBZ_FSW/49HBZ_FSW:VU1"
    )
    # Users whose email is at one of these domains get their own library's resolver
    # instead of OPENURL_RESOLVER.
    OPENURL_RESOLVERS_BY_DOMAIN: dict[str, str] = {
        "uni-muenster.de": "https://katalogplus.uni-muenster.de/discovery/openurl"
        "?institution=49HBZ_ULM&vid=49HBZ_ULM:VU2",
    }

    # Vercel Blob store for the paper PDFs admins upload. Vercel sets it when a
    # Blob store is connected to the project; without it, uploads are disabled.
    BLOB_READ_WRITE_TOKEN: str = os.getenv("BLOB_READ_WRITE_TOKEN", "")
    # Largest PDF an admin may upload (in MB).
    PAPER_PDF_MAX_MB: int = int(os.getenv("PAPER_PDF_MAX_MB", "50"))

    # Quota alerts: admins get a mail once an external API's remaining quota drops
    # below this share (in percent) or the quota is used up.
    API_QUOTA_WARN_PERCENT: float = float(os.getenv("API_QUOTA_WARN_PERCENT", "10"))
    # OpenAlex only reports the remaining budget, not the total, so the daily
    # budget of the API key is configured here.
    OPENALEX_DAILY_BUDGET_USD: float = float(os.getenv("OPENALEX_DAILY_BUDGET_USD", "1.0"))

    # Springer Nature Meta API key, used for journals with external_api="springer".
    SPRINGER_API_KEY: str = os.getenv("SPRINGER_API_KEY", "")


settings = Settings()
