"""
Project Registry Module
=======================

Cross-platform project registry for storing project name to path mappings.
Uses SQLite database stored at ~/.autocoder/registry.db.
"""

import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, String, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Module logger
logger = logging.getLogger(__name__)


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


# =============================================================================
# Database Connection
# =============================================================================

# Module-level singleton for database engine
_engine = None
_SessionLocal = None


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
    Get or create the database engine (singleton pattern).

    Returns:
        Tuple of (engine, SessionLocal)
    """
    global _engine, _SessionLocal

    if _engine is None:
        db_path = get_registry_path()
        db_url = f"sqlite:///{db_path.as_posix()}"
        _engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=_engine)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.debug("Initialized registry database at: %s", db_path)

    return _engine, _SessionLocal


@contextmanager
def _get_session():
    """
    Context manager for database sessions with automatic commit/rollback.

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
                "created_at": p.created_at.isoformat() if p.created_at else None
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
            "created_at": project.created_at.isoformat() if project.created_at else None
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
