"""
Chat-to-Features Database
=========================

SQLAlchemy models and functions for persisting chat-to-features conversations.
Each project has its own chat_features.db file in the project directory.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class ChatConversation(Base):
    """A chat-to-features conversation for a project."""
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
    suggestions = relationship("ChatSuggestion", back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    """A single message within a chat-to-features conversation."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("ChatConversation", back_populates="messages")


class ChatSuggestion(Base):
    """A pending feature suggestion within a conversation."""
    __tablename__ = "chat_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True)
    suggestion_index = Column(Integer, nullable=False)  # Index within the conversation
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(Text, nullable=False)  # JSON-encoded list
    reasoning = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # "pending" | "accepted" | "rejected"
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("ChatConversation", back_populates="suggestions")


def get_db_path(project_dir: Path) -> Path:
    """Get the path to the chat-to-features database for a project."""
    return project_dir / "chat_features.db"


def get_engine(project_dir: Path):
    """Get or create a SQLAlchemy engine for a project's chat database."""
    db_path = get_db_path(project_dir)
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

def get_or_create_conversation(project_dir: Path, project_name: str) -> ChatConversation:
    """
    Get the active conversation for a project, or create one if it doesn't exist.

    For chat-to-features, we maintain a single conversation per project
    that persists across panel open/close cycles.
    """
    session = get_session(project_dir)
    try:
        # Look for existing conversation
        conversation = session.query(ChatConversation).filter_by(
            project_name=project_name
        ).order_by(ChatConversation.updated_at.desc()).first()

        if conversation:
            return conversation

        # Create new conversation
        conversation = ChatConversation(project_name=project_name)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return conversation
    finally:
        session.close()


def get_conversation_by_id(project_dir: Path, conversation_id: int) -> Optional[ChatConversation]:
    """Get a conversation by ID."""
    session = get_session(project_dir)
    try:
        return session.query(ChatConversation).filter_by(id=conversation_id).first()
    finally:
        session.close()


def clear_conversation(project_dir: Path, project_name: str) -> bool:
    """Clear all messages and suggestions from a project's conversation."""
    session = get_session(project_dir)
    try:
        conversation = session.query(ChatConversation).filter_by(
            project_name=project_name
        ).first()

        if conversation:
            # Delete all messages and suggestions
            session.query(ChatMessage).filter_by(conversation_id=conversation.id).delete()
            session.query(ChatSuggestion).filter_by(conversation_id=conversation.id).delete()
            session.commit()
            return True
        return False
    finally:
        session.close()


# ============================================================================
# Message Operations
# ============================================================================

def add_message(
    project_dir: Path,
    conversation_id: int,
    role: str,
    content: str,
    timestamp: Optional[datetime] = None
) -> ChatMessage:
    """Add a message to a conversation."""
    session = get_session(project_dir)
    try:
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=timestamp or datetime.utcnow()
        )
        session.add(message)

        # Update conversation timestamp
        conversation = session.query(ChatConversation).filter_by(id=conversation_id).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()

        session.commit()
        session.refresh(message)
        return message
    finally:
        session.close()


def get_messages(project_dir: Path, conversation_id: int) -> list[dict]:
    """Get all messages for a conversation, ordered by timestamp."""
    session = get_session(project_dir)
    try:
        messages = session.query(ChatMessage).filter_by(
            conversation_id=conversation_id
        ).order_by(ChatMessage.timestamp.asc()).all()

        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ]
    finally:
        session.close()


# ============================================================================
# Suggestion Operations
# ============================================================================

def add_suggestion(
    project_dir: Path,
    conversation_id: int,
    suggestion_index: int,
    name: str,
    category: str,
    description: str,
    steps: list[str],
    reasoning: Optional[str] = None
) -> ChatSuggestion:
    """Add a feature suggestion to a conversation."""
    session = get_session(project_dir)
    try:
        suggestion = ChatSuggestion(
            conversation_id=conversation_id,
            suggestion_index=suggestion_index,
            name=name,
            category=category,
            description=description,
            steps=json.dumps(steps),
            reasoning=reasoning,
            status="pending"
        )
        session.add(suggestion)
        session.commit()
        session.refresh(suggestion)
        return suggestion
    finally:
        session.close()


def get_pending_suggestions(project_dir: Path, conversation_id: int) -> list[dict]:
    """Get all pending suggestions for a conversation."""
    session = get_session(project_dir)
    try:
        suggestions = session.query(ChatSuggestion).filter_by(
            conversation_id=conversation_id,
            status="pending"
        ).order_by(ChatSuggestion.suggestion_index.asc()).all()

        return [
            {
                "index": s.suggestion_index,
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "steps": json.loads(s.steps),
                "reasoning": s.reasoning
            }
            for s in suggestions
        ]
    finally:
        session.close()


def update_suggestion_status(
    project_dir: Path,
    conversation_id: int,
    suggestion_index: int,
    status: str
) -> bool:
    """Update the status of a suggestion (accepted/rejected)."""
    session = get_session(project_dir)
    try:
        suggestion = session.query(ChatSuggestion).filter_by(
            conversation_id=conversation_id,
            suggestion_index=suggestion_index
        ).first()

        if suggestion:
            suggestion.status = status
            session.commit()
            return True
        return False
    finally:
        session.close()


# ============================================================================
# Full Conversation Load (for reconnection)
# ============================================================================

def load_conversation_history(project_dir: Path, project_name: str) -> dict:
    """
    Load full conversation history for sending to client on reconnect.

    Returns:
        Dict with messages and pending_suggestions lists
    """
    session = get_session(project_dir)
    try:
        conversation = session.query(ChatConversation).filter_by(
            project_name=project_name
        ).order_by(ChatConversation.updated_at.desc()).first()

        if not conversation:
            return {"messages": [], "pending_suggestions": [], "conversation_id": None}

        messages = get_messages(project_dir, conversation.id)
        suggestions = get_pending_suggestions(project_dir, conversation.id)

        return {
            "conversation_id": conversation.id,
            "messages": messages,
            "pending_suggestions": suggestions
        }
    finally:
        session.close()
