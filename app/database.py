"""
Database layer — powered by SQLModel (SQLAlchemy 2 + Pydantic).
All public functions return plain dict objects so callers need zero changes.
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select, func

from app.models import ConversationMessage, User
from app.logger import logger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "omniquery.db")

_engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

@contextmanager
def _get_session() -> Generator[Session, None, None]:
    with Session(_engine) as session:
        yield session

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def create_table() -> None:
    SQLModel.metadata.create_all(_engine)
    logger.info("SQLModel | tables verified / created")

def create_users_table() -> None:
    pass

def upsert_user(*, github_id: int, login: str, email: str | None, name: str, avatar_url: str) -> dict:
    with _get_session() as session:
        user = session.exec(select(User).where(User.github_id == github_id)).first()
        now = _now()
        if user:
            user.login = login
            user.email = email
            user.name = name
            user.avatar_url = avatar_url
            user.last_login = now
        else:
            user = User(
                github_id=github_id, login=login, email=email, name=name,
                avatar_url=avatar_url, created_at=now, last_login=now,
            )
            session.add(user)
        session.commit()
        session.refresh(user)
        return _user_dict(user)

def get_user_by_github_id(github_id: int) -> dict | None:
    with _get_session() as session:
        user = session.exec(select(User).where(User.github_id == github_id)).first()
        return _user_dict(user) if user else None

def get_user_by_id(user_id: int) -> dict | None:
    with _get_session() as session:
        user = session.get(User, user_id)
        return _user_dict(user) if user else None

def _user_dict(user: User) -> dict:
    return {
        "id": user.id, "github_id": user.github_id, "login": user.login,
        "email": user.email, "name": user.name, "avatar_url": user.avatar_url,
        "created_at": user.created_at, "last_login": user.last_login,
    }

def save_conversation(conversation_id: str, query: str, answer: str, source: str, user_id: int | None = None) -> None:
    with _get_session() as session:
        msg = ConversationMessage(
            conversation_id=conversation_id, query=query, answer=answer,
            source=source, user_id=user_id, timestamp=_now(),
        )
        session.add(msg)
        session.commit()

def get_conversations(limit: int = 10, user_id: int | None = None) -> list[dict]:
    sql_template = """
        SELECT
            c.conversation_id,
            MIN(c.timestamp)  AS first_time,
            (SELECT query FROM conversations WHERE conversation_id = c.conversation_id {user_sub} ORDER BY timestamp ASC LIMIT 1) AS first_query,
            MAX(c.timestamp) AS last_updated
        FROM conversations c
        {user_main}
        GROUP BY c.conversation_id
        ORDER BY last_updated DESC
        LIMIT :limit
    """
    with _get_session() as session:
        if user_id is not None:
            sql = sql_template.format(user_sub="AND user_id = :uid", user_main="WHERE c.user_id = :uid")
            rows = session.exec(text(sql), params={"uid": user_id, "limit": limit}).fetchall()
        else:
            sql = sql_template.format(user_sub="", user_main="")
            rows = session.exec(text(sql), params={"limit": limit}).fetchall()
    return [{"conversation_id": r[0], "first_query": r[2], "last_updated": r[3]} for r in rows]

def get_messages_by_conversation(conversation_id: str, user_id: int | None = None) -> list[dict]:
    with _get_session() as session:
        stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        if user_id is not None:
            stmt = stmt.where(ConversationMessage.user_id == user_id)
        stmt = stmt.order_by(ConversationMessage.timestamp)
        messages = session.exec(stmt).all()
    return [{"query": m.query, "answer": m.answer, "source": m.source, "timestamp": m.timestamp} for m in messages]

def delete_conversation(conversation_id: str, user_id: int | None = None) -> bool:
    with _get_session() as session:
        stmt = select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        if user_id is not None:
            stmt = stmt.where(ConversationMessage.user_id == user_id)
        rows = session.exec(stmt).all()
        if not rows:
            return False
        for row in rows:
            session.delete(row)
        session.commit()
    return True