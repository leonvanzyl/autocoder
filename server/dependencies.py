"""
Server Dependencies
===================

FastAPI dependencies for common validation patterns.
"""

import sys
from pathlib import Path

from fastapi import HTTPException


def _get_detach_module():
    """Lazy import of detach module."""
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import detach
    return detach


def _get_registry_module():
    """Lazy import of registry module."""
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from registry import get_project_path
    return get_project_path


def validate_project_not_detached(project_name: str) -> Path:
    """Validate that a project is not detached.

    This dependency ensures that database operations are not performed
    on detached projects, which would cause empty database recreation.

    Args:
        project_name: The project name to validate

    Returns:
        Path to the project directory if accessible

    Raises:
        HTTPException 404: If project not found in registry
        HTTPException 409: If project is detached (Conflict)
    """
    get_project_path = _get_registry_module()
    detach = _get_detach_module()

    project_dir = get_project_path(project_name)
    if project_dir is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}"
        )

    if detach.is_project_detached(project_dir):
        raise HTTPException(
            status_code=409,
            detail=f"Project '{project_name}' is detached. Reattach to access features."
        )

    return project_dir


def check_project_detached_for_background(project_dir: Path) -> bool:
    """Check if a project is detached (for background services).

    Unlike validate_project_not_detached, this doesn't raise exceptions.
    It's meant for background services that should silently skip detached projects.

    Args:
        project_dir: Path to the project directory

    Returns:
        True if project is detached, False otherwise
    """
    detach = _get_detach_module()
    return bool(detach.is_project_detached(project_dir))
