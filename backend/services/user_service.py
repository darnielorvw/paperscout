from database import models
from passlib.context import CryptContext
from sqlmodel import Session

# Setup für das Passwort-Hashing (bcrypt ist der Standard)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vergleicht ein Klartext-Passwort mit einem Hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Erzeugt einen Hash aus einem Klartext-Passwort."""
    return pwd_context.hash(password)


def create_db_user_from_hash(
    session: Session, email: str, name: str, hashed_password: str
) -> models.User:
    """Legt einen User anhand eines bereits gehashten Passworts an (z.B. nach E-Mail-Bestätigung)."""
    institution = email.split('@')[-1]
    db_user = models.User(
        name=name, email=email, hashed_password=hashed_password, institution=institution
    )
    session.add(db_user)
    return db_user