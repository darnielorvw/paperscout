from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# Schema for creating a new user (registration)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str


# Schema for the public representation of a user (without password)
class UserPublic(BaseModel):
    id: int
    email: EmailStr
    name: str
    institution: str
    is_admin: bool


# Schema for login
class UserLogin(BaseModel):
    email: EmailStr
    password: str


# Schema for the settings within a search profile
class ProfileSettings(BaseModel):
    rowSelection: Dict[str, bool] = Field(default_factory=dict)
    startDate: datetime
    endDate: datetime
    searchTerm: str = ""
    emailNotifications: bool = True


# Schema for creating a new profile
class ProfileCreate(BaseModel):
    name: str
    settings: ProfileSettings


# Schema for toggling email notifications for a profile
class ProfileNotificationsUpdate(BaseModel):
    emailNotifications: bool


# Schema for changing the email address (confirmed via current password)
class ChangeEmailRequest(BaseModel):
    currentPassword: str
    newEmail: EmailStr


# Schema for changing the password
class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


# Schema for deleting one's own account
class DeleteAccountRequest(BaseModel):
    currentPassword: str


# Schema for importing one or more journals by name (admin only)
class JournalImportByName(BaseModel):
    names: List[str]
