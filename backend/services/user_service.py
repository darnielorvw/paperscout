from passlib.context import CryptContext
from sqlmodel import Session

from database import models

# Setup for password hashing (bcrypt is the standard)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compares a plaintext password with a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Creates a hash from a plaintext password."""
    return pwd_context.hash(password)


def create_db_user_from_hash(
    session: Session, email: str, name: str, hashed_password: str
) -> models.User:
    """Creates a user from an already-hashed password (e.g. after email confirmation)."""
    institution = email.split("@")[-1]
    db_user = models.User(
        name=name, email=email, hashed_password=hashed_password, institution=institution
    )
    session.add(db_user)
    return db_user
