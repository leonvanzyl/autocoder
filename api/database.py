"""
Database Models and Connection
==============================

SQLite database schema for hierarchical task management using SQLAlchemy.

Hierarchy: Project → Phase → Feature → Task

- Phase: Major milestone in a project (e.g., "Phase 1: Foundation")
- Feature: Major work item requiring spec creation (e.g., "User Authentication")
- Task: Actionable item the agent works on (formerly "Feature")
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from sqlalchemy.types import JSON

Base = declarative_base()


class Phase(Base):
    """Phase represents a major milestone in the project.

    Phases contain Features and provide approval gates before
    the project can proceed to the next phase.

    Status flow: pending → in_progress → awaiting_approval → completed
    """

    __tablename__ = "phases"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False, default=0, index=True)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    features = relationship(
        "Feature", back_populates="phase", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert phase to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "feature_count": len(self.features) if self.features else 0,
        }


class Feature(Base):
    """Feature represents a major work item requiring spec creation.

    Features group related Tasks and can be assigned to specific agents.
    When a new Feature is added, it triggers the spec creation workflow.

    Status flow: pending → speccing → ready → in_progress → completed
    """

    __tablename__ = "features_v2"  # New table to avoid conflict during migration

    id = Column(Integer, primary_key=True, index=True)
    phase_id = Column(Integer, ForeignKey("phases.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    spec = Column(Text, nullable=True)  # Generated spec for this feature
    status = Column(String(50), default="pending", index=True)
    priority = Column(Integer, default=0, index=True)
    agent_id = Column(String(100), nullable=True, index=True)  # Assigned agent
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    phase = relationship("Phase", back_populates="features")
    tasks = relationship("Task", back_populates="feature", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convert feature to dictionary for JSON serialization."""
        tasks_list = self.tasks if self.tasks else []
        return {
            "id": self.id,
            "phase_id": self.phase_id,
            "name": self.name,
            "description": self.description,
            "spec": self.spec,
            "status": self.status,
            "priority": self.priority,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "task_count": len(tasks_list),
            "tasks_completed": sum(1 for t in tasks_list if t.passes),
        }


class Task(Base):
    """Task represents an actionable item the agent works on.

    This was formerly called "Feature" in the old schema.
    Tasks are the atomic units of work that agents complete.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(
        Integer, ForeignKey("features_v2.id"), nullable=True, index=True
    )
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)

    # Complexity estimation for usage-based scheduling (1-5 scale)
    estimated_complexity = Column(Integer, default=2)

    # Dependency tracking
    depends_on = Column(JSON, nullable=True)  # Array of task IDs this depends on
    blocks = Column(JSON, nullable=True)  # Array of task IDs blocked by this
    is_blocked = Column(Boolean, default=False, index=True)
    blocked_reason = Column(String(500), nullable=True)

    # Review tracking
    reviewed = Column(Boolean, default=False, index=True)
    review_notes = Column(Text, nullable=True)
    review_score = Column(Integer, nullable=True)  # 1-5 quality score

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    feature = relationship("Feature", back_populates="tasks")

    def to_dict(self) -> dict:
        """Convert task to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
            "estimated_complexity": self.estimated_complexity,
            # Dependency fields
            "depends_on": self.depends_on or [],
            "blocks": self.blocks or [],
            "is_blocked": self.is_blocked,
            "blocked_reason": self.blocked_reason,
            # Review fields
            "reviewed": self.reviewed,
            "review_notes": self.review_notes,
            "review_score": self.review_score,
            # Timestamps
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class UsageLog(Base):
    """Track Claude API usage for monitoring and smart scheduling.

    Captures token usage per API call to enable:
    - Usage dashboards
    - Smart task scheduling based on remaining quota
    - Per-project usage tracking
    """

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    task_id = Column(Integer, nullable=True)  # Which task triggered this
    agent_id = Column(String(100), nullable=True)  # Which agent made the call
    session_id = Column(String(100), nullable=True)  # Agent session identifier

    def to_dict(self) -> dict:
        """Convert usage log to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
        }


# =============================================================================
# Legacy Feature Model (for backward compatibility during migration)
# =============================================================================


class LegacyFeature(Base):
    """Legacy Feature model - kept for migration purposes.

    This represents the old schema where 'features' were the atomic work items.
    After migration, these become 'tasks' in the new schema.
    """

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)
    passes = Column(Boolean, default=False, index=True)
    in_progress = Column(Boolean, default=False, index=True)

    def to_dict(self) -> dict:
        """Convert legacy feature to dictionary."""
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "passes": self.passes,
            "in_progress": self.in_progress,
        }


# =============================================================================
# Database Connection and Initialization
# =============================================================================


def get_database_path(project_dir: Path) -> Path:
    """Return the path to the SQLite database for a project."""
    return project_dir / "features.db"


def get_database_url(project_dir: Path) -> str:
    """Return the SQLAlchemy database URL for a project.

    Uses POSIX-style paths (forward slashes) for cross-platform compatibility.
    """
    db_path = get_database_path(project_dir)
    return f"sqlite:///{db_path.as_posix()}"


def _migrate_add_in_progress_column(engine) -> None:
    """Add in_progress column to existing databases that don't have it."""
    from sqlalchemy import text

    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "in_progress" not in columns:
            # Add the column with default value
            conn.execute(
                text("ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0")
            )
            conn.commit()


