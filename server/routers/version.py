"""
Version Router
==============

API endpoints for version information.
"""

# Import from parent package to access root-level version module
import sys
from pathlib import Path

from fastapi import APIRouter

# Add parent directory to path to import version module
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from version import get_version_dict, get_version_string

router = APIRouter(prefix="/api/version", tags=["version"])


@router.get("")
async def get_version():
    """
    Get version information.

    Returns:
        Version info including version string, edition, and build date.
    """
    return get_version_dict()


@router.get("/string")
async def get_version_as_string():
    """
    Get version as a simple string.

    Returns:
        Version string like "2026.1.0.0 - Chance Edition"
    """
    return {"version": get_version_string()}
