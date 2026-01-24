"""
Database Models and Connection
==============================

SQLite database schema for feature storage using SQLAlchemy.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now() -> datetime:
    """Return current UTC time. Replacement for deprecated _utc_now()."""
    return datetime.now(timezone.utc)

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from sqlalchemy.types import JSON

Base = declarative_base()


class Feature(Base):
    """Feature model representing a test case/feature to implement."""

    __tablename__ = "features"

    # Composite index for common status query pattern (passes, in_progress)
    # Used by feature_get_stats, get_ready_features, and other status queries
    __table_args__ = (
        Index('ix_feature_status', 'passes', 'in_progress'),
    )

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, nullable=False, default=False, index=True)
    in_progress = Column(Boolean, nullable=False, default=False, index=True)
    # Dependencies: list of feature IDs that must be completed before this feature
    # NULL/empty = no dependencies (backwards compatible)
    dependencies = Column(JSON, nullable=True, default=None)

    def to_dict(self) -> dict:
        """Convert feature to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            # Handle legacy NULL values gracefully - treat as False
            "passes": self.passes if self.passes is not None else False,
            "in_progress": self.in_progress if self.in_progress is not None else False,
            # Dependencies: NULL/empty treated as empty list for backwards compat
            "dependencies": self.dependencies if self.dependencies else [],
        }

    def get_dependencies_safe(self) -> list[int]:
        """Safely extract dependencies, handling NULL and malformed data."""
        if self.dependencies is None:
            return []
        if isinstance(self.dependencies, list):
            return [d for d in self.dependencies if isinstance(d, int)]
        return []


class Schedule(Base):
    """Time-based schedule for automated agent start/stop."""

    __tablename__ = "schedules"

    # Database-level CHECK constraints for data integrity
    __table_args__ = (
        CheckConstraint('duration_minutes >= 1 AND duration_minutes <= 1440', name='ck_schedule_duration'),
        CheckConstraint('days_of_week >= 0 AND days_of_week <= 127', name='ck_schedule_days'),
        CheckConstraint('max_concurrency >= 1 AND max_concurrency <= 5', name='ck_schedule_concurrency'),
        CheckConstraint('crash_count >= 0', name='ck_schedule_crash_count'),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(50), nullable=False, index=True)

    # Timing (stored in UTC)
    start_time = Column(String(5), nullable=False)  # "HH:MM" format
    duration_minutes = Column(Integer, nullable=False)  # 1-1440

    # Day filtering (bitfield: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64)
    days_of_week = Column(Integer, nullable=False, default=127)  # 127 = all days

    # State
    enabled = Column(Boolean, nullable=False, default=True, index=True)

    # Agent configuration for scheduled runs
    yolo_mode = Column(Boolean, nullable=False, default=False)
    model = Column(String(50), nullable=True)  # None = use global default
    max_concurrency = Column(Integer, nullable=False, default=3)  # 1-5 concurrent agents

    # Crash recovery tracking
    crash_count = Column(Integer, nullable=False, default=0)  # Resets at window start

    # Metadata
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    # Relationships
    overrides = relationship(
        "ScheduleOverride", back_populates="schedule", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert schedule to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "start_time": self.start_time,
            "duration_minutes": self.duration_minutes,
            "days_of_week": self.days_of_week,
            "enabled": self.enabled,
            "yolo_mode": self.yolo_mode,
            "model": self.model,
            "max_concurrency": self.max_concurrency,
            "crash_count": self.crash_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_active_on_day(self, weekday: int) -> bool:
        """Check if schedule is active on given weekday (0=Monday, 6=Sunday)."""
        day_bit = 1 << weekday
        return bool(self.days_of_week & day_bit)


class ScheduleOverride(Base):
    """Persisted manual override for a schedule window."""

    __tablename__ = "schedule_overrides"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )

    # Override details
    override_type = Column(String(10), nullable=False)  # "start" or "stop"
    expires_at = Column(DateTime, nullable=False)  # When this window ends (UTC)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    # Relationships
    schedule = relationship("Schedule", back_populates="overrides")

    def to_dict(self) -> dict:
        """Convert override to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "override_type": self.override_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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


def _migrate_add_in_progress_column(engine) -> None:
    """Add in_progress column to existing databases that don't have it."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "in_progress" not in columns:
            # Add the column with default value
            conn.execute(text("ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0"))
            conn.commit()


