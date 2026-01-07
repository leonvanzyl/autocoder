"""
Assistant Database
==================

SQLAlchemy models and functions for persisting assistant conversations.
Each project has its own assistant.db file in the project directory.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class Conversation(Base):
    """A conversation with the assistant for a project."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=True)  # Optional title, derived from first message
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """A single message within a conversation."""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


def get_db_path(project_dir: Path) -> Path:
    """Get the path to the assistant database for a project."""
    return project_dir / "assistant.db"


def get_engine(project_dir: Path):
    """Get or create a SQLAlchemy engine for a project's assistant database."""
    db_path = get_db_path(project_dir)
    # Use as_posix() for cross-platform compatibility with SQLite connection strings
    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


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
    """Get all conversations for a project with message counts."""
    session = get_session(project_dir)
    try:
        conversations = (
            session.query(Conversation)
            .filter(Conversation.project_name == project_name)
            .order_by(Conversation.updated_at.desc())
            .all()
        )
        return [
            {
                "id": c.id,
                "project_name": c.project_name,
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "message_count": len(c.messages),
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
        conversation.updated_at = datetime.utcnow()

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
