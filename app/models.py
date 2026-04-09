"""
SQLModel ORM table definitions for OmniQuery.

Two tables:
  - users          → User
  - conversations  → ConversationMessage
"""
from typing import Optional
from sqlmodel import Field, Relationship, SQLModel

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    github_id: int = Field(unique=True, nullable=False, index=True)
    login: str = Field(nullable=False)
    email: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    created_at: Optional[str] = Field(default=None)
    last_login: Optional[str] = Field(default=None)
    messages: list["ConversationMessage"] = Relationship(back_populates="user")

class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversations"
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: str = Field(nullable=False, index=True)
    query: str = Field(nullable=False)
    answer: str = Field(nullable=False)
    source: str = Field(nullable=False)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    timestamp: Optional[str] = Field(default=None)
    user: Optional[User] = Relationship(back_populates="messages")
