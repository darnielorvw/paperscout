from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from config import settings
from database import models
from database.database import get_session

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_email_verification_token(
    email: str, name: str, hashed_password: str, expire_hours: int
) -> str:
    """Creates a signed token with the registration data for the confirmation link.

    We deliberately don't create a user in the DB yet – only clicking the
    link in the email (i.e. proof that the address belongs to the sender)
    creates the account.
    """
    to_encode = {
        "purpose": "email_verification",
        "email": email,
        "name": name,
        "hashed_password": hashed_password,
        "exp": datetime.now(timezone.utc) + timedelta(hours=expire_hours),
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_email_verification_token(token: str) -> dict:
    """Decodes and validates an email confirmation token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("purpose") != "email_verification" or not payload.get("email"):
            raise HTTPException(status_code=400, detail="Invalid confirmation link.")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="The confirmation link has expired. Please register again.",
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid confirmation link.") from None


def get_user_by_email(session: Session, email: str) -> Optional[models.User]:
    """Fetches a user by their email address from the DB."""
    statement = select(models.User).where(models.User.email == email)
    return session.exec(statement).first()


async def get_current_user(
    session: Session = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> models.User:
    # If there's no token AND we're in dev mode, return a dummy user.

    # if not credentials and settings.ENVIRONMENT == "dev":
    #     return {
    #         "email": "max.mustermann@uni-muenster.de",
    #         "name": "Max Mustermann",
    #         "institution": "fh-swf",
    #         "role": "faculty",
    #     }
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. 'Authorization' header missing.",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token (no 'sub').")
        user = get_user_by_email(session, email)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found.")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="The login token has expired.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from None


async def require_admin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    """Like get_current_user, but only lets admins through (403 otherwise)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user
