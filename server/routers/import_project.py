"""
Import Project Router
=====================

REST and WebSocket endpoints for importing existing projects into Autocoder.

The import flow:
1. POST /api/import/analyze - Analyze codebase, detect stack
2. POST /api/import/extract-features - Generate features from analysis
3. POST /api/import/create-features - Create features in database
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["import-project"])

# Root directory
ROOT_DIR = Path(__file__).parent.parent.parent

# Add root to path for imports
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    from registry import get_project_path
    return get_project_path(project_name)


def validate_path(path: str) -> bool:
    """Validate path to prevent traversal attacks and access to sensitive locations."""
    from pathlib import Path

    # Check for null bytes and basic traversal patterns
    if "\x00" in path:
        return False

    try:
        resolved_path = Path(path).resolve()
    except (OSError, ValueError):
        return False

    # Blocklist of sensitive system locations
    blocked_paths = [
        Path("/etc").resolve(),
        Path("/root").resolve(),
        Path("/var").resolve(),
        Path("/sys").resolve(),
        Path("/proc").resolve(),
    ]

    # Windows paths to block (if on Windows)
    if os.name == 'nt':
        blocked_paths.extend([
            Path(r"C:\Windows").resolve(),
            Path(r"C:\Windows\System32").resolve(),
            Path(r"C:\Program Files").resolve(),
        ])

    # Check if path is a subpath of any blocked location
    for blocked in blocked_paths:
        try:
            resolved_path.relative_to(blocked)
            return False  # Path is under a blocked location
        except ValueError:
            pass  # Not under this blocked location, continue checking

    # For now, allow absolute paths but they will be validated further by callers
    # You could add an allowlist here: e.g., only allow paths under /home/user or /data

    return True


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeRequest(BaseModel):
    """Request to analyze a project directory."""
    path: str = Field(..., description="Absolute path to the project directory")


class StackInfo(BaseModel):
    """Information about a detected stack."""
    name: str
    category: str
    confidence: float


class AnalyzeResponse(BaseModel):
    """Response from project analysis."""
    project_dir: str
    detected_stacks: list[StackInfo]
    primary_frontend: Optional[str] = None
    primary_backend: Optional[str] = None
    database: Optional[str] = None
    routes_count: int
    components_count: int
    endpoints_count: int
    summary: str


class ExtractFeaturesRequest(BaseModel):
    """Request to extract features from an analyzed project."""
    path: str = Field(..., description="Absolute path to the project directory")


class DetectedFeature(BaseModel):
    """A feature extracted from codebase analysis."""
    category: str
    name: str
    description: str
    steps: list[str]
    source_type: str
    source_file: Optional[str] = None
    confidence: float


class ExtractFeaturesResponse(BaseModel):
    """Response from feature extraction."""
    features: list[DetectedFeature]
    count: int
    by_category: dict[str, int]
    summary: str


class CreateFeaturesRequest(BaseModel):
    """Request to create features in the database."""
    project_name: str = Field(..., description="Name of the registered project")
    features: list[dict] = Field(..., description="Features to create (category, name, description, steps)")


class CreateFeaturesResponse(BaseModel):
    """Response from feature creation."""
    created: int
    project_name: str
    message: str


# ============================================================================
# REST Endpoints
# ============================================================================

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_project(request: AnalyzeRequest):
    """
    Analyze a project directory to detect tech stack.

    Returns detected stacks with confidence scores, plus counts of
    routes, endpoints, and components found.
    """
    if not validate_path(request.path):
        raise HTTPException(status_code=400, detail="Invalid path")

    project_dir = Path(request.path).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    if not project_dir.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    try:
        from analyzers import StackDetector

        detector = StackDetector(project_dir)
        result = detector.detect()

        # Convert to response model
        stacks = [
            StackInfo(
                name=s["name"],
                category=s["category"],
                confidence=s["confidence"],
            )
            for s in result["detected_stacks"]
        ]

        return AnalyzeResponse(
            project_dir=str(project_dir),
            detected_stacks=stacks,
            primary_frontend=result.get("primary_frontend"),
            primary_backend=result.get("primary_backend"),
            database=result.get("database"),
            routes_count=result.get("routes_count", 0),
            components_count=result.get("components_count", 0),
            endpoints_count=result.get("endpoints_count", 0),
            summary=result.get("summary", ""),
        )

    except Exception as e:
        logger.exception(f"Error analyzing project: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/extract-features", response_model=ExtractFeaturesResponse)
async def extract_features(request: ExtractFeaturesRequest):
    """
    Extract features from an analyzed project.

    Returns a list of features ready for import, each with:
    - category, name, description, steps
    - source_type (route, endpoint, component, inferred)
    - confidence score
    """
    if not validate_path(request.path):
        raise HTTPException(status_code=400, detail="Invalid path")

    project_dir = Path(request.path).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    try:
        from analyzers import extract_from_project

        result = extract_from_project(project_dir)

        # Convert to response model
        features = [
            DetectedFeature(
                category=f["category"],
                name=f["name"],
                description=f["description"],
                steps=f["steps"],
                source_type=f["source_type"],
                source_file=f.get("source_file"),
                confidence=f["confidence"],
            )
            for f in result["features"]
        ]

        return ExtractFeaturesResponse(
            features=features,
            count=result["count"],
            by_category=result["by_category"],
            summary=result["summary"],
        )

    except Exception as e:
        logger.exception(f"Error extracting features: {e}")
        raise HTTPException(status_code=500, detail=f"Feature extraction failed: {str(e)}")


@router.post("/create-features", response_model=CreateFeaturesResponse)
async def create_features(request: CreateFeaturesRequest):
    """
    Create features in the database for a registered project.

    Takes extracted features and creates them via the feature database.
    All features are created with passes=False (pending verification).
    """
    # Validate project name
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', request.project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    if not request.features:
        raise HTTPException(status_code=400, detail="No features provided")

    try:
        from api.database import Feature, create_database

        # Initialize database
        engine, SessionLocal = create_database(project_dir)
        session = SessionLocal()

        try:
            # Get starting priority
            from sqlalchemy import func
            max_priority = session.query(func.max(Feature.priority)).scalar() or 0

            # Create features
            created_count = 0
            for i, f in enumerate(request.features):
                # Validate required fields
                if not all(key in f for key in ["category", "name", "description", "steps"]):
                    logger.warning(f"Skipping feature missing required fields: {f}")
                    continue

                feature = Feature(
                    priority=max_priority + i + 1,
                    category=f["category"],
                    name=f["name"],
                    description=f["description"],
                    steps=f["steps"],
                    passes=False,
                    in_progress=False,
                )
                session.add(feature)
                created_count += 1

            session.commit()

            return CreateFeaturesResponse(
                created=created_count,
                project_name=request.project_name,
                message=f"Created {created_count} features for project '{request.project_name}'",
            )

        finally:
            session.close()

    except Exception as e:
        logger.exception(f"Error creating features: {e}")
        raise HTTPException(status_code=500, detail=f"Feature creation failed: {str(e)}")


@router.get("/quick-detect")
async def quick_detect(path: str):
    """
    Quick detection endpoint for UI preview.

    Returns only stack names and confidence without full analysis.
    Useful for showing detected stack while user configures import.
    """
    if not validate_path(path):
        raise HTTPException(status_code=400, detail="Invalid path")

    project_dir = Path(path).resolve()

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Directory not found")

    try:
        from analyzers import StackDetector

        detector = StackDetector(project_dir)
        result = detector.detect_quick()

        return {
            "project_dir": str(project_dir),
            "stacks": result.get("stacks", []),
            "primary": result.get("primary"),
        }

    except Exception as e:
        logger.exception(f"Error in quick detect: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")
