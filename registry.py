"""
Project Registry Module
=======================

Cross-platform project registry for storing project name to path mappings.
Uses SQLite database stored at ~/.autocoder/registry.db.
"""

import logging
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Module logger
logger = logging.getLogger(__name__)


# =============================================================================
# Model Configuration (Single Source of Truth)
# =============================================================================

# Available models with display names (Claude models)
# To add a new model: add an entry here with {"id": "model-id", "name": "Display Name"}
CLAUDE_MODELS = [
    {"id": "claude-opus-4-5-20251101", "name": "Claude Opus 4.5"},
    {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5"},
]

# Common Ollama models for local inference
OLLAMA_MODELS = [
    {"id": "llama3.3:70b", "name": "Llama 3.3 70B"},
    {"id": "llama3.2:latest", "name": "Llama 3.2"},
    {"id": "codellama:34b", "name": "Code Llama 34B"},
    {"id": "deepseek-coder:33b", "name": "DeepSeek Coder 33B"},
    {"id": "qwen2.5:72b", "name": "Qwen 2.5 72B"},
    {"id": "mistral:latest", "name": "Mistral"},
]

# Default to Claude models (will be overridden if Ollama is detected)
AVAILABLE_MODELS = CLAUDE_MODELS

# List of valid model IDs (includes both Claude and Ollama models)
VALID_MODELS = [m["id"] for m in CLAUDE_MODELS] + [m["id"] for m in OLLAMA_MODELS]

# Default model and settings
DEFAULT_MODEL = "claude-opus-4-5-20251101"
DEFAULT_OLLAMA_MODEL = "llama3.3:70b"
DEFAULT_YOLO_MODE = False

# SQLite connection settings
SQLITE_TIMEOUT = 30  # seconds to wait for database lock
SQLITE_MAX_RETRIES = 3  # number of retry attempts on busy database


# =============================================================================
# Exceptions
# =============================================================================

class RegistryError(Exception):
    """Base registry exception."""
    pass


class RegistryNotFound(RegistryError):
    """Registry file doesn't exist."""
    pass


class RegistryCorrupted(RegistryError):
    """Registry database is corrupted."""
    pass


class RegistryPermissionDenied(RegistryError):
    """Can't read/write registry file."""
    pass


# =============================================================================
# SQLAlchemy Model
# =============================================================================

Base = declarative_base()


class Project(Base):
    """SQLAlchemy model for registered projects."""
    __tablename__ = "projects"

    name = Column(String(50), primary_key=True, index=True)
    path = Column(String, nullable=False)  # POSIX format for cross-platform
    created_at = Column(DateTime, nullable=False)
    default_concurrency = Column(Integer, nullable=False, default=3)


class Settings(Base):
    """SQLAlchemy model for global settings (key-value store)."""
    __tablename__ = "settings"

    key = Column(String(50), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, nullable=False)


# =============================================================================
# Database Connection
# =============================================================================

# Module-level singleton for database engine with thread-safe initialization
_engine = None
_SessionLocal = None
_engine_lock = threading.Lock()


def get_config_dir() -> Path:
    """
    Get the config directory: ~/.autocoder/

    Returns:
        Path to ~/.autocoder/ (created if it doesn't exist)
    """
    config_dir = Path.home() / ".autocoder"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_registry_path() -> Path:
    """Get the path to the registry database."""
    return get_config_dir() / "registry.db"


def _get_engine():
    """
    Get or create the database engine (thread-safe singleton pattern).

    Returns:
        Tuple of (engine, SessionLocal)
    """
    global _engine, _SessionLocal

    # Double-checked locking for thread safety
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                db_path = get_registry_path()
                db_url = f"sqlite:///{db_path.as_posix()}"
                _engine = create_engine(
                    db_url,
                    connect_args={
                        "check_same_thread": False,
                        "timeout": SQLITE_TIMEOUT,
                    }
                )
                Base.metadata.create_all(bind=_engine)
                _migrate_add_default_concurrency(_engine)
                _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
                logger.debug("Initialized registry database at: %s", db_path)

    return _engine, _SessionLocal


def _migrate_add_default_concurrency(engine) -> None:
    """Add default_concurrency column if missing (for existing databases)."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(projects)"))
        columns = [row[1] for row in result.fetchall()]
        if "default_concurrency" not in columns:
            conn.execute(text(
                "ALTER TABLE projects ADD COLUMN default_concurrency INTEGER DEFAULT 3"
            ))
            conn.commit()
            logger.info("Migrated projects table: added default_concurrency column")


@contextmanager
def _get_session():
    """
    Context manager for database sessions with automatic commit/rollback.

    Includes retry logic for SQLite busy database errors.

    Yields:
        SQLAlchemy session
    """
    _, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _with_retry(func, *args, **kwargs):
    """
    Execute a database operation with retry logic for busy database.

    Args:
        func: Function to execute
        *args, **kwargs: Arguments to pass to the function

    Returns:
        Result of the function

    Raises:
        Last exception if all retries fail
    """
    last_error = None
    for attempt in range(SQLITE_MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "database is locked" in error_str or "sqlite_busy" in error_str:
                if attempt < SQLITE_MAX_RETRIES - 1:
                    wait_time = (2 ** attempt) * 0.1  # Exponential backoff: 0.1s, 0.2s, 0.4s
                    logger.warning(
                        "Database busy, retrying in %.1fs (attempt %d/%d)",
                        wait_time, attempt + 1, SQLITE_MAX_RETRIES
                    )
                    time.sleep(wait_time)
                    continue
            raise
    raise last_error


# =============================================================================
# Project CRUD Functions
# =============================================================================

def register_project(name: str, path: Path) -> None:
    """
    Register a new project in the registry.

    Args:
        name: The project name (unique identifier).
        path: The absolute path to the project directory.

    Raises:
        ValueError: If project name is invalid or path is not absolute.
        RegistryError: If a project with that name already exists.
    """
    # Validate name
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise ValueError(
            "Invalid project name. Use only letters, numbers, hyphens, "
            "and underscores (1-50 chars)."
        )

    # Ensure path is absolute
    path = Path(path).resolve()

    with _get_session() as session:
        existing = session.query(Project).filter(Project.name == name).first()
        if existing:
            logger.warning("Attempted to register duplicate project: %s", name)
            raise RegistryError(f"Project '{name}' already exists in registry")

        project = Project(
            name=name,
            path=path.as_posix(),
            created_at=datetime.now()
        )
        session.add(project)

    logger.info("Registered project '%s' at path: %s", name, path)


def unregister_project(name: str) -> bool:
    """
    Remove a project from the registry.

    Args:
        name: The project name to remove.

    Returns:
        True if removed, False if project wasn't found.
    """
    with _get_session() as session:
        project = session.query(Project).filter(Project.name == name).first()
        if not project:
            logger.debug("Attempted to unregister non-existent project: %s", name)
            return False

        session.delete(project)

    logger.info("Unregistered project: %s", name)
    return True


def get_project_path(name: str) -> Path | None:
    """
    Look up a project's path by name.

    Args:
        name: The project name.

    Returns:
        The project Path, or None if not found.
    """
    _, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        project = session.query(Project).filter(Project.name == name).first()
        if project is None:
            return None
        return Path(project.path)
    finally:
        session.close()


def list_registered_projects() -> dict[str, dict[str, Any]]:
    """
    Get all registered projects.

    Returns:
        Dictionary mapping project names to their info dictionaries.
    """
    _, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        projects = session.query(Project).all()
        return {
            p.name: {
                "path": p.path,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "default_concurrency": getattr(p, 'default_concurrency', 3) or 3
            }
            for p in projects
        }
    finally:
        session.close()


def get_project_info(name: str) -> dict[str, Any] | None:
    """
    Get full info about a project.

    Args:
        name: The project name.

    Returns:
        Project info dictionary, or None if not found.
    """
    _, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        project = session.query(Project).filter(Project.name == name).first()
        if project is None:
            return None
        return {
            "path": project.path,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "default_concurrency": getattr(project, 'default_concurrency', 3) or 3
        }
    finally:
        session.close()


def update_project_path(name: str, new_path: Path) -> bool:
    """
    Update a project's path (for relocating projects).

    Args:
        name: The project name.
        new_path: The new absolute path.

    Returns:
        True if updated, False if project wasn't found.
    """
    new_path = Path(new_path).resolve()

    with _get_session() as session:
        project = session.query(Project).filter(Project.name == name).first()
        if not project:
            return False

        project.path = new_path.as_posix()

    return True


def get_project_concurrency(name: str) -> int:
    """
    Get project's default concurrency (1-5).

    Args:
        name: The project name.

    Returns:
        The default concurrency value (defaults to 3 if not set or project not found).
    """
    _, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        project = session.query(Project).filter(Project.name == name).first()
        if project is None:
            return 3
        return getattr(project, 'default_concurrency', 3) or 3
    finally:
        session.close()


def set_project_concurrency(name: str, concurrency: int) -> bool:
    """
    Set project's default concurrency (1-5).

    Args:
        name: The project name.
        concurrency: The concurrency value (1-5).

    Returns:
        True if updated, False if project wasn't found.

    Raises:
        ValueError: If concurrency is not between 1 and 5.
    """
    if concurrency < 1 or concurrency > 5:
        raise ValueError("concurrency must be between 1 and 5")

    with _get_session() as session:
        project = session.query(Project).filter(Project.name == name).first()
        if not project:
            return False

        project.default_concurrency = concurrency

    logger.info("Set project '%s' default_concurrency to %d", name, concurrency)
    return True


# =============================================================================
# Validation Functions
# =============================================================================

def validate_project_path(path: Path) -> tuple[bool, str]:
    """
    Validate that a project path is accessible and writable.

    Args:
        path: The path to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    path = Path(path).resolve()

    # Check if path exists
    if not path.exists():
        return False, f"Path does not exist: {path}"

    # Check if it's a directory
    if not path.is_dir():
        return False, f"Path is not a directory: {path}"

    # Check read permissions
    if not os.access(path, os.R_OK):
        return False, f"No read permission: {path}"

    # Check write permissions
    if not os.access(path, os.W_OK):
        return False, f"No write permission: {path}"

    return True, ""


def cleanup_stale_projects() -> list[str]:
    """
    Remove projects from registry whose paths no longer exist.

    Returns:
        List of removed project names.
    """
    removed = []

    with _get_session() as session:
        projects = session.query(Project).all()
        for project in projects:
            path = Path(project.path)
            if not path.exists():
                session.delete(project)
                removed.append(project.name)

    if removed:
        logger.info("Cleaned up stale projects: %s", removed)

    return removed


def list_valid_projects() -> list[dict[str, Any]]:
    """
    List all projects that have valid, accessible paths.

    Returns:
        List of project info dicts with additional 'name' field.
    """
    _, SessionLocal = _get_engine()
    session = SessionLocal()
    try:
        projects = session.query(Project).all()
        valid = []
        for p in projects:
            path = Path(p.path)
            is_valid, _ = validate_project_path(path)
            if is_valid:
                valid.append({
                    "name": p.name,
                    "path": p.path,
                    "created_at": p.created_at.isoformat() if p.created_at else None
                })
        return valid
    finally:
        session.close()


# =============================================================================
# Settings CRUD Functions
# =============================================================================

def get_setting(key: str, default: str | None = None) -> str | None:
    """
    Get a setting value by key.

    Args:
        key: The setting key.
        default: Default value if setting doesn't exist or on DB error.

    Returns:
        The setting value, or default if not found or on error.
    """
    try:
        _, SessionLocal = _get_engine()
        session = SessionLocal()
        try:
            setting = session.query(Settings).filter(Settings.key == key).first()
            return setting.value if setting else default
        finally:
            session.close()
    except Exception as e:
        logger.warning("Failed to read setting '%s': %s", key, e)
        return default


def set_setting(key: str, value: str) -> None:
    """
    Set a setting value (creates or updates).

    Args:
        key: The setting key.
        value: The setting value.
    """
    with _get_session() as session:
        setting = session.query(Settings).filter(Settings.key == key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.now()
        else:
            setting = Settings(
                key=key,
                value=value,
                updated_at=datetime.now()
            )
            session.add(setting)

    logger.debug("Set setting '%s' = '%s'", key, value)


def get_all_settings() -> dict[str, str]:
    """
    Get all settings as a dictionary.

    Returns:
        Dictionary mapping setting keys to values.
    """
    try:
        _, SessionLocal = _get_engine()
        session = SessionLocal()
        try:
            settings = session.query(Settings).all()
            return {s.key: s.value for s in settings}
        finally:
            session.close()
    except Exception as e:
        logger.warning("Failed to read settings: %s", e)
        return {}
