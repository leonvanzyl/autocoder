"""
Stack Detector
==============

Orchestrates detection of tech stacks in a codebase.
Uses multiple analyzers to detect frontend, backend, and database technologies.
"""

import json
import logging
from pathlib import Path
from typing import TypedDict

from .base_analyzer import AnalysisResult

logger = logging.getLogger(__name__)


class StackInfo(TypedDict):
    """Information about a detected stack."""
    name: str
    category: str  # frontend, backend, database, other
    confidence: float
    analysis: AnalysisResult | None


class StackDetectionResult(TypedDict):
    """Complete result of stack detection."""
    project_dir: str
    detected_stacks: list[StackInfo]
    primary_frontend: str | None
    primary_backend: str | None
    database: str | None
    routes_count: int
    components_count: int
    endpoints_count: int
    all_routes: list[dict]
    all_endpoints: list[dict]
    all_components: list[dict]
    summary: str


class StackDetector:
    """
    Detects tech stacks in a codebase by running multiple analyzers.

    Usage:
        detector = StackDetector(project_dir)
        result = detector.detect()
    """

    def __init__(self, project_dir: Path):
        """
        Initialize the stack detector.

        Args:
            project_dir: Path to the project directory to analyze
        """
        self.project_dir = Path(project_dir).resolve()
        self._analyzers = []
        self._load_analyzers()

    def _load_analyzers(self) -> None:
        """Load all available analyzers."""
        # Import analyzers here to avoid circular imports
        from .node_analyzer import NodeAnalyzer
        from .python_analyzer import PythonAnalyzer
        from .react_analyzer import ReactAnalyzer
        from .vue_analyzer import VueAnalyzer

        # Order matters: frontend framework analyzers first, then backend analyzers
        self._analyzers = [
            ReactAnalyzer(self.project_dir),
            VueAnalyzer(self.project_dir),
            NodeAnalyzer(self.project_dir),
            PythonAnalyzer(self.project_dir),
        ]

    def detect(self) -> StackDetectionResult:
        """
        Run all analyzers and compile results.

        Returns:
            StackDetectionResult with all detected stacks and extracted information
        """
        detected_stacks: list[StackInfo] = []
        all_routes: list[dict] = []
        all_endpoints: list[dict] = []
        all_components: list[dict] = []

        for analyzer in self._analyzers:
            try:
                can_analyze, confidence = analyzer.can_analyze()
            except Exception:
                logger.exception(f"Warning: {analyzer.stack_name} can_analyze failed")
                continue

            if can_analyze and confidence > 0.3:  # Minimum confidence threshold
                try:
                    analysis = analyzer.analyze()

                    # Determine category
                    stack_name = analyzer.stack_name.lower()
                    # Use prefix matching to handle variants like vue-vite, vue-cli
                    if any(stack_name.startswith(prefix) for prefix in ("react", "next", "vue", "nuxt", "angular")):
                        category = "frontend"
                    elif any(stack_name.startswith(prefix) for prefix in ("express", "fastapi", "django", "flask", "nest")):
                        category = "backend"
                    elif any(stack_name.startswith(prefix) for prefix in ("postgres", "mysql", "mongo", "sqlite")):
                        category = "database"
                    else:
                        category = "other"

                    detected_stacks.append({
                        "name": analyzer.stack_name,
                        "category": category,
                        "confidence": confidence,
                        "analysis": analysis,
                    })

                    # Collect all routes, endpoints, components
                    all_routes.extend(analysis.get("routes", []))
                    all_endpoints.extend(analysis.get("endpoints", []))
                    all_components.extend(analysis.get("components", []))

                except Exception:
                    # Log but don't fail - continue with other analyzers
                    logger.exception(f"Warning: {analyzer.stack_name} analyzer failed")

        # Sort by confidence
        detected_stacks.sort(key=lambda x: x["confidence"], reverse=True)

        # Determine primary frontend and backend
        primary_frontend = None
        primary_backend = None
        database = None

        for stack in detected_stacks:
            if stack["category"] == "frontend" and primary_frontend is None:
                primary_frontend = stack["name"]
            elif stack["category"] == "backend" and primary_backend is None:
                primary_backend = stack["name"]
            elif stack["category"] == "database" and database is None:
                database = stack["name"]

        # Build summary
        stack_names = [s["name"] for s in detected_stacks]
        if stack_names:
            summary = f"Detected: {', '.join(stack_names)}"
        else:
            summary = "No recognized tech stack detected"

        if all_routes:
            summary += f" | {len(all_routes)} routes"
        if all_endpoints:
            summary += f" | {len(all_endpoints)} endpoints"
        if all_components:
            summary += f" | {len(all_components)} components"

        return {
            "project_dir": str(self.project_dir),
            "detected_stacks": detected_stacks,
            "primary_frontend": primary_frontend,
            "primary_backend": primary_backend,
            "database": database,
            "routes_count": len(all_routes),
            "components_count": len(all_components),
            "endpoints_count": len(all_endpoints),
            "all_routes": all_routes,
            "all_endpoints": all_endpoints,
            "all_components": all_components,
            "summary": summary,
        }

    def detect_quick(self) -> dict:
        """
        Quick detection without full analysis.

        Returns a simplified result with just stack names and confidence.
        Useful for UI display before full analysis.
        """
        results = []

        for analyzer in self._analyzers:
            try:
                can_analyze, confidence = analyzer.can_analyze()
            except Exception:
                logger.exception(f"Warning: {analyzer.stack_name} can_analyze failed")
                continue

            if can_analyze and confidence > 0.3:
                results.append({
                    "name": analyzer.stack_name,
                    "confidence": confidence,
                })

        results.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "project_dir": str(self.project_dir),
            "stacks": results,
            "primary": results[0]["name"] if results else None,
        }

    def to_json(self, result: StackDetectionResult) -> str:
        """Convert detection result to JSON string."""
        # Remove analysis objects for cleaner output
        clean_result = {
            **result,
            "detected_stacks": [
                {k: v for k, v in stack.items() if k != "analysis"}
                for stack in result["detected_stacks"]
            ],
        }
        return json.dumps(clean_result, indent=2)


def detect_stack(project_dir: str | Path) -> StackDetectionResult:
    """
    Convenience function to detect stack in a project.

    Args:
        project_dir: Path to the project directory

    Returns:
        StackDetectionResult
    """
    detector = StackDetector(Path(project_dir))
    return detector.detect()
