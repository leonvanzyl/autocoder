"""
Filesystem Router
==================

API endpoints for browsing the filesystem for project folder selection.
Provides cross-platform support for Windows, macOS, and Linux.
"""

import logging
import os
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    CreateDirectoryRequest,
    DirectoryEntry,
    DirectoryListResponse,
    DriveInfo,
    PathValidationResponse,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Module logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


# =============================================================================
# Platform-Specific Blocked Paths
# =============================================================================

# Windows blocked paths
WINDOWS_BLOCKED = {
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\System Volume Information",
    "C:\\$Recycle.Bin",
    "C:\\Recovery",
}

# macOS blocked paths
MACOS_BLOCKED = {
    "/System",
    "/Library",
    "/private",
    "/usr",
    "/bin",
    "/sbin",
    "/etc",
    "/var",
    "/Volumes",
    "/cores",
    "/opt",
}

# Linux blocked paths
LINUX_BLOCKED = {
    "/etc",
    "/var",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/proc",
    "/sys",
    "/dev",
    "/root",
    "/lib",
    "/lib64",
    "/run",
    "/tmp",
    "/opt",
}

# Universal blocked paths (relative to home directory)
UNIVERSAL_BLOCKED_RELATIVE = {
    ".ssh",
    ".aws",
    ".gnupg",
    ".config/gh",
    ".netrc",
    ".docker",
    ".kube",
    ".terraform",
}

# Patterns for files that should not be shown
HIDDEN_PATTERNS = [
    r"^\.env",           # .env files
    r".*\.key$",         # Key files
    r".*\.pem$",         # PEM files
    r".*credentials.*",  # Credential files
    r".*secrets.*",      # Secrets files
]


def get_blocked_paths() -> set[Path]:
    """Get the set of blocked paths for the current platform."""
    home = Path.home()
    blocked = set()

    # Add platform-specific blocked paths
    if sys.platform == "win32":
        for p in WINDOWS_BLOCKED:
            blocked.add(Path(p).resolve())
    elif sys.platform == "darwin":
        for p in MACOS_BLOCKED:
            blocked.add(Path(p).resolve())
    else:  # Linux
        for p in LINUX_BLOCKED:
            blocked.add(Path(p).resolve())

    # Add universal blocked paths (relative to home)
    for rel in UNIVERSAL_BLOCKED_RELATIVE:
        blocked.add((home / rel).resolve())

    return blocked


def is_path_blocked(path: Path) -> bool:
    """Check if a path is in the blocked list."""
    try:
        resolved = path.resolve()
    except (OSError, ValueError):
        return True  # Can't resolve = blocked

    # Allow paths under the workspace root even if parent is blocked (/opt/etc)
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        return False

    blocked_paths = get_blocked_paths()

    # Check if path is exactly a blocked path or inside one
    for blocked in blocked_paths:
        try:
            resolved.relative_to(blocked)
            return True
        except ValueError:
            pass

        # Also check if blocked is inside path (for parent directories)
        if resolved == blocked:
            return True

    return False


def is_hidden_file(path: Path) -> bool:
    """Check if a file/directory is hidden (cross-platform)."""
    name = path.name

    # Unix-style: starts with dot
    if name.startswith('.'):
        return True

    # Windows: check FILE_ATTRIBUTE_HIDDEN
    if sys.platform == "win32":
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs != -1 and (attrs & 0x02):  # FILE_ATTRIBUTE_HIDDEN
                return True
        except Exception:
            pass

    return False


def matches_blocked_pattern(name: str) -> bool:
    """Check if filename matches a blocked pattern."""
    for pattern in HIDDEN_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            return True
    return False


def is_unc_path(path_str: str) -> bool:
    """Check if path is a Windows UNC path (network share)."""
    return path_str.startswith("\\\\") or path_str.startswith("//")


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/list", response_model=DirectoryListResponse)
async def list_directory(
    path: str | None = Query(None, description="Directory path to list (defaults to home)"),
    show_hidden: bool = Query(False, description="Include hidden files"),
):
    """
    List contents of a directory.

    Returns directories only (for folder selection).
    On Windows, includes available drives.
    """
    # Default to home directory
    if path is None or path == "":
        target = Path.home()
    else:
        # Security: Block UNC paths
        if is_unc_path(path):
            logger.warning("Blocked UNC path access attempt: %s", path)
            raise HTTPException(
                status_code=403,
                detail="Network paths (UNC) are not allowed"
            )
        target = Path(path)

    # Resolve symlinks and get absolute path
    try:
        target = target.resolve()
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}")

    # Security: Check if path is blocked
    if is_path_blocked(target):
        logger.warning("Blocked access to restricted path: %s", target)
        raise HTTPException(
            status_code=403,
            detail="Access to this directory is not allowed"
        )

    # Check if path exists and is a directory
    if not target.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Check read permission
    if not os.access(target, os.R_OK):
        raise HTTPException(status_code=403, detail="No read permission")

    # List directory contents
    entries = []
    try:
        for item in sorted(target.iterdir(), key=lambda x: x.name.lower()):
            # Skip if blocked pattern
            if matches_blocked_pattern(item.name):
                continue

            # Check if hidden
            hidden = is_hidden_file(item)
            if hidden and not show_hidden:
                continue

            # Security: Skip if item path is blocked
            if is_path_blocked(item):
                continue

            # Only include directories for folder browsing
            if item.is_dir():
                try:
                    # Check if directory has any subdirectories
                    has_children = False
                    try:
                        for child in item.iterdir():
                            if child.is_dir() and not is_path_blocked(child):
                                has_children = True
                                break
                    except (PermissionError, OSError):
                        pass  # Can't read = assume no children

                    entries.append(DirectoryEntry(
                        name=item.name,
                        path=item.as_posix(),
                        is_directory=True,
                        is_hidden=hidden,
                        size=None,
                        has_children=has_children,
                    ))
                except Exception:
                    pass  # Skip items we can't process

    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error reading directory: {e}")

    # Calculate parent path
    parent_path = None
    if target != target.parent:  # Not at root
        parent = target.parent
        # Don't expose parent if it's blocked
        if not is_path_blocked(parent):
            parent_path = parent.as_posix()

    # Get drives on Windows
    drives = None
    if sys.platform == "win32":
        drives = get_windows_drives()

    return DirectoryListResponse(
        current_path=target.as_posix(),
        parent_path=parent_path,
        entries=entries,
        drives=drives,
    )


