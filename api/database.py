"""
Database Models and Connection
==============================

SQLite database schema for feature storage using SQLAlchemy.
"""

import enum
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.types import JSON

Base = declarative_base()


class FeatureStatus(enum.Enum):
    """Status of a feature in the queue."""

    PENDING = "pending"  # Available for claiming
    IN_PROGRESS = "in_progress"  # Claimed by a worker (leased)
    PASSING = "passing"  # Completed successfully
    CONFLICT = "conflict"  # Merge conflict; manual resolution needed
    FAILED = "failed"  # Agent could not complete (permanent)


class Feature(Base):
    """Feature model representing a test case/feature to implement."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array

    # Status tracking (new enum-based status for parallel execution)
    status = Column(
        Enum(FeatureStatus, values_callable=lambda x: [e.value for e in x]),
        default=FeatureStatus.PENDING,
        index=True,
    )

    # Legacy fields - kept for backward compatibility
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)

    # Claim/lease tracking for parallel execution
    claimed_by = Column(String(100), nullable=True)  # Worker ID holding this feature
    claimed_at = Column(DateTime, nullable=True)  # Timestamp for lease expiry detection

    # Completion audit
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String(100), nullable=True)

    def to_dict(self) -> dict:
        """Convert feature to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
            "status": self.status.value if self.status else FeatureStatus.PENDING.value,
            "claimed_by": self.claimed_by,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completed_by": self.completed_by,
        }


def get_database_path(project_dir: Path) -> Path:
    """Return the path to the SQLite database for a project."""
    return project_dir / "features.db"


def get_database_url(project_dir: Path) -> str:
    """Return the SQLAlchemy database URL for a project.

    Uses POSIX-style paths (forward slashes) for cross-platform compatibility.
    """
    db_path = get_database_path(project_dir)
    return f"sqlite:///{db_path.as_posix()}"


def _migrate_database_schema(engine) -> None:
    """Migrate existing databases to add new columns for parallel execution."""
    from sqlalchemy import text

    with engine.connect() as conn:
        # Check existing columns
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        # Migration: in_progress column (legacy)
        if "in_progress" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0"))

        # Migration: status column for parallel execution
        if "status" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN status TEXT DEFAULT 'pending'"))
            # Migrate existing data: passes=True -> 'passing', in_progress=True -> 'in_progress'
            conn.execute(text("""
                UPDATE features SET status = CASE
                    WHEN passes = 1 THEN 'passing'
                    WHEN in_progress = 1 THEN 'in_progress'
                    ELSE 'pending'
                END
            """))

        # Migration: claim tracking columns
        if "claimed_by" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN claimed_by TEXT"))

        if "claimed_at" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN claimed_at DATETIME"))

        # Migration: completion audit columns
        if "completed_at" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN completed_at DATETIME"))

        if "completed_by" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN completed_by TEXT"))

        conn.commit()


def create_database(project_dir: Path) -> tuple:
    """
    Create database and return engine + session maker.

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    # Migrate existing databases to add new columns
    _migrate_database_schema(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


# Global session maker - will be set when server starts
_session_maker: Optional[sessionmaker] = None


def set_session_maker(session_maker: sessionmaker) -> None:
    """Set the global session maker."""
    global _session_maker
    _session_maker = session_maker


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.

    Yields a database session and ensures it's closed after use.
    """
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call set_session_maker first.")

    db = _session_maker()
    try:
        yield db
    finally:
        db.close()
