"""
Shared validation utilities for the server.
"""

import re

from fastapi import HTTPException

# Compiled regex for project name validation (reused across functions)
PROJECT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,50}$')


def is_valid_project_name(name: str) -> bool:
    """
    Check if project name is valid.

    Args:
        name: Project name to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(PROJECT_NAME_PATTERN.match(name))


def validate_project_name(name: str) -> str:
    """
    Validate and sanitize project name to prevent path traversal.

    Args:
        name: Project name to validate

    Returns:
        The validated project name

    Raises:
        HTTPException: If name is invalid
    """
    if not is_valid_project_name(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name. Use only letters, numbers, hyphens, and underscores (1-50 chars)."
        )
    return name
