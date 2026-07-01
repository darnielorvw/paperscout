from datetime import datetime
import hashlib
import json
from typing import Dict, List, Optional

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

JournalIDStr = str


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    hashed_password: str
    institution: str

    profiles: List["Profile"] = Relationship(back_populates="user")


class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_name: str = Field(unique=True)
    user_id: int = Field(foreign_key="user.id")
    row_selection: Dict[JournalIDStr, bool] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    start_date: datetime
    end_date: datetime
    searchTerm: str
    settings_hash: str = Field(unique=True, index=True)
    user: User = Relationship(back_populates="profiles")

    def generate_hash(self):
        json_str = json.dumps(self.row_selection, sort_keys=True)
        data_string = f"{self.start_date.isoformat()}-{self.end_date.isoformat()}-{self.searchTerm}-{json_str}"
        return hashlib.md5(data_string.encode("utf-8")).hexdigest()


class Journals(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    name: str
    issn: str
    publisher: str
    homepage: str
