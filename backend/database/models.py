from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

# WICHTIG: Jedes Modell erbt von SQLModel und hat table=True

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    institution: str

    profiles: List["Profile"] = Relationship(back_populates="user")

class Profile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_name: str
    user_id: int = Field(foreign_key="user.id")

    user: User = Relationship(back_populates="profiles")