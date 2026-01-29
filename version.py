"""
Version Module
==============

Provides version information and utilities for the Autocoder application.
Reads version data from VERSION.json for single source of truth.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to VERSION.json relative to this file
VERSION_FILE = Path(__file__).parent / "VERSION.json"


@dataclass
class VersionInfo:
    """Version information container."""
    version: str
    edition: str
    year: int
    major: int
    minor: int
    patch: int
    build_date: str
    description: str

    @property
    def full_version(self) -> str:
        """Return full version string with edition."""
        return f"{self.version} - {self.edition}"

    @property
    def short_version(self) -> str:
        """Return short version string (e.g., '2026.1.0')."""
        return f"{self.year}.{self.major}.{self.minor}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "edition": self.edition,
            "year": self.year,
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "buildDate": self.build_date,
            "description": self.description,
            "fullVersion": self.full_version,
            "shortVersion": self.short_version,
        }


def load_version() -> VersionInfo:
    """
    Load version information from VERSION.json.

    Returns:
        VersionInfo object with version details.

    Raises:
        FileNotFoundError: If VERSION.json doesn't exist.
        json.JSONDecodeError: If VERSION.json is malformed.
    """
    if not VERSION_FILE.exists():
        logger.warning("VERSION.json not found, using defaults")
        return VersionInfo(
            version="0.0.0.0",
            edition="Development",
            year=2026,
            major=0,
            minor=0,
            patch=0,
            build_date="unknown",
            description="Development version",
        )

    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return VersionInfo(
        version=data.get("version", "0.0.0.0"),
        edition=data.get("edition", "Unknown"),
        year=data.get("year", 2026),
        major=data.get("major", 0),
        minor=data.get("minor", 0),
        patch=data.get("patch", 0),
        build_date=data.get("buildDate", "unknown"),
        description=data.get("description", ""),
    )


def get_version_string() -> str:
    """Get the full version string for display."""
    info = load_version()
    return info.full_version


def get_version_dict() -> dict[str, Any]:
    """Get version information as a dictionary."""
    return load_version().to_dict()


# Module-level cached version info
_cached_version: VersionInfo | None = None


def get_version() -> VersionInfo:
    """
    Get cached version information.

    Returns:
        Cached VersionInfo object (loaded once per process).
    """
    global _cached_version
    if _cached_version is None:
        _cached_version = load_version()
    return _cached_version


# Convenience exports
__version__ = get_version().version if VERSION_FILE.exists() else "0.0.0.0"
__edition__ = get_version().edition if VERSION_FILE.exists() else "Development"
