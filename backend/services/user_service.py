from database import models
from passlib.context import CryptContext
from schemas import UserCreate
from sqlmodel import Session

# Setup für das Passwort-Hashing (bcrypt ist der Standard)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vergleicht ein Klartext-Passwort mit einem Hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Erzeugt einen Hash aus einem Klartext-Passwort."""
    return pwd_context.hash(password)


def create_db_user(session: Session, user: UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    institution = user.email.split('@')[-1]

    # Erstelle das Datenbank-Modell. Wir übergeben die Felder aus dem UserCreate-Schema
    # manuell und fügen die serverseitig generierten Felder hinzu.
    db_user = models.User(
        name=user.name, email=user.email, hashed_password=hashed_password, institution=institution
    )
    session.add(db_user)
    return db_user