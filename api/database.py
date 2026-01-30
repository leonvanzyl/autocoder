"""
Database Models and Connection
==============================

SQLite database schema for feature storage using SQLAlchemy.

Concurrency Protection:
- WAL mode for better concurrent read/write access
- Busy timeout (30s) to handle lock contention
- Connection-level retries for transient errors
"""

import logging
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Module logger
logger = logging.getLogger(__name__)

# SQLite configuration constants
SQLITE_BUSY_TIMEOUT_MS = 30000  # 30 seconds
SQLITE_MAX_RETRIES = 3
SQLITE_RETRY_DELAY_MS = 100  # Start with 100ms, exponential backoff


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


def get_robust_connection(db_path: Path) -> sqlite3.Connection:
    """
    Get a robust SQLite connection with proper settings for concurrent access.

    This should be used by all code that accesses the database directly via sqlite3
    (not through SQLAlchemy). It ensures consistent settings across all access points.

    Settings applied:
    - WAL mode for better concurrency (unless on network filesystem)
    - Busy timeout of 30 seconds
    - Synchronous mode NORMAL for balance of safety and performance

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Configured sqlite3.Connection

    Raises:
        sqlite3.Error: If connection cannot be established
    """
    conn = sqlite3.connect(str(db_path), timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)

    # Set busy timeout (in milliseconds for sqlite3)
    conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")

    # Enable WAL mode (only for local filesystems)
    if not _is_network_path(db_path):
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            # WAL mode might fail on some systems, fall back to default
            pass

    # Synchronous NORMAL provides good balance of safety and performance
    conn.execute("PRAGMA synchronous = NORMAL")

    return conn


@contextmanager
def robust_db_connection(db_path: Path):
    """
    Context manager for robust SQLite connections with automatic cleanup.

    Usage:
        with robust_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM features")

    Args:
        db_path: Path to the SQLite database file

    Yields:
        Configured sqlite3.Connection
    """
    conn = None
    try:
        conn = get_robust_connection(db_path)
        yield conn
    finally:
        if conn:
            conn.close()


def execute_with_retry(
    db_path: Path,
    query: str,
    params: tuple = (),
    fetch: str = "none",
    max_retries: int = SQLITE_MAX_RETRIES
) -> Any:
    """
    Execute a SQLite query with automatic retry on transient errors.

    Handles SQLITE_BUSY and SQLITE_LOCKED errors with exponential backoff.

    Args:
        db_path: Path to the SQLite database file
        query: SQL query to execute
        params: Query parameters (tuple)
        fetch: What to fetch - "none", "one", "all"
        max_retries: Maximum number of retry attempts

    Returns:
        Query result based on fetch parameter

    Raises:
        sqlite3.Error: If query fails after all retries
    """
    last_error = None
    delay = SQLITE_RETRY_DELAY_MS / 1000  # Convert to seconds

    for attempt in range(max_retries + 1):
        try:
            with robust_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

                if fetch == "one":
                    result = cursor.fetchone()
                elif fetch == "all":
                    result = cursor.fetchall()
                else:
                    conn.commit()
                    result = cursor.rowcount

                return result

        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            # Retry on lock/busy errors
            if "locked" in error_msg or "busy" in error_msg:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        f"Database busy/locked (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                    continue
            raise
        except sqlite3.DatabaseError as e:
            # Log corruption errors clearly
            error_msg = str(e).lower()
            if "malformed" in error_msg or "corrupt" in error_msg:
                logger.error(f"DATABASE CORRUPTION DETECTED: {e}")
            raise

    # If we get here, all retries failed
    raise last_error or sqlite3.OperationalError("Query failed after all retries")


