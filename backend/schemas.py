from typing import Dict, List, Literal, Optional

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
    searchTerm: str = ""
    semanticQuery: str = Field(default="", max_length=2000)
    searchMode: Literal["keywords", "semantic"] = "keywords"
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


# Where the free version of a search result is (see _open_access in search_service)
class OpenAccess(BaseModel):
    url: str
    status: Optional[str] = None
    host: Optional[str] = None


# Schema for a search result as it is saved to the reading list
class SavedArticleData(BaseModel):
    id: str = Field(min_length=1)
    title: Optional[str] = None
    author: Optional[str] = None
    journal_name: Optional[str] = None
    publication_date: Optional[str] = None
    journal_publication_date: Optional[str] = None
    issue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    library_url: Optional[str] = None
    abstract: Optional[str] = None
    topic: Optional[str] = None
    open_access: Optional[OpenAccess] = None


# Schema for adding search results to the reading list
class SavedArticlesCreate(BaseModel):
    articles: List[SavedArticleData] = Field(min_length=1, max_length=200)


# Schema for marking a reading list entry as read or unread
class SavedArticleUpdate(BaseModel):
    isRead: bool


# Schema for requesting a client token to upload a paper's PDF (admin only)
class PaperPdfUploadToken(BaseModel):
    article_id: str = Field(min_length=1)


# Schema for storing the URL of an uploaded paper PDF (admin only)
class PaperPdfCreate(BaseModel):
    article_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
