"""
Assistant Database
==================

SQLAlchemy models and functions for persisting assistant conversations.
Each project has its own assistant.db file in the project directory.
"""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()

# Engine cache to avoid creating new engines for each request
# Key: project directory path (as posix string), Value: SQLAlchemy engine
_engine_cache: dict[str, object] = {}

# Lock for thread-safe access to the engine cache
# Prevents race conditions when multiple threads create engines simultaneously
_cache_lock = threading.Lock()


def _utc_now() -> datetime:
    """Return current UTC time. Replacement for deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


class Conversation(Base):
    """A conversation with the assistant for a project."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=True)  # Optional title, derived from first message
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)

    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """A single message within a conversation."""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=_utc_now)

    conversation = relationship("Conversation", back_populates="messages")


def get_db_path(project_dir: Path) -> Path:
    """Get the path to the assistant database for a project."""
    return project_dir / "assistant.db"


def get_engine(project_dir: Path):
    """Get or create a SQLAlchemy engine for a project's assistant database.

    Uses a cache to avoid creating new engines for each request, which improves
    performance by reusing database connections.

    Thread-safe: Uses a lock to prevent race conditions when multiple threads
    try to create engines simultaneously for the same project.
    """
    cache_key = project_dir.as_posix()

    # Double-checked locking for thread safety and performance
    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

    with _cache_lock:
        # Check again inside the lock in case another thread created it
        if cache_key not in _engine_cache:
            db_path = get_db_path(project_dir)
            # Use as_posix() for cross-platform compatibility with SQLite connection strings
            db_url = f"sqlite:///{db_path.as_posix()}"
            engine = create_engine(
                db_url,
                echo=False,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,  # Wait up to 30s for locks
                }
            )
            Base.metadata.create_all(engine)
            _engine_cache[cache_key] = engine
            logger.debug(f"Created new database engine for {cache_key}")

    return _engine_cache[cache_key]


def get_session(project_dir: Path):
    """Get a new database session for a project."""
    engine = get_engine(project_dir)
    Session = sessionmaker(bind=engine)
    return Session()


# ============================================================================
# Conversation Operations
# ============================================================================

def create_conversation(project_dir: Path, project_name: str, title: Optional[str] = None) -> Conversation:
    """Create a new conversation for a project."""
    session = get_session(project_dir)
    try:
        conversation = Conversation(
            project_name=project_name,
            title=title,
        )
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        logger.info(f"Created conversation {conversation.id} for project {project_name}")
        return conversation
    finally:
        session.close()


def get_conversations(project_dir: Path, project_name: str) -> list[dict]:
    """Get all conversations for a project with message counts.

    Uses a subquery for message_count to avoid N+1 query problem.
    """
    session = get_session(project_dir)
    try:
        # Subquery to count messages per conversation (avoids N+1 query)
        message_count_subquery = (
            session.query(
                ConversationMessage.conversation_id,
                func.count(ConversationMessage.id).label("message_count")
            )
            .group_by(ConversationMessage.conversation_id)
            .subquery()
        )

        # Join conversation with message counts
        conversations = (
            session.query(
                Conversation,
                func.coalesce(message_count_subquery.c.message_count, 0).label("message_count")
            )
            .outerjoin(
                message_count_subquery,
                Conversation.id == message_count_subquery.c.conversation_id
            )
            .filter(Conversation.project_name == project_name)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        return [
            {
                "id": c.Conversation.id,
                "project_name": c.Conversation.project_name,
                "title": c.Conversation.title,
                "created_at": c.Conversation.created_at.isoformat() if c.Conversation.created_at else None,
                "updated_at": c.Conversation.updated_at.isoformat() if c.Conversation.updated_at else None,
                "message_count": c.message_count,
            }
            for c in conversations
        ]
    finally:
        session.close()


def get_conversation(project_dir: Path, conversation_id: int) -> Optional[dict]:
    """Get a conversation with all its messages."""
    session = get_session(project_dir)
    try:
        conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return None
        return {
            "id": conversation.id,
            "project_name": conversation.project_name,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                }
                for m in sorted(conversation.messages, key=lambda x: x.timestamp or datetime.min)
            ],
        }
    finally:
        session.close()


def delete_conversation(project_dir: Path, conversation_id: int) -> bool:
    """Delete a conversation and all its messages."""
    session = get_session(project_dir)
    try:
        conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return False
        session.delete(conversation)
        session.commit()
        logger.info(f"Deleted conversation {conversation_id}")
        return True
    finally:
        session.close()


# ============================================================================
# Message Operations
# ============================================================================

def add_message(project_dir: Path, conversation_id: int, role: str, content: str) -> Optional[dict]:
    """Add a message to a conversation."""
    session = get_session(project_dir)
    try:
        conversation = session.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return None

        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        session.add(message)

        # Update conversation's updated_at timestamp
        conversation.updated_at = _utc_now()

        # Auto-generate title from first user message if not set
        if not conversation.title and role == "user":
            # Take first 50 chars of first user message as title
            conversation.title = content[:50] + ("..." if len(content) > 50 else "")

        session.commit()
        session.refresh(message)

        logger.debug(f"Added {role} message to conversation {conversation_id}")
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        }
    finally:
        session.close()


def get_messages(project_dir: Path, conversation_id: int) -> list[dict]:
    """Get all messages for a conversation."""
    session = get_session(project_dir)
    try:
        messages = (
            session.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.timestamp.asc())
            .all()
        )
        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in messages
        ]
    finally:
        session.close()
