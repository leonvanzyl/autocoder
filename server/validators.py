"""
Shared Validators
=================

Centralized validation functions used across the server.
"""

import re
from fastapi import HTTPException

# Regex pattern for valid project names
# - Allows: letters, numbers, hyphens, underscores
# - Length: 1-50 characters
PROJECT_NAME_REGEX = r'^[a-zA-Z0-9_-]{1,50}$'


def is_valid_project_name(name: str) -> bool:
    """
    Check if a project name is valid.

    Args:
        name: The project name to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(PROJECT_NAME_REGEX, name))


def validate_project_name(name: str) -> str:
    """
    Validate project name, raising HTTPException if invalid.

    Use this in REST API endpoints that need to reject invalid names
    with a proper HTTP error response.

    Args:
        name: The project name to validate

    Returns:
        The validated name (unchanged)

    Raises:
        HTTPException: 400 error if the name is invalid
    """
    if not is_valid_project_name(name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name. Use only letters, numbers, hyphens, and underscores (1-50 chars)."
        )
    return name
