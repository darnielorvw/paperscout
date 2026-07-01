from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


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


# Schema für die Einstellungen innerhalb eines Suchprofils
class ProfileSettings(BaseModel):
    rowSelection: Dict[str, bool] = Field(default_factory=dict)
    startDate: datetime
    endDate: datetime
    searchTerm: str = ""


# Schema für die Erstellung eines neuen Profils
class ProfileCreate(BaseModel):
    name: str
    settings: ProfileSettings
