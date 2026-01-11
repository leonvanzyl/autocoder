"""
Shared validation utilities for the server.
"""

import re

from fastapi import HTTPException


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
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name. Use only letters, numbers, hyphens, and underscores (1-50 chars)."
        )
    return name
