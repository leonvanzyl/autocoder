"""
Features Router
===============

API endpoints for feature/test case management.
"""

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException

from ..dependencies import validate_project_not_detached
from ..schemas import (
    DependencyGraphEdge,
    DependencyGraphNode,
    DependencyGraphResponse,
    DependencyUpdate,
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
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def feature_to_response(f, passing_ids: set[int] | None = None) -> FeatureResponse:
    """Convert a Feature model to a FeatureResponse.

    Handles legacy NULL values in boolean fields by treating them as False.
    Computes blocked status if passing_ids is provided.

    Args:
        f: Feature model instance
        passing_ids: Optional set of feature IDs that are passing (for computing blocked status)

    Returns:
        FeatureResponse with computed blocked status
    """
    deps = f.dependencies or []
    if passing_ids is None:
        blocking = []
        blocked = False
    else:
        blocking = [d for d in deps if d not in passing_ids]
        blocked = len(blocking) > 0

    return FeatureResponse(
        id=f.id,
        priority=f.priority,
        category=f.category,
        name=f.name,
        description=f.description,
        steps=f.steps if isinstance(f.steps, list) else [],
        dependencies=deps,
        # Handle legacy NULL values gracefully - treat as False
        passes=f.passes if f.passes is not None else False,
        in_progress=f.in_progress if f.in_progress is not None else False,
        blocked=blocked,
        blocking_dependencies=blocking,
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

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    from autoforge_paths import get_features_db_path
    db_file = get_features_db_path(project_dir)
    if not db_file.exists():
        return FeatureListResponse(pending=[], in_progress=[], done=[])

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            all_features = session.query(Feature).order_by(Feature.priority).all()

            # Compute passing IDs for blocked status calculation
            passing_ids = {f.id for f in all_features if f.passes}

            pending = []
            in_progress = []
            done = []

            for f in all_features:
                feature_response = feature_to_response(f, passing_ids)
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

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

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
                dependencies=feature.dependencies if feature.dependencies else None,
                passes=False,
                in_progress=False,
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


# ============================================================================
# Static path endpoints - MUST be declared before /{feature_id} routes
# ============================================================================


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

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    if not bulk.features:
        return FeatureBulkCreateResponse(created=0, features=[])

    # Validate starting_priority if provided
    if bulk.starting_priority is not None and bulk.starting_priority < 1:
        raise HTTPException(status_code=400, detail="starting_priority must be >= 1")

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            # Determine starting priority
            # Note: SQLite uses file-level locking, not row-level locking, so we rely on
            # SQLite's transaction isolation. Concurrent bulk creates may get overlapping
            # priorities, but this is acceptable since priorities can be reordered.
            if bulk.starting_priority is not None:
                current_priority = bulk.starting_priority
            else:
                max_priority_feature = (
                    session.query(Feature)
                    .order_by(Feature.priority.desc())
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
                    dependencies=feature_data.dependencies if feature_data.dependencies else None,
                    passes=False,
                    in_progress=False,
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


@router.get("/graph", response_model=DependencyGraphResponse)
async def get_dependency_graph(project_name: str):
    """Return dependency graph data for visualization.

    Returns nodes (features) and edges (dependencies) suitable for
    rendering with React Flow or similar graph libraries.
    """
    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    from autoforge_paths import get_features_db_path
    db_file = get_features_db_path(project_dir)
    if not db_file.exists():
        return DependencyGraphResponse(nodes=[], edges=[])

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            all_features = session.query(Feature).all()
            passing_ids = {f.id for f in all_features if f.passes}

            nodes = []
            edges = []

            for f in all_features:
                deps = f.dependencies or []
                blocking = [d for d in deps if d not in passing_ids]

                status: Literal["pending", "in_progress", "done", "blocked"]
                if f.passes:
                    status = "done"
                elif blocking:
                    status = "blocked"
                elif f.in_progress:
                    status = "in_progress"
                else:
                    status = "pending"

                nodes.append(DependencyGraphNode(
                    id=f.id,
                    name=f.name,
                    category=f.category,
                    status=status,
                    priority=f.priority,
                    dependencies=deps
                ))

                for dep_id in deps:
                    edges.append(DependencyGraphEdge(source=dep_id, target=f.id))

            return DependencyGraphResponse(nodes=nodes, edges=edges)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get dependency graph")
        raise HTTPException(status_code=500, detail="Failed to get dependency graph")


# ============================================================================
# Parameterized path endpoints - /{feature_id} routes
# ============================================================================


@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(project_name: str, feature_id: int):
    """Get details of a specific feature."""
    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    from autoforge_paths import get_features_db_path
    db_file = get_features_db_path(project_dir)
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


@router.patch("/{feature_id}", response_model=FeatureResponse)
async def update_feature(project_name: str, feature_id: int, update: FeatureUpdate):
    """
    Update a feature's details.

    Only features that are not yet completed (passes=False) can be edited.
    This allows users to provide corrections or additional instructions
    when the agent is stuck or implementing a feature incorrectly.
    """
    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Prevent editing completed features
            if feature.passes:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot edit a completed feature. Features marked as done are immutable."
                )

            # Apply updates for non-None fields
            if update.category is not None:
                feature.category = update.category
            if update.name is not None:
                feature.name = update.name
            if update.description is not None:
                feature.description = update.description
            if update.steps is not None:
                feature.steps = update.steps
            if update.priority is not None:
                feature.priority = update.priority
            if update.dependencies is not None:
                feature.dependencies = update.dependencies if update.dependencies else None

            session.commit()
            session.refresh(feature)

            # Compute passing IDs for response
            all_features = session.query(Feature).all()
            passing_ids = {f.id for f in all_features if f.passes}

            return feature_to_response(feature, passing_ids)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update feature")
        raise HTTPException(status_code=500, detail="Failed to update feature")


@router.delete("/{feature_id}")
async def delete_feature(project_name: str, feature_id: int):
    """Delete a feature and clean up references in other features' dependencies.

    When a feature is deleted, any other features that depend on it will have
    that dependency removed from their dependencies list. This prevents orphaned
    dependencies that would permanently block features.
    """
    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Clean up dependency references in other features
            # This prevents orphaned dependencies that would block features forever
            affected_features = []
            for f in session.query(Feature).all():
                if f.dependencies and feature_id in f.dependencies:
                    # Remove the deleted feature from this feature's dependencies
                    deps = [d for d in f.dependencies if d != feature_id]
                    f.dependencies = deps if deps else None
                    affected_features.append(f.id)

            session.delete(feature)
            session.commit()

            message = f"Feature {feature_id} deleted"
            if affected_features:
                message += f". Removed from dependencies of features: {affected_features}"

            return {"success": True, "message": message, "affected_features": affected_features}
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

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Set priority to max + 1 to push to end (consistent with MCP server)
            max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
            feature.priority = (max_priority.priority + 1) if max_priority else 1

            session.commit()

            return {"success": True, "message": f"Feature {feature_id} moved to end of queue"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to skip feature")
        raise HTTPException(status_code=500, detail="Failed to skip feature")


# ============================================================================
# Dependency Management Endpoints
# ============================================================================


def _get_dependency_resolver():
    """Lazy import of dependency resolver."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from api.dependency_resolver import MAX_DEPENDENCIES_PER_FEATURE, would_create_circular_dependency
    return would_create_circular_dependency, MAX_DEPENDENCIES_PER_FEATURE


@router.post("/{feature_id}/dependencies/{dep_id}")
async def add_dependency(project_name: str, feature_id: int, dep_id: int):
    """Add a dependency relationship between features.

    The dep_id feature must be completed before feature_id can be started.
    Validates: self-reference, existence, circular dependencies, max limit.
    """
    project_name = validate_project_name(project_name)

    # Security: Self-reference check
    if feature_id == dep_id:
        raise HTTPException(status_code=400, detail="A feature cannot depend on itself")

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    would_create_circular_dependency, MAX_DEPENDENCIES_PER_FEATURE = _get_dependency_resolver()
    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            dependency = session.query(Feature).filter(Feature.id == dep_id).first()

            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
            if not dependency:
                raise HTTPException(status_code=404, detail=f"Dependency {dep_id} not found")

            current_deps = feature.dependencies or []

            # Security: Limit check
            if len(current_deps) >= MAX_DEPENDENCIES_PER_FEATURE:
                raise HTTPException(status_code=400, detail=f"Maximum {MAX_DEPENDENCIES_PER_FEATURE} dependencies allowed")

            if dep_id in current_deps:
                raise HTTPException(status_code=400, detail="Dependency already exists")

            # Security: Circular dependency check
            # source_id = feature_id (gaining dep), target_id = dep_id (being depended upon)
            all_features = [f.to_dict() for f in session.query(Feature).all()]
            if would_create_circular_dependency(all_features, feature_id, dep_id):
                raise HTTPException(status_code=400, detail="Would create circular dependency")

            current_deps.append(dep_id)
            feature.dependencies = sorted(current_deps)
            session.commit()

            return {"success": True, "feature_id": feature_id, "dependencies": feature.dependencies}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to add dependency")
        raise HTTPException(status_code=500, detail="Failed to add dependency")


@router.delete("/{feature_id}/dependencies/{dep_id}")
async def remove_dependency(project_name: str, feature_id: int, dep_id: int):
    """Remove a dependency from a feature."""
    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            current_deps = feature.dependencies or []
            if dep_id not in current_deps:
                raise HTTPException(status_code=400, detail="Dependency does not exist")

            current_deps.remove(dep_id)
            feature.dependencies = current_deps if current_deps else None
            session.commit()

            return {"success": True, "feature_id": feature_id, "dependencies": feature.dependencies or []}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to remove dependency")
        raise HTTPException(status_code=500, detail="Failed to remove dependency")


@router.put("/{feature_id}/dependencies")
async def set_dependencies(project_name: str, feature_id: int, update: DependencyUpdate):
    """Set all dependencies for a feature at once, replacing any existing.

    Validates: self-reference, existence of all dependencies, circular dependencies, max limit.
    """
    project_name = validate_project_name(project_name)

    # Check detach status before accessing database
    project_dir = validate_project_not_detached(project_name)

    dependency_ids = update.dependency_ids

    # Security: Self-reference check
    if feature_id in dependency_ids:
        raise HTTPException(status_code=400, detail="A feature cannot depend on itself")

    # Check for duplicates
    if len(dependency_ids) != len(set(dependency_ids)):
        raise HTTPException(status_code=400, detail="Duplicate dependencies not allowed")

    would_create_circular_dependency, _ = _get_dependency_resolver()
    _, Feature = _get_db_classes()

    try:
        with get_db_session(project_dir) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Validate all dependencies exist
            all_feature_ids = {f.id for f in session.query(Feature).all()}
            missing = [d for d in dependency_ids if d not in all_feature_ids]
            if missing:
                raise HTTPException(status_code=400, detail=f"Dependencies not found: {missing}")

            # Check for circular dependencies
            all_features = [f.to_dict() for f in session.query(Feature).all()]
            # Temporarily update the feature's dependencies for cycle check
            test_features = []
            for f in all_features:
                if f["id"] == feature_id:
                    test_features.append({**f, "dependencies": dependency_ids})
                else:
                    test_features.append(f)

            for dep_id in dependency_ids:
                # source_id = feature_id (gaining dep), target_id = dep_id (being depended upon)
                if would_create_circular_dependency(test_features, feature_id, dep_id):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot add dependency {dep_id}: would create circular dependency"
                    )

            # Set dependencies
            feature.dependencies = sorted(dependency_ids) if dependency_ids else None
            session.commit()

            return {"success": True, "feature_id": feature_id, "dependencies": feature.dependencies or []}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to set dependencies")
        raise HTTPException(status_code=500, detail="Failed to set dependencies")
