"""
Base Analyzer
=============

Abstract base class for all stack analyzers.
Each analyzer detects a specific tech stack and extracts relevant information.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypedDict


class RouteInfo(TypedDict):
    """Information about a detected route."""
    path: str
    method: str  # GET, POST, PUT, DELETE, etc.
    handler: str  # Function or component name
    file: str  # Source file path


class ComponentInfo(TypedDict):
    """Information about a detected component."""
    name: str
    file: str
    type: str  # page, component, layout, etc.


class EndpointInfo(TypedDict):
    """Information about an API endpoint."""
    path: str
    method: str
    handler: str
    file: str
    description: str  # Generated description


class AnalysisResult(TypedDict):
    """Result of analyzing a codebase with a specific analyzer."""
    stack_name: str
    confidence: float  # 0.0 to 1.0
    routes: list[RouteInfo]
    components: list[ComponentInfo]
    endpoints: list[EndpointInfo]
    entry_point: str | None
    config_files: list[str]
    dependencies: dict[str, str]  # name: version
    metadata: dict  # Additional stack-specific info


class BaseAnalyzer(ABC):
    """
    Abstract base class for stack analyzers.

    Each analyzer is responsible for:
    1. Detecting if a codebase uses its stack (can_analyze)
    2. Extracting routes, components, and endpoints (analyze)
    """

    def __init__(self, project_dir: Path):
        """
        Initialize the analyzer.

        Args:
            project_dir: Path to the project directory to analyze
        """
        self.project_dir = project_dir

    @property
    @abstractmethod
    def stack_name(self) -> str:
        """The name of the stack this analyzer handles (e.g., 'react', 'nextjs')."""
        pass

    @abstractmethod
    def can_analyze(self) -> tuple[bool, float]:
        """
        Check if this analyzer can handle the codebase.

        Returns:
            (can_handle, confidence) where:
            - can_handle: True if the analyzer recognizes the stack
            - confidence: 0.0 to 1.0 indicating how confident the detection is
        """
        pass

    @abstractmethod
    def analyze(self) -> AnalysisResult:
        """
        Analyze the codebase and extract information.

        Returns:
            AnalysisResult with detected routes, components, endpoints, etc.
        """
        pass

    def _read_file_safe(self, path: Path, max_size: int = 1024 * 1024) -> str | None:
        """
        Safely read a file, returning None if it doesn't exist or is too large.

        Args:
            path: Path to the file
            max_size: Maximum file size in bytes (default 1MB)

        Returns:
            File contents or None
        """
        if not path.exists():
            return None

        try:
            if path.stat().st_size > max_size:
                return None
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def _find_files(self, pattern: str, exclude_dirs: list[str] | None = None) -> list[Path]:
        """
        Find files matching a glob pattern, excluding common non-source directories.

        Args:
            pattern: Glob pattern (e.g., "**/*.tsx")
            exclude_dirs: Additional directories to exclude

        Returns:
            List of matching file paths
        """
        default_exclude = [
            "node_modules",
            "venv",
            ".venv",
            "__pycache__",
            ".git",
            "dist",
            "build",
            ".next",
            ".nuxt",
            "coverage",
        ]

        if exclude_dirs:
            default_exclude.extend(exclude_dirs)

        results = []
        for path in self.project_dir.glob(pattern):
            # Check if any parent is in exclude list
            parts = path.relative_to(self.project_dir).parts
            if not any(part in default_exclude for part in parts):
                results.append(path)

        return results
