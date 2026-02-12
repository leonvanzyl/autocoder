"""
Agent Session Database
======================

SQLAlchemy models and functions for persisting agent session output.
Each project has its own agent_sessions.db file in the project directory.
"""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 style declarative base."""
    pass


# Engine cache to avoid creating new engines for each request
_engine_cache: dict[str, Engine] = {}
_cache_lock = threading.Lock()


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class AgentSession(Base):
    """An agent session for a project."""
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running/completed/crashed
    yolo_mode = Column(Boolean, nullable=False, default=False)
    model = Column(String(100), nullable=True)
    max_concurrency = Column(Integer, nullable=True)

    logs = relationship("AgentSessionLog", back_populates="session", cascade="all, delete-orphan")


class AgentSessionLog(Base):
    """A single log line within an agent session."""
    __tablename__ = "agent_session_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("agent_sessions.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=_utc_now)
    line_type = Column(String(20), nullable=False)  # output/tool_use/tool_result/agent_update/error
    content = Column(Text, nullable=False)
    feature_id = Column(Integer, nullable=True)
    agent_index = Column(Integer, nullable=True)
    agent_name = Column(String(20), nullable=True)

    session = relationship("AgentSession", back_populates="logs")

    __table_args__ = (
        Index("ix_session_logs_session_timestamp", "session_id", "timestamp"),
    )


def _get_db_path(project_dir: Path) -> Path:
    """Get the path to the agent sessions database for a project."""
    from autoforge_paths import get_agent_sessions_db_path
    return get_agent_sessions_db_path(project_dir)


def get_engine(project_dir: Path) -> Engine:
    """Get or create a SQLAlchemy engine for a project's agent sessions database."""
    cache_key = project_dir.as_posix()

    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

    with _cache_lock:
        if cache_key not in _engine_cache:
            db_path = _get_db_path(project_dir)
            db_url = f"sqlite:///{db_path.as_posix()}"
            engine = create_engine(
                db_url,
                echo=False,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                }
            )

            # Enable WAL mode for better concurrent read/write performance
            @event.listens_for(engine, "connect")
            def _set_wal_mode(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

            Base.metadata.create_all(engine)
            _engine_cache[cache_key] = engine
            logger.debug("Created agent sessions database engine for %s", cache_key)

            # Refresh .gitignore so existing projects pick up the new db entries
            from autoforge_paths import ensure_autoforge_dir
            ensure_autoforge_dir(project_dir)

    return _engine_cache[cache_key]


def dispose_engine(project_dir: Path) -> bool:
    """Dispose of and remove the cached engine for a project."""
    cache_key = project_dir.as_posix()

    if cache_key in _engine_cache:
        engine = _engine_cache.pop(cache_key)
        engine.dispose()
        logger.debug("Disposed agent sessions database engine for %s", cache_key)
        return True

    return False


def get_session(project_dir: Path):
    """Get a new database session for a project."""
    engine = get_engine(project_dir)
    Session = sessionmaker(bind=engine)
    return Session()


# ============================================================================
# Session CRUD
# ============================================================================

def create_session(
    project_dir: Path,
    project_name: str,
    yolo_mode: bool = False,
    model: Optional[str] = None,
    max_concurrency: Optional[int] = None,
) -> int:
    """Create a new agent session. Returns the session ID."""
    db = get_session(project_dir)
    try:
        session = AgentSession(
            project_name=project_name,
            yolo_mode=yolo_mode,
            model=model,
            max_concurrency=max_concurrency,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info("Created agent session %d for project %s", session.id, project_name)
        return session.id
    finally:
        db.close()


def end_session(project_dir: Path, session_id: int, status: str = "completed") -> None:
    """Mark a session as ended."""
    db = get_session(project_dir)
    try:
        session = db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if session:
            session.ended_at = _utc_now()
            session.status = status
            db.commit()
            logger.info("Ended agent session %d with status %s", session_id, status)
    finally:
        db.close()


def add_log(
    project_dir: Path,
    session_id: int,
    line_type: str,
    content: str,
    feature_id: Optional[int] = None,
    agent_index: Optional[int] = None,
    agent_name: Optional[str] = None,
) -> None:
    """Add a single log entry to a session."""
    db = get_session(project_dir)
    try:
        log = AgentSessionLog(
            session_id=session_id,
            line_type=line_type,
            content=content,
            feature_id=feature_id,
            agent_index=agent_index,
            agent_name=agent_name,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


def add_logs_batch(project_dir: Path, session_id: int, logs: list[dict]) -> None:
    """Bulk insert log entries for performance."""
    if not logs:
        return
    db = get_session(project_dir)
    try:
        for log_data in logs:
            log = AgentSessionLog(
                session_id=session_id,
                line_type=log_data["line_type"],
                content=log_data["content"],
                feature_id=log_data.get("feature_id"),
                agent_index=log_data.get("agent_index"),
                agent_name=log_data.get("agent_name"),
            )
            db.add(log)
        db.commit()
    finally:
        db.close()


def get_sessions(
    project_dir: Path,
    project_name: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Get sessions for a project, ordered by most recent first."""
    db = get_session(project_dir)
    try:
        sessions = (
            db.query(AgentSession)
            .filter(AgentSession.project_name == project_name)
            .order_by(AgentSession.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": s.id,
                "project_name": s.project_name,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": s.status,
                "yolo_mode": s.yolo_mode,
                "model": s.model,
                "max_concurrency": s.max_concurrency,
            }
            for s in sessions
        ]
    finally:
        db.close()


def get_session_detail(project_dir: Path, session_id: int) -> Optional[dict]:
    """Get a single session by ID."""
    db = get_session(project_dir)
    try:
        session = db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if not session:
            return None
        return {
            "id": session.id,
            "project_name": session.project_name,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "status": session.status,
            "yolo_mode": session.yolo_mode,
            "model": session.model,
            "max_concurrency": session.max_concurrency,
        }
    finally:
        db.close()


def get_session_logs(
    project_dir: Path,
    session_id: int,
    line_type_filter: Optional[str] = None,
    feature_id_filter: Optional[int] = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    """Get logs for a session with optional filters."""
    db = get_session(project_dir)
    try:
        query = (
            db.query(AgentSessionLog)
            .filter(AgentSessionLog.session_id == session_id)
        )
        if line_type_filter:
            query = query.filter(AgentSessionLog.line_type == line_type_filter)
        if feature_id_filter is not None:
            query = query.filter(AgentSessionLog.feature_id == feature_id_filter)

        logs = (
            query
            .order_by(AgentSessionLog.timestamp.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": log.id,
                "session_id": log.session_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "line_type": log.line_type,
                "content": log.content,
                "feature_id": log.feature_id,
                "agent_index": log.agent_index,
                "agent_name": log.agent_name,
            }
            for log in logs
        ]
    finally:
        db.close()


def delete_session(project_dir: Path, session_id: int) -> bool:
    """Delete a session and all its logs."""
    db = get_session(project_dir)
    try:
        session = db.query(AgentSession).filter(AgentSession.id == session_id).first()
        if not session:
            return False
        db.delete(session)
        db.commit()
        logger.info("Deleted agent session %d", session_id)
        return True
    finally:
        db.close()
