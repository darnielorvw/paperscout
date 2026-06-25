from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from config import settings
from database import models
from database.database import get_session
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from services import user_service
from sqlmodel import Session, select

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def get_user_by_email(session: Session, email: str) -> Optional[models.User]:
    """Holt einen Benutzer anhand seiner E-Mail-Adresse aus der DB."""
    statement = select(models.User).where(models.User.email == email)
    return session.exec(statement).first()


async def get_current_user(
    session: Session = Depends(get_session),
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> models.User:
    # Wenn kein Token da ist UND wir im Dev-Modus sind, geben wir einen Dummy-User zurück.

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
            detail="Authentifizierung erforderlich. 'Authorization'-Header fehlt.",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Ungültiges Token (kein 'sub').")
        user = get_user_by_email(session, email)
        if user is None:
            raise HTTPException(status_code=401, detail="Benutzer nicht gefunden.")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Das Login-Token ist abgelaufen.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Ungültiges Authentifizierungs-Token.")