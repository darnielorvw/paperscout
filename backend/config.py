import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # "dev" für lokale Entwicklung ohne Mail-Zwang, "prod" für echten Betrieb
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "dev")
    
    # Geheimschlüssel für die JWT-Verschlüsselung (In Prod unbedingt ändern!)
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-for-local-testing")
    JWT_ALGORITHM: str = "HS256"
    
    # Mail-Server-Konfiguration (nur für Prod relevant)
    SMTP_SERVER: str = "mail.fh-swf.de"
    SMTP_PORT: int = 587

settings = Settings()