from typing import Optional

from pydantic import BaseModel, EmailStr


# Schema für die Erstellung eines neuen Benutzers (Registrierung)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

# Schema für die öffentliche Darstellung eines Benutzers (ohne Passwort)
class UserPublic(BaseModel):
    id: int
    email: EmailStr
    name: str
    institution: str

# Schema für das Login
class UserLogin(BaseModel):
    email: EmailStr
    password: str