def _check_schema_version(engine) -> str:
    """Check which schema version the database is using.

    Returns:
        'legacy': Old schema with only 'features' table
        'v2': New schema with phases, features_v2, tasks tables
        'empty': No tables exist yet
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        # Check for tables
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}

        if "tasks" in tables and "phases" in tables:
            return "v2"
        elif "features" in tables:
            return "legacy"
        else:
            return "empty"


def create_database(project_dir: Path) -> tuple:
    """
    Create database and return engine + session maker.

    Automatically detects schema version and handles migrations.

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Check current schema version
    schema_version = _check_schema_version(engine)

    if schema_version == "legacy":
        # Migrate in_progress column if needed (legacy migration)
        _migrate_add_in_progress_column(engine)
        # Note: Full migration to v2 schema is handled by migrate_to_v2()

    # Create all tables (new tables will be created, existing ones untouched)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


# =============================================================================
# Global Session Management
# =============================================================================

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


# =============================================================================
# Dependency Management Utilities
# =============================================================================


def update_blocked_status(db: Session, task: Task) -> None:
    """Update whether a task is blocked based on its dependencies.

    Args:
        db: Database session
        task: Task to update
    """
    if not task.depends_on:
        task.is_blocked = False
        task.blocked_reason = None
        return

    # Check if all dependencies are complete
    deps = db.query(Task).filter(Task.id.in_(task.depends_on)).all()
    incomplete = [d for d in deps if not d.passes]

    if incomplete:
        task.is_blocked = True
        names = ", ".join(d.name[:30] for d in incomplete[:3])
        if len(incomplete) > 3:
            names += f" (+{len(incomplete) - 3} more)"
        task.blocked_reason = f"Waiting on: {names}"
    else:
        task.is_blocked = False
        task.blocked_reason = None


def propagate_completion(db: Session, task_id: int) -> list[int]:
    """When a task completes, unblock dependent tasks.

    Args:
        db: Database session
        task_id: ID of the completed task

    Returns:
        List of task IDs that were unblocked
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return []

    unblocked = []
    for blocked_id in task.blocks or []:
        blocked_task = db.query(Task).filter(Task.id == blocked_id).first()
        if blocked_task:
            was_blocked = blocked_task.is_blocked
            update_blocked_status(db, blocked_task)
            if was_blocked and not blocked_task.is_blocked:
                unblocked.append(blocked_id)

    db.commit()
    return unblocked


def set_task_dependencies(db: Session, task_id: int, depends_on: list[int]) -> Task:
    """Set dependencies for a task.

    Args:
        db: Database session
        task_id: ID of the task to update
        depends_on: List of task IDs this task depends on

    Returns:
        Updated task
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise ValueError(f"Task {task_id} not found")

    # Remove this task from old dependencies' blocks lists
    if task.depends_on:
        for old_dep_id in task.depends_on:
            old_dep = db.query(Task).filter(Task.id == old_dep_id).first()
            if old_dep and old_dep.blocks:
                blocks = list(old_dep.blocks)
                if task_id in blocks:
                    blocks.remove(task_id)
                    old_dep.blocks = blocks

    # Set new dependencies
    task.depends_on = depends_on

    # Add this task to new dependencies' blocks lists
    for dep_id in depends_on:
        dep_task = db.query(Task).filter(Task.id == dep_id).first()
        if dep_task:
            blocks = list(dep_task.blocks or [])
            if task_id not in blocks:
                blocks.append(task_id)
                dep_task.blocks = blocks

    # Update blocked status
    update_blocked_status(db, task)

    db.commit()
    return task
