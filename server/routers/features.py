"""
Features Router
===============

API endpoints for feature/test case management.
"""

import logging
import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    FeatureCreate,
    FeatureListResponse,
    FeatureResponse,
)

# Lazy imports to avoid circular dependencies
_create_database = None
_Feature = None

logger = logging.getLogger(__name__)


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def _get_db_classes():
    """Lazy import of database classes."""
    global _create_database, _Feature
    if _create_database is None:
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from api.database import Feature, create_database
        _create_database = create_database
        _Feature = Feature
    return _create_database, _Feature


router = APIRouter(prefix="/api/projects/{project_name}/features", tags=["features"])


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


@contextmanager
def get_db_session(project_dir: Path):
    """
    Context manager for database sessions.
    Ensures session is always closed, even on exceptions.
    """
    create_database, _ = _get_db_classes()
    _, SessionLocal = create_database(project_dir)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def feature_to_response(f) -> FeatureResponse:
    """Convert a Feature model to a FeatureResponse."""
    return FeatureResponse(
        id=f.id,
        priority=f.priority,
        category=f.category,
        name=f.name,
        description=f.description,
        steps=f.steps if isinstance(f.steps, list) else [],
        passes=f.passes,
        in_progress=f.in_progress,
    )


@router.get("", response_model=FeatureListResponse)
async def list_features(project_name: str):
    """
    List all features for a project organized by status.

    Returns features in three lists:
    - pending: passes=False, not currently being worked on
    - in_progress: features currently being worked on (tracked via agent output)
    - done: passes=True
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db_file = project_dir / "features.db"
    if not db_file.exists():
        return FeatureListResponse(pending=[], in_progress=[], done=[])

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            all_features = session.query(Feature).order_by(Feature.priority).all()

            pending = []
            in_progress = []
            done = []

            for f in all_features:
                feature_response = feature_to_response(f)
                if f.passes:
                    done.append(feature_response)
                elif f.in_progress:
                    in_progress.append(feature_response)
                else:
                    pending.append(feature_response)

            return FeatureListResponse(
                pending=pending,
                in_progress=in_progress,
                done=done,
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error in list_features")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("", response_model=FeatureResponse)
async def create_feature(project_name: str, feature: FeatureCreate):
    """Create a new feature/test case manually."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            # Get next priority if not specified
            if feature.priority is None:
                max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
                priority = (max_priority.priority + 1) if max_priority else 1
            else:
                priority = feature.priority

            # Create new feature
            db_feature = Feature(
                priority=priority,
                category=feature.category,
                name=feature.name,
                description=feature.description,
                steps=feature.steps,
                passes=False,
            )

            session.add(db_feature)
            session.commit()
            session.refresh(db_feature)

            return feature_to_response(db_feature)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create feature")
        raise HTTPException(status_code=500, detail="Failed to create feature")


@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(project_name: str, feature_id: int):
    """Get details of a specific feature."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db_file = project_dir / "features.db"
    if not db_file.exists():
        raise HTTPException(status_code=404, detail="No features database found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            return feature_to_response(feature)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Database error in get_feature")
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.delete("/{feature_id}")
async def delete_feature(project_name: str, feature_id: int):
    """Delete a feature."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            session.delete(feature)
            session.commit()

            return {"success": True, "message": f"Feature {feature_id} deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete feature")
        raise HTTPException(status_code=500, detail="Failed to delete feature")


@router.post("/repair")
async def repair_database(project_name: str):
    """
    Repair the feature database by removing duplicates and compacting IDs.

    Performs the following repairs:
    1. Removes duplicate features (keeping the one with lowest ID)
    2. Compacts IDs to be sequential (1, 2, 3, ...) with no gaps
    3. Resets priorities to match the new sequential IDs
    """
    from sqlalchemy import text

    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    db_file = project_dir / "features.db"
    if not db_file.exists():
        return {"duplicates_removed": 0, "ids_compacted": False, "total_features": 0}

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            # Step 1: Find and remove duplicates (keep lowest ID for each name)
            duplicates_query = """
                SELECT id FROM features
                WHERE id NOT IN (
                    SELECT MIN(id) FROM features GROUP BY name
                )
            """
            result = session.execute(text(duplicates_query))
            duplicate_ids = [row[0] for row in result.fetchall()]
            duplicates_removed = len(duplicate_ids)

            if duplicate_ids:
                session.execute(
                    text(f"DELETE FROM features WHERE id IN ({','.join(map(str, duplicate_ids))})")
                )
                session.commit()

            # Step 2: Get current state
            all_features = session.query(Feature).order_by(Feature.priority.asc(), Feature.id.asc()).all()
            old_max_id = max(f.id for f in all_features) if all_features else 0
            total_features = len(all_features)

            # Step 3: Check if compaction is needed
            expected_ids = set(range(1, total_features + 1))
            actual_ids = set(f.id for f in all_features)
            needs_compaction = expected_ids != actual_ids

            new_max_id = old_max_id
            if needs_compaction and all_features:
                # First, shift all IDs to negative to avoid conflicts
                session.execute(text("UPDATE features SET id = -id"))
                session.commit()

                # Then assign new sequential IDs
                for new_id, feature in enumerate(all_features, start=1):
                    session.execute(
                        text(f"UPDATE features SET id = {new_id}, priority = {new_id} WHERE id = {-feature.id}")
                    )
                session.commit()

                new_max_id = total_features

            return {
                "success": True,
                "duplicates_removed": duplicates_removed,
                "ids_compacted": needs_compaction,
                "old_max_id": old_max_id,
                "new_max_id": new_max_id,
                "total_features": total_features
            }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to repair database")
        raise HTTPException(status_code=500, detail="Failed to repair database")


@router.patch("/{feature_id}/skip")
async def skip_feature(project_name: str, feature_id: int):
    """
    Mark a feature as skipped by moving it to the end of the priority queue.

    This doesn't delete the feature but gives it a very high priority number
    so it will be processed last.
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Set priority to max + 1000 to push to end
            max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
            feature.priority = (max_priority.priority if max_priority else 0) + 1000

            session.commit()

            return {"success": True, "message": f"Feature {feature_id} moved to end of queue"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to skip feature")
        raise HTTPException(status_code=500, detail="Failed to skip feature")