def check_database_health(db_path: Path) -> dict:
    """
    Check the health of a SQLite database.

    Returns:
        Dict with:
        - healthy (bool): True if database passes integrity check
        - journal_mode (str): Current journal mode (WAL/DELETE/etc)
        - error (str, optional): Error message if unhealthy
    """
    if not db_path.exists():
        return {"healthy": False, "error": "Database file does not exist"}

    try:
        with robust_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Check integrity
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]

            # Get journal mode
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]

            if integrity.lower() == "ok":
                return {
                    "healthy": True,
                    "journal_mode": journal_mode,
                    "integrity": integrity
                }
            else:
                return {
                    "healthy": False,
                    "journal_mode": journal_mode,
                    "error": f"Integrity check failed: {integrity}"
                }

    except sqlite3.Error as e:
        return {"healthy": False, "error": str(e)}


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
    """Legacy migration - handles testing columns that were removed from the model.

    The testing_in_progress and last_tested_at columns were removed from the
    Feature model as part of simplifying the testing agent architecture.
    Multiple testing agents can now test the same feature concurrently
    without coordination.

    This migration ensures these columns are nullable so INSERTs don't fail
    on databases that still have them with NOT NULL constraints.
    """
    with engine.connect() as conn:
        # Check if testing_in_progress column exists with NOT NULL
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = {row[1]: {"notnull": row[3], "dflt_value": row[4]} for row in result.fetchall()}

        if "testing_in_progress" in columns and columns["testing_in_progress"]["notnull"]:
            # SQLite doesn't support ALTER COLUMN, need to recreate table
            # Instead, we'll use a workaround: create a new table, copy data, swap
            logger.info("Migrating testing_in_progress column to nullable...")

            try:
                # Step 1: Create new table without NOT NULL on testing columns
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS features_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        priority INTEGER NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        steps JSON NOT NULL,
                        passes BOOLEAN NOT NULL DEFAULT 0,
                        in_progress BOOLEAN NOT NULL DEFAULT 0,
                        dependencies JSON,
                        testing_in_progress BOOLEAN DEFAULT 0,
                        last_tested_at DATETIME
                    )
                """))

                # Step 2: Copy data
                conn.execute(text("""
                    INSERT INTO features_new
                    SELECT id, priority, category, name, description, steps, passes, in_progress,
                           dependencies, testing_in_progress, last_tested_at
                    FROM features
                """))

                # Step 3: Drop old table and rename
                conn.execute(text("DROP TABLE features"))
                conn.execute(text("ALTER TABLE features_new RENAME TO features"))

                # Step 4: Recreate indexes
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_id ON features (id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_priority ON features (priority)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_passes ON features (passes)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_features_in_progress ON features (in_progress)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_feature_status ON features (passes, in_progress)"))

                conn.commit()
                logger.info("Successfully migrated testing columns to nullable")
            except Exception as e:
                logger.error(f"Failed to migrate testing columns: {e}")
                conn.rollback()
                raise


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

    Uses a cache to avoid creating new engines for each request, which improves
    performance by reusing database connections.

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    cache_key = project_dir.as_posix()

    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

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

    # Cache the engine and session maker
    _engine_cache[cache_key] = (engine, SessionLocal)

    return engine, SessionLocal


def dispose_engine(project_dir: Path) -> bool:
    """Dispose of and remove the cached engine for a project.

    This closes all database connections, releasing file locks on Windows.
    Should be called before deleting the database file.

    Returns:
        True if an engine was disposed, False if no engine was cached.
    """
    cache_key = project_dir.as_posix()

    if cache_key in _engine_cache:
        engine, _ = _engine_cache.pop(cache_key)
        engine.dispose()
        return True

    return False


# Global session maker - will be set when server starts
_session_maker: Optional[sessionmaker] = None

# Engine cache to avoid creating new engines for each request
# Key: project directory path (as posix string), Value: (engine, SessionLocal)
_engine_cache: dict[str, tuple] = {}


def set_session_maker(session_maker: sessionmaker) -> None:
    """Set the global session maker."""
    global _session_maker
    _session_maker = session_maker


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.

    Yields a database session and ensures it's closed after use.
    Properly rolls back on error to prevent PendingRollbackError.
    """
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call set_session_maker first.")

    db = _session_maker()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
