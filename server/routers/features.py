"""
Features Router
===============

API endpoints for feature/test case management.
"""

import logging
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    FeatureBulkCreate,
    FeatureBulkCreateResponse,
    FeatureCreate,
    FeatureListResponse,
    FeatureResponse,
    FeatureUpdate,
)
from ..utils.validation import validate_project_name

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


@router.patch("/{feature_id}", response_model=FeatureResponse)
async def update_feature(project_name: str, feature_id: int, update: FeatureUpdate):
    """
    Update a feature's editable fields (category, name, description, steps).

    Only provided fields are updated; others remain unchanged.
    Cannot update: id, priority (use skip), passes, in_progress (agent-controlled).
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

            # Get only the fields that were provided (exclude unset)
            update_data = update.model_dump(exclude_unset=True)

            if not update_data:
                raise HTTPException(status_code=400, detail="No fields to update")

            # Apply updates
            for field, value in update_data.items():
                setattr(feature, field, value)

            session.commit()
            session.refresh(feature)

            return feature_to_response(feature)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update feature")
        raise HTTPException(status_code=500, detail="Failed to update feature")


@router.post("/bulk", response_model=FeatureBulkCreateResponse)
async def create_features_bulk(project_name: str, bulk: FeatureBulkCreate):
    """
    Create multiple features at once.

    Features are assigned sequential priorities starting from:
    - starting_priority if specified (must be >= 1)
    - max(existing priorities) + 1 if not specified

    This is useful for:
    - Expanding a project with new features via AI
    - Importing features from external sources
    - Batch operations

    Returns:
        {"created": N, "features": [...]}
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    if not bulk.features:
        return FeatureBulkCreateResponse(created=0, features=[])

    # Validate starting_priority if provided
    if bulk.starting_priority is not None and bulk.starting_priority < 1:
        raise HTTPException(status_code=400, detail="starting_priority must be >= 1")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            # Determine starting priority with row-level lock to prevent race conditions
            if bulk.starting_priority is not None:
                current_priority = bulk.starting_priority
            else:
                # Lock the max priority row to prevent concurrent inserts from getting same priority
                max_priority_feature = (
                    session.query(Feature)
                    .order_by(Feature.priority.desc())
                    .with_for_update()
                    .first()
                )
                current_priority = (max_priority_feature.priority + 1) if max_priority_feature else 1

            created_ids = []

            for feature_data in bulk.features:
                db_feature = Feature(
                    priority=current_priority,
                    category=feature_data.category,
                    name=feature_data.name,
                    description=feature_data.description,
                    steps=feature_data.steps,
                    passes=False,
                )
                session.add(db_feature)
                session.flush()  # Flush to get the ID immediately
                created_ids.append(db_feature.id)
                current_priority += 1

            session.commit()

            # Query created features by their IDs (avoids relying on priority range)
            created_features = []
            for db_feature in session.query(Feature).filter(
                Feature.id.in_(created_ids)
            ).order_by(Feature.priority).all():
                created_features.append(feature_to_response(db_feature))

            return FeatureBulkCreateResponse(
                created=len(created_features),
                features=created_features
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to bulk create features")
        raise HTTPException(status_code=500, detail="Failed to bulk create features")