@router.get("/drives", response_model=list[DriveInfo] | None)
async def list_drives():
    """
    List available drives (Windows only).

    Returns null on non-Windows platforms.
    """
    if sys.platform != "win32":
        return None

    return get_windows_drives()


def get_windows_drives() -> list[DriveInfo]:
    """Get list of available drives on Windows."""
    drives = []

    try:
        import ctypes
        import string

        # Get bitmask of available drives
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()

        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                drive_path = f"{letter}:\\"
                try:
                    # Try to get volume label
                    volume_name = ctypes.create_unicode_buffer(1024)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        drive_path,
                        volume_name,
                        1024,
                        None, None, None, None, 0
                    )
                    label = volume_name.value or f"Local Disk ({letter}:)"
                except Exception:
                    label = f"Drive ({letter}:)"

                # Check if drive is accessible
                available = os.path.exists(drive_path)

                drives.append(DriveInfo(
                    letter=letter,
                    label=label,
                    available=available,
                ))
    except Exception:
        # Fallback: just list C: drive
        drives.append(DriveInfo(letter="C", label="Local Disk (C:)", available=True))

    return drives


@router.post("/validate", response_model=PathValidationResponse)
async def validate_path(path: str = Query(..., description="Path to validate")):
    """
    Validate if a path is accessible and writable.

    Used to check a path before creating a project there.
    """
    # Security: Block UNC paths
    if is_unc_path(path):
        return PathValidationResponse(
            valid=False,
            exists=False,
            is_directory=False,
            can_read=False,
            can_write=False,
            message="Network paths (UNC) are not allowed",
        )

    try:
        target = Path(path).resolve()
    except (OSError, ValueError) as e:
        return PathValidationResponse(
            valid=False,
            exists=False,
            is_directory=False,
            can_read=False,
            can_write=False,
            message=f"Invalid path: {e}",
        )

    # Security: Check if blocked
    if is_path_blocked(target):
        return PathValidationResponse(
            valid=False,
            exists=target.exists(),
            is_directory=target.is_dir() if target.exists() else False,
            can_read=False,
            can_write=False,
            message="Access to this directory is not allowed",
        )

    exists = target.exists()
    is_dir = target.is_dir() if exists else False
    can_read = os.access(target, os.R_OK) if exists else False
    can_write = os.access(target, os.W_OK) if exists else False

    # For non-existent paths, check if parent is writable
    if not exists:
        parent = target.parent
        parent_exists = parent.exists()
        parent_writable = os.access(parent, os.W_OK) if parent_exists else False
        can_write = parent_writable

    valid = is_dir and can_read and can_write if exists else can_write
    message = ""
    if not exists:
        message = "Directory does not exist (will be created)"
    elif not is_dir:
        message = "Path is not a directory"
    elif not can_read:
        message = "No read permission"
    elif not can_write:
        message = "No write permission"

    return PathValidationResponse(
        valid=valid,
        exists=exists,
        is_directory=is_dir,
        can_read=can_read,
        can_write=can_write,
        message=message,
    )


@router.post("/create-directory")
async def create_directory(request: CreateDirectoryRequest):
    """
    Create a new directory inside a parent directory.

    Used for creating project folders from the folder browser.
    """
    # Validate directory name
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Directory name cannot be empty")

    # Security: Block special directory names that could enable traversal
    if name in ('.', '..') or '..' in name:
        raise HTTPException(
            status_code=400,
            detail="Invalid directory name"
        )

    # Security: Check for invalid characters
    invalid_chars = '<>:"/\\|?*' if sys.platform == "win32" else '/'
    if any(c in name for c in invalid_chars):
        raise HTTPException(
            status_code=400,
            detail="Directory name contains invalid characters"
        )

    # Security: Block UNC paths
    if is_unc_path(request.parent_path):
        raise HTTPException(status_code=403, detail="Network paths are not allowed")

    try:
        parent = Path(request.parent_path).resolve()
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid parent path: {e}")

    # Security: Check if parent is blocked
    if is_path_blocked(parent):
        raise HTTPException(
            status_code=403,
            detail="Cannot create directory in this location"
        )

    # Check parent exists and is writable
    if not parent.exists():
        raise HTTPException(status_code=404, detail="Parent directory not found")

    if not parent.is_dir():
        raise HTTPException(status_code=400, detail="Parent path is not a directory")

    if not os.access(parent, os.W_OK):
        raise HTTPException(status_code=403, detail="No write permission")

    # Create the new directory
    new_dir = parent / name

    if new_dir.exists():
        raise HTTPException(status_code=409, detail="Directory already exists")

    try:
        new_dir.mkdir(parents=False, exist_ok=False)
        logger.info("Created directory: %s", new_dir)
    except OSError as e:
        logger.error("Failed to create directory %s: %s", new_dir, e)
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}")

    return {
        "success": True,
        "path": new_dir.as_posix(),
        "message": f"Created directory: {name}",
    }


@router.get("/home")
async def get_home_directory():
    """Get the user's home directory path."""
    home = Path.home()
    return {
        "path": home.as_posix(),
        "display_path": str(home),
    }
