from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

JournalIDStr = str


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    hashed_password: str
    institution: str
    is_admin: bool = Field(default=False)

    profiles: List["Profile"] = Relationship(back_populates="user")


class Journals(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    name: str
    issn: str
    publisher: str
    homepage: str
    # Flags individual handling of this journal's papers by an external API, e.g.
    # "springer" or "scopus" (see services/external_api_service.py). None = Crossref/OpenAlex only.
    external_api: Optional[str] = Field(default=None)


class ProfileJournalLink(SQLModel, table=True):
    """Join table connecting a search profile to its selected journals."""

    profile_id: Optional[int] = Field(
        default=None, foreign_key="profile.id", primary_key=True, ondelete="CASCADE"
    )
    journal_id: Optional[str] = Field(
        default=None, foreign_key="journals.id", primary_key=True, ondelete="CASCADE"
    )


class Profile(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "profile_name", name="uq_profile_user_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_name: str
    user_id: int = Field(foreign_key="user.id")
    searchTerm: str
    email_notifications: bool = Field(default=True)

    user: User = Relationship(back_populates="profiles")
    journals: List[Journals] = Relationship(link_model=ProfileJournalLink)


class SavedArticle(SQLModel, table=True):
    """A paper on a user's reading list. Stores the search result as it was when
    saved, so the list doesn't need Crossref/OpenAlex to be shown again."""

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_saved_article_user_article"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    # The search result's `id`, i.e. the bare DOI.
    article_id: str
    title: Optional[str] = None
    author: Optional[str] = None
    journal_name: Optional[str] = None
    publication_date: Optional[str] = None
    journal_publication_date: Optional[str] = None
    issue: Optional[str] = None
    doi: Optional[str] = None
    library_url: Optional[str] = None
    abstract: Optional[str] = None
    topic: Optional[str] = None
    is_read: bool = Field(default=False)
    saved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiAlert(SQLModel, table=True):
    """A quota alert mail that has gone out, so every API is reported at most
    once per day and kind (quota running low / quota exhausted)."""

    __table_args__ = (UniqueConstraint("api", "kind", "day", name="uq_api_alert_api_kind_day"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    api: str
    # "low" or "exhausted"
    kind: str
    # ISO date (UTC) of the day the alert went out.
    day: str


class PaperRequest(SQLModel, table=True):
    """A user asking the admins for a paper's PDF, because the library has no
    access to it. Removed together with the paper from the reading list."""

    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_paper_request_user_article"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    # The search result's `id`, i.e. the bare DOI.
    article_id: str = Field(index=True)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaperPdf(SQLModel, table=True):
    """A PDF an admin uploaded for a paper. Every user with the paper on their
    reading list can open it."""

    # The search result's `id`, i.e. the bare DOI.
    article_id: str = Field(primary_key=True)
    # Public Vercel Blob URL. Its random suffix keeps it unguessable, and the
    # API only hands it to users with the paper on their reading list.
    url: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