def _migrate_fix_null_boolean_fields(engine) -> None:
    """Fix NULL values in passes and in_progress columns."""
    with engine.connect() as conn:
        # Fix NULL passes values
        conn.execute(text("UPDATE features SET passes = 0 WHERE passes IS NULL"))
        # Fix NULL in_progress values
        conn.execute(text("UPDATE features SET in_progress = 0 WHERE in_progress IS NULL"))
        conn.commit()


def _migrate_add_dependencies_column(engine) -> None:
    """Add dependencies column to existing databases that don't have it.

    Uses NULL default for backwards compatibility - existing features
    without dependencies will have NULL which is treated as empty list.
    """
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "dependencies" not in columns:
            # Use TEXT for SQLite JSON storage, NULL default for backwards compat
            conn.execute(text("ALTER TABLE features ADD COLUMN dependencies TEXT DEFAULT NULL"))
            conn.commit()


def _migrate_add_testing_columns(engine) -> None:
    """Legacy migration - no longer adds testing columns.

    The testing_in_progress and last_tested_at columns were removed from the
    Feature model as part of simplifying the testing agent architecture.
    Multiple testing agents can now test the same feature concurrently
    without coordination.

    This function is kept for backwards compatibility but does nothing.
    Existing databases with these columns will continue to work - the columns
    are simply ignored.
    """
    pass


def _is_network_path(path: Path) -> bool:
    """Detect if path is on a network filesystem.

    WAL mode doesn't work reliably on network filesystems (NFS, SMB, CIFS)
    and can cause database corruption. This function detects common network
    path patterns so we can fall back to DELETE mode.

    Args:
        path: The path to check

    Returns:
        True if the path appears to be on a network filesystem
    """
    path_str = str(path.resolve())

    if sys.platform == "win32":
        # Windows UNC paths: \\server\share or \\?\UNC\server\share
        if path_str.startswith("\\\\"):
            return True
        # Mapped network drives - check if the drive is a network drive
        try:
            import ctypes
            drive = path_str[:2]  # e.g., "Z:"
            if len(drive) == 2 and drive[1] == ":":
                # DRIVE_REMOTE = 4
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
                if drive_type == 4:  # DRIVE_REMOTE
                    return True
        except (AttributeError, OSError):
            pass
    else:
        # Unix: Check mount type via /proc/mounts or mount command
        try:
            with open("/proc/mounts", "r") as f:
                mounts = f.read()
                # Check each mount point to find which one contains our path
                for line in mounts.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[1]
                        fs_type = parts[2]
                        # Check if path is under this mount point and if it's a network FS
                        if path_str.startswith(mount_point):
                            if fs_type in ("nfs", "nfs4", "cifs", "smbfs", "fuse.sshfs"):
                                return True
        except (FileNotFoundError, PermissionError):
            pass

    return False


def _migrate_add_schedules_tables(engine) -> None:
    """Create schedules and schedule_overrides tables if they don't exist."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Create schedules table if missing
    if "schedules" not in existing_tables:
        Schedule.__table__.create(bind=engine)

    # Create schedule_overrides table if missing
    if "schedule_overrides" not in existing_tables:
        ScheduleOverride.__table__.create(bind=engine)

    # Add crash_count column if missing (for upgrades)
    if "schedules" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("schedules")]
        if "crash_count" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE schedules ADD COLUMN crash_count INTEGER DEFAULT 0")
                )
                conn.commit()

        # Add max_concurrency column if missing (for upgrades)
        if "max_concurrency" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE schedules ADD COLUMN max_concurrency INTEGER DEFAULT 3")
                )
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
    engine = create_engine(db_url, connect_args={
        "check_same_thread": False,
        "timeout": 30  # Wait up to 30s for locks
    })
    Base.metadata.create_all(bind=engine)

    # Choose journal mode based on filesystem type
    # WAL mode doesn't work reliably on network filesystems and can cause corruption
    is_network = _is_network_path(project_dir)
    journal_mode = "DELETE" if is_network else "WAL"

    with engine.connect() as conn:
        conn.execute(text(f"PRAGMA journal_mode={journal_mode}"))
        conn.execute(text("PRAGMA busy_timeout=30000"))
        conn.commit()

    # Migrate existing databases
    _migrate_add_in_progress_column(engine)
    _migrate_fix_null_boolean_fields(engine)
    _migrate_add_dependencies_column(engine)
    _migrate_add_testing_columns(engine)

    # Migrate to add schedules tables
    _migrate_add_schedules_tables(engine)

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
