"""
Database Connection Management
==============================

SQLite connection utilities, session management, and engine caching.

Concurrency Protection:
- WAL mode for better concurrent read/write access
- Busy timeout (30s) to handle lock contention
- Connection-level retries for transient errors
"""

import logging
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from api.migrations import run_all_migrations
from api.models import Base

# Module logger
logger = logging.getLogger(__name__)

# SQLite configuration constants
SQLITE_BUSY_TIMEOUT_MS = 30000  # 30 seconds
SQLITE_MAX_RETRIES = 3
SQLITE_RETRY_DELAY_MS = 100  # Start with 100ms, exponential backoff

# Engine cache to avoid creating new engines for each request
# Key: project directory path (as posix string), Value: (engine, SessionLocal)
# Thread-safe: protected by _engine_cache_lock
_engine_cache: dict[str, tuple] = {}
_engine_cache_lock = threading.Lock()


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


def get_database_path(project_dir: Path) -> Path:
    """Return the path to the SQLite database for a project."""
    return project_dir / "features.db"


def get_database_url(project_dir: Path) -> str:
    """Return the SQLAlchemy database URL for a project.

    Uses POSIX-style paths (forward slashes) for cross-platform compatibility.
    """
    db_path = get_database_path(project_dir)
    return f"sqlite:///{db_path.as_posix()}"


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


def create_database(project_dir: Path) -> tuple:
    """
    Create database and return engine + session maker.

    Uses a cache to avoid creating new engines for each request, which prevents
    file descriptor leaks and improves performance by reusing database connections.

    Thread Safety:
    - Uses double-checked locking pattern to minimize lock contention
    - First check is lock-free for fast path (cache hit)
    - Lock is only acquired when creating new engines

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    cache_key = project_dir.resolve().as_posix()

    # Fast path: check cache without lock (double-checked locking pattern)
    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

    # Slow path: acquire lock and check again
    with _engine_cache_lock:
        # Double-check inside lock to prevent race condition
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

        # Run all migrations
        run_all_migrations(engine)

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Cache the engine and session maker
        _engine_cache[cache_key] = (engine, SessionLocal)
        logger.debug(f"Created new database engine for {cache_key}")

        return engine, SessionLocal


def invalidate_engine_cache(project_dir: Path) -> None:
    """
    Invalidate the engine cache for a specific project.

    Call this when you need to ensure fresh database connections, e.g.,
    after subprocess commits that may not be visible to the current connection.

    Args:
        project_dir: Directory containing the project
    """
    cache_key = project_dir.resolve().as_posix()
    with _engine_cache_lock:
        if cache_key in _engine_cache:
            engine, _ = _engine_cache[cache_key]
            try:
                engine.dispose()
            except Exception as e:
                logger.warning(f"Error disposing engine for {cache_key}: {e}")
            del _engine_cache[cache_key]
            logger.debug(f"Invalidated engine cache for {cache_key}")


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


@contextmanager
def get_db_session(project_dir: Path):
    """
    Context manager for database sessions with automatic cleanup.

    Ensures the session is properly closed on all code paths, including exceptions.
    Rolls back uncommitted changes on error to prevent PendingRollbackError.

    Usage:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).first()
            feature.passes = True
            session.commit()

    Args:
        project_dir: Path to the project directory

    Yields:
        SQLAlchemy Session object

    Raises:
        Any exception from the session operations (after rollback)
    """
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
