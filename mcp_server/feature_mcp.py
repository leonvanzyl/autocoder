#!/usr/bin/env python3
"""
MCP Server for Feature Management
==================================

Provides tools to manage features in the autonomous coding system.

Tools:
- feature_get_stats: Get progress statistics
- feature_get_by_id: Get a specific feature by ID
- feature_get_summary: Get minimal feature info (id, name, status, deps)
- feature_mark_passing: Mark a feature as passing
- feature_mark_failing: Mark a feature as failing (regression detected)
- feature_skip: Skip a feature (move to end of queue)
- feature_mark_in_progress: Mark a feature as in-progress
- feature_claim_and_get: Atomically claim and get feature details
- feature_clear_in_progress: Clear in-progress status
- feature_create_bulk: Create multiple features at once
- feature_create: Create a single feature
- feature_add_dependency: Add a dependency between features
- feature_remove_dependency: Remove a dependency
- feature_get_ready: Get features ready to implement
- feature_get_blocked: Get features blocked by dependencies (with limit)
- feature_get_graph: Get the dependency graph

Note: Feature selection (which feature to work on) is handled by the
orchestrator, not by agents. Agents receive pre-assigned feature IDs.
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy import text

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, atomic_transaction, create_database
from api.dependency_resolver import (
    MAX_DEPENDENCIES_PER_FEATURE,
    compute_scheduling_scores,
    would_create_circular_dependency,
)
from api.migration import migrate_json_to_sqlite

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()


# Pydantic models for input validation
class MarkPassingInput(BaseModel):
    """Input for marking a feature as passing."""
    feature_id: int = Field(..., description="The ID of the feature to mark as passing", ge=1)


class SkipFeatureInput(BaseModel):
    """Input for skipping a feature."""
    feature_id: int = Field(..., description="The ID of the feature to skip", ge=1)


class MarkInProgressInput(BaseModel):
    """Input for marking a feature as in-progress."""
    feature_id: int = Field(..., description="The ID of the feature to mark as in-progress", ge=1)


class ClearInProgressInput(BaseModel):
    """Input for clearing in-progress status."""
    feature_id: int = Field(..., description="The ID of the feature to clear in-progress status", ge=1)


class RegressionInput(BaseModel):
    """Input for getting regression features."""
    limit: int = Field(default=3, ge=1, le=10, description="Maximum number of passing features to return")


class FeatureCreateItem(BaseModel):
    """Schema for creating a single feature."""
    category: str = Field(..., min_length=1, max_length=100, description="Feature category")
    name: str = Field(..., min_length=1, max_length=255, description="Feature name")
    description: str = Field(..., min_length=1, description="Detailed description")
    steps: list[str] = Field(..., min_length=1, description="Implementation/test steps")


class BulkCreateInput(BaseModel):
    """Input for bulk creating features."""
    features: list[FeatureCreateItem] = Field(..., min_length=1, description="List of features to create")


# Global database session maker (initialized on startup)
_session_maker = None
_engine = None

# NOTE: The old threading.Lock() was removed because it only worked per-process,
# not cross-process. In parallel mode, multiple MCP servers run in separate
# processes, so the lock was useless. We now use atomic SQL operations instead.


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup, cleanup on shutdown."""
    global _session_maker, _engine

    # Create project directory if it doesn't exist
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    _engine, _session_maker = create_database(PROJECT_DIR)

    # Run migration if needed (converts legacy JSON to SQLite)
    migrate_json_to_sqlite(PROJECT_DIR, _session_maker)

    yield

    # Cleanup
    if _engine:
        _engine.dispose()


# Initialize the MCP server
mcp = FastMCP("features", lifespan=server_lifespan)


def get_session():
    """Get a new database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized")
    return _session_maker()


@mcp.tool()
def feature_get_stats() -> str:
    """Get statistics about feature completion progress.

    Returns the number of passing features, in-progress features, total features,
    and completion percentage. Use this to track overall progress of the implementation.

    Returns:
        JSON with: passing (int), in_progress (int), total (int), percentage (float)
    """
    from sqlalchemy import case, func

    session = get_session()
    try:
        # Single aggregate query instead of 3 separate COUNT queries
        result = session.query(
            func.count(Feature.id).label('total'),
            func.sum(case((Feature.passes == True, 1), else_=0)).label('passing'),
            func.sum(case((Feature.in_progress == True, 1), else_=0)).label('in_progress'),
            func.sum(case((Feature.needs_human_input == True, 1), else_=0)).label('needs_human_input')
        ).first()

        total = result.total or 0
        passing = int(result.passing or 0)
        in_progress = int(result.in_progress or 0)
        needs_human_input = int(result.needs_human_input or 0)
        percentage = round((passing / total) * 100, 1) if total > 0 else 0.0

        return json.dumps({
            "passing": passing,
            "in_progress": in_progress,
            "needs_human_input": needs_human_input,
            "total": total,
            "percentage": percentage
        })
    finally:
        session.close()


@mcp.tool()
def feature_get_by_id(
    feature_id: Annotated[int, Field(description="The ID of the feature to retrieve", ge=1)]
) -> str:
    """Get a specific feature by its ID.

    Returns the full details of a feature including its name, description,
    verification steps, and current status.

    Args:
        feature_id: The ID of the feature to retrieve

    Returns:
        JSON with feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        return json.dumps(feature.to_dict())
    finally:
        session.close()


@mcp.tool()
def feature_get_summary(
    feature_id: Annotated[int, Field(description="The ID of the feature", ge=1)]
) -> str:
    """Get minimal feature info: id, name, status, and dependencies only.

    Use this instead of feature_get_by_id when you only need status info,
    not the full description and steps. This reduces response size significantly.

    Args:
        feature_id: The ID of the feature to retrieve

    Returns:
        JSON with: id, name, passes, in_progress, dependencies
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})
        return json.dumps({
            "id": feature.id,
            "name": feature.name,
            "passes": feature.passes,
            "in_progress": feature.in_progress,
            "needs_human_input": feature.needs_human_input if feature.needs_human_input is not None else False,
            "dependencies": feature.dependencies or []
        })
    finally:
        session.close()


@mcp.tool()
def feature_mark_passing(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as passing", ge=1)]
) -> str:
    """Mark a feature as passing after successful implementation.

    Updates the feature's passes field to true and clears the in_progress flag.
    Use this after you have implemented the feature and verified it works correctly.

    Args:
        feature_id: The ID of the feature to mark as passing

    Returns:
        JSON with success confirmation: {success, feature_id, name}
    """
    session = get_session()
    try:
        # Atomic update with state guard - prevents double-pass in parallel mode
        result = session.execute(text("""
            UPDATE features
            SET passes = 1, in_progress = 0
            WHERE id = :id AND passes = 0
        """), {"id": feature_id})
        session.commit()

        if result.rowcount == 0:
            # Check why the update didn't match
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if feature is None:
                return json.dumps({"error": f"Feature with ID {feature_id} not found"})
            if feature.passes:
                return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})
            return json.dumps({"error": "Failed to mark feature passing for unknown reason"})

        # Get the feature name for the response
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        return json.dumps({"success": True, "feature_id": feature_id, "name": feature.name})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to mark feature passing: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_mark_failing(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as failing", ge=1)]
) -> str:
    """Mark a feature as failing after finding a regression.

    Updates the feature's passes field to false and clears the in_progress flag.
    Use this when a testing agent discovers that a previously-passing feature
    no longer works correctly (regression detected).

    After marking as failing, you should:
    1. Investigate the root cause
    2. Fix the regression
    3. Verify the fix
    4. Call feature_mark_passing once fixed

    Args:
        feature_id: The ID of the feature to mark as failing

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        # Check if feature exists first
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Atomic update for parallel safety
        session.execute(text("""
            UPDATE features
            SET passes = 0, in_progress = 0
            WHERE id = :id
        """), {"id": feature_id})
        session.commit()

        # Refresh to get updated state
        session.refresh(feature)

        return json.dumps({
            "message": f"Feature #{feature_id} marked as failing - regression detected",
            "feature": feature.to_dict()
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to mark feature failing: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_skip(
    feature_id: Annotated[int, Field(description="The ID of the feature to skip", ge=1)]
) -> str:
    """Skip a feature by moving it to the end of the priority queue.

    Use this when a feature cannot be implemented yet due to:
    - Dependencies on other features that aren't implemented yet
    - External blockers (missing assets, unclear requirements)
    - Technical prerequisites that need to be addressed first

    The feature's priority is set to max_priority + 1, so it will be
    worked on after all other pending features. Also clears the in_progress
    flag so the feature returns to "pending" status.

    Args:
        feature_id: The ID of the feature to skip

    Returns:
        JSON with skip details: id, name, old_priority, new_priority, message
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": "Cannot skip a feature that is already passing"})

        old_priority = feature.priority
        name = feature.name

        # Atomic update: set priority to max+1 in a single statement
        # This prevents race conditions where two features get the same priority
        session.execute(text("""
            UPDATE features
            SET priority = (SELECT COALESCE(MAX(priority), 0) + 1 FROM features),
                in_progress = 0
            WHERE id = :id
        """), {"id": feature_id})
        session.commit()

        # Refresh to get new priority
        session.refresh(feature)
        new_priority = feature.priority

        return json.dumps({
            "id": feature_id,
            "name": name,
            "old_priority": old_priority,
            "new_priority": new_priority,
            "message": f"Feature '{name}' moved to end of queue"
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to skip feature: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_mark_in_progress(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as in-progress", ge=1)]
) -> str:
    """Mark a feature as in-progress.

    This prevents other agent sessions from working on the same feature.
    Call this after getting your assigned feature details with feature_get_by_id.

    Args:
        feature_id: The ID of the feature to mark as in-progress

    Returns:
        JSON with the updated feature details, or error if not found or already in-progress.
    """
    session = get_session()
    try:
        # Atomic claim: only succeeds if feature is not already claimed, passing, or blocked for human input
        result = session.execute(text("""
            UPDATE features
            SET in_progress = 1
            WHERE id = :id AND passes = 0 AND in_progress = 0 AND needs_human_input = 0
        """), {"id": feature_id})
        session.commit()

        if result.rowcount == 0:
            # Check why the claim failed
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if feature is None:
                return json.dumps({"error": f"Feature with ID {feature_id} not found"})
            if feature.passes:
                return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})
            if feature.in_progress:
                return json.dumps({"error": f"Feature with ID {feature_id} is already in-progress"})
            if getattr(feature, 'needs_human_input', False):
                return json.dumps({"error": f"Feature with ID {feature_id} is blocked waiting for human input"})
            return json.dumps({"error": "Failed to mark feature in-progress for unknown reason"})

        # Fetch the claimed feature
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        return json.dumps(feature.to_dict())
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to mark feature in-progress: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_claim_and_get(
    feature_id: Annotated[int, Field(description="The ID of the feature to claim", ge=1)]
) -> str:
    """Atomically claim a feature (mark in-progress) and return its full details.

    Combines feature_mark_in_progress + feature_get_by_id into a single operation.
    If already in-progress, still returns the feature details (idempotent).

    Args:
        feature_id: The ID of the feature to claim and retrieve

    Returns:
        JSON with feature details including claimed status, or error if not found.
    """
    session = get_session()
    try:
        # First check if feature exists
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})

        if getattr(feature, 'needs_human_input', False):
            return json.dumps({"error": f"Feature with ID {feature_id} is blocked waiting for human input"})

        # Try atomic claim: only succeeds if not already claimed and not blocked for human input
        result = session.execute(text("""
            UPDATE features
            SET in_progress = 1
            WHERE id = :id AND passes = 0 AND in_progress = 0 AND needs_human_input = 0
        """), {"id": feature_id})
        session.commit()

        # Determine if we claimed it or it was already claimed
        already_claimed = result.rowcount == 0
        if already_claimed:
            # Verify it's in_progress (not some other failure condition)
            session.refresh(feature)
            if not feature.in_progress:
                return json.dumps({"error": f"Failed to claim feature {feature_id} for unknown reason"})

        # Refresh to get current state
        session.refresh(feature)
        result_dict = feature.to_dict()
        result_dict["already_claimed"] = already_claimed
        return json.dumps(result_dict)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to claim feature: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_clear_in_progress(
    feature_id: Annotated[int, Field(description="The ID of the feature to clear in-progress status", ge=1)]
) -> str:
    """Clear in-progress status from a feature.

    Use this when abandoning a feature or manually unsticking a stuck feature.
    The feature will return to the pending queue.

    Args:
        feature_id: The ID of the feature to clear in-progress status

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        # Check if feature exists
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Atomic update - idempotent, safe in parallel mode
        session.execute(text("""
            UPDATE features
            SET in_progress = 0
            WHERE id = :id
        """), {"id": feature_id})
        session.commit()

        session.refresh(feature)
        return json.dumps(feature.to_dict())
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to clear in-progress status: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_create_bulk(
    features: Annotated[list[dict], Field(description="List of features to create, each with category, name, description, and steps")]
) -> str:
    """Create multiple features in a single operation.

    Features are assigned sequential priorities based on their order.
    All features start with passes=false.

    This is typically used by the initializer agent to set up the initial
    feature list from the app specification.

    Args:
        features: List of features to create, each with:
            - category (str): Feature category
            - name (str): Feature name
            - description (str): Detailed description
            - steps (list[str]): Implementation/test steps
            - depends_on_indices (list[int], optional): Array indices (0-based) of
              features in THIS batch that this feature depends on. Use this instead
              of 'dependencies' since IDs aren't known until after creation.
              Example: [0, 2] means this feature depends on features at index 0 and 2.

    Returns:
        JSON with: created (int) - number of features created, with_dependencies (int)
    """
    try:
        # Use atomic transaction for bulk inserts to prevent priority conflicts
        with atomic_transaction(_session_maker) as session:
            # Get the starting priority atomically within the transaction
            result = session.execute(text("""
                SELECT COALESCE(MAX(priority), 0) FROM features
            """)).fetchone()
            start_priority = (result[0] or 0) + 1

            # First pass: validate all features and their index-based dependencies
            for i, feature_data in enumerate(features):
                # Validate required fields
                if not all(key in feature_data for key in ["category", "name", "description", "steps"]):
                    return json.dumps({
                        "error": f"Feature at index {i} missing required fields (category, name, description, steps)"
                    })

                # Validate depends_on_indices
                indices = feature_data.get("depends_on_indices", [])
                if indices:
                    # Check max dependencies
                    if len(indices) > MAX_DEPENDENCIES_PER_FEATURE:
                        return json.dumps({
                            "error": f"Feature at index {i} has {len(indices)} dependencies, max is {MAX_DEPENDENCIES_PER_FEATURE}"
                        })
                    # Check for duplicates
                    if len(indices) != len(set(indices)):
                        return json.dumps({
                            "error": f"Feature at index {i} has duplicate dependencies"
                        })
                    # Check for forward references (can only depend on earlier features)
                    for idx in indices:
                        if not isinstance(idx, int) or idx < 0:
                            return json.dumps({
                                "error": f"Feature at index {i} has invalid dependency index: {idx}"
                            })
                        if idx >= i:
                            return json.dumps({
                                "error": f"Feature at index {i} cannot depend on feature at index {idx} (forward reference not allowed)"
                            })

            # Second pass: create all features with reserved priorities
            created_features: list[Feature] = []
            for i, feature_data in enumerate(features):
                db_feature = Feature(
                    priority=start_priority + i,
                    category=feature_data["category"],
                    name=feature_data["name"],
                    description=feature_data["description"],
                    steps=feature_data["steps"],
                    passes=False,
                    in_progress=False,
                )
                session.add(db_feature)
                created_features.append(db_feature)

            # Flush to get IDs assigned
            session.flush()

            # Third pass: resolve index-based dependencies to actual IDs
            deps_count = 0
            for i, feature_data in enumerate(features):
                indices = feature_data.get("depends_on_indices", [])
                if indices:
                    # Convert indices to actual feature IDs
                    dep_ids = [created_features[idx].id for idx in indices]
                    created_features[i].dependencies = sorted(dep_ids)  # type: ignore[assignment]  # SQLAlchemy JSON Column accepts list at runtime
                    deps_count += 1

            # Commit happens automatically on context manager exit
            return json.dumps({
                "created": len(created_features),
                "with_dependencies": deps_count
            })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def feature_create(
    category: Annotated[str, Field(min_length=1, max_length=100, description="Feature category (e.g., 'Authentication', 'API', 'UI')")],
    name: Annotated[str, Field(min_length=1, max_length=255, description="Feature name")],
    description: Annotated[str, Field(min_length=1, description="Detailed description of the feature")],
    steps: Annotated[list[str], Field(min_length=1, description="List of implementation/verification steps")]
) -> str:
    """Create a single feature in the project backlog.

    Use this when the user asks to add a new feature, capability, or test case.
    The feature will be added with the next available priority number.

    Args:
        category: Feature category for grouping (e.g., 'Authentication', 'API', 'UI')
        name: Descriptive name for the feature
        description: Detailed description of what this feature should do
        steps: List of steps to implement or verify the feature

    Returns:
        JSON with the created feature details including its ID
    """
    try:
        # Use atomic transaction to prevent priority collisions
        with atomic_transaction(_session_maker) as session:
            # Get the next priority atomically within the transaction
            result = session.execute(text("""
                SELECT COALESCE(MAX(priority), 0) + 1 FROM features
            """)).fetchone()
            next_priority = result[0]

            db_feature = Feature(
                priority=next_priority,
                category=category,
                name=name,
                description=description,
                steps=steps,
                passes=False,
                in_progress=False,
            )
            session.add(db_feature)
            session.flush()  # Get the ID

            feature_dict = db_feature.to_dict()
            # Commit happens automatically on context manager exit

        return json.dumps({
            "success": True,
            "message": f"Created feature: {name}",
            "feature": feature_dict
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def feature_add_dependency(
    feature_id: Annotated[int, Field(ge=1, description="Feature to add dependency to")],
    dependency_id: Annotated[int, Field(ge=1, description="ID of the dependency feature")]
) -> str:
    """Add a dependency relationship between features.

    The dependency_id feature must be completed before feature_id can be started.
    Validates: self-reference, existence, circular dependencies, max limit.

    Args:
        feature_id: The ID of the feature that will depend on another feature
        dependency_id: The ID of the feature that must be completed first

    Returns:
        JSON with success status and updated dependencies list, or error message
    """
    try:
        # Security: Self-reference check (can do before transaction)
        if feature_id == dependency_id:
            return json.dumps({"error": "A feature cannot depend on itself"})

        # Use atomic transaction for consistent cycle detection
        with atomic_transaction(_session_maker) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            dependency = session.query(Feature).filter(Feature.id == dependency_id).first()

            if not feature:
                return json.dumps({"error": f"Feature {feature_id} not found"})
            if not dependency:
                return json.dumps({"error": f"Dependency feature {dependency_id} not found"})

            current_deps = feature.dependencies or []

            # Security: Max dependencies limit
            if len(current_deps) >= MAX_DEPENDENCIES_PER_FEATURE:
                return json.dumps({"error": f"Maximum {MAX_DEPENDENCIES_PER_FEATURE} dependencies allowed per feature"})

            # Check if already exists
            if dependency_id in current_deps:
                return json.dumps({"error": "Dependency already exists"})

            # Security: Circular dependency check
            # Within IMMEDIATE transaction, snapshot is protected by write lock
            all_features = [f.to_dict() for f in session.query(Feature).all()]
            if would_create_circular_dependency(all_features, feature_id, dependency_id):
                return json.dumps({"error": "Cannot add: would create circular dependency"})

            # Add dependency atomically
            new_deps = sorted(current_deps + [dependency_id])
            feature.dependencies = new_deps
            # Commit happens automatically on context manager exit

            return json.dumps({
                "success": True,
                "feature_id": feature_id,
                "dependencies": new_deps
            })
    except Exception as e:
        return json.dumps({"error": f"Failed to add dependency: {str(e)}"})


@mcp.tool()
def feature_remove_dependency(
    feature_id: Annotated[int, Field(ge=1, description="Feature to remove dependency from")],
    dependency_id: Annotated[int, Field(ge=1, description="ID of dependency to remove")]
) -> str:
    """Remove a dependency from a feature.

    Args:
        feature_id: The ID of the feature to remove a dependency from
        dependency_id: The ID of the dependency to remove

    Returns:
        JSON with success status and updated dependencies list, or error message
    """
    try:
        # Use atomic transaction for consistent read-modify-write
        with atomic_transaction(_session_maker) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                return json.dumps({"error": f"Feature {feature_id} not found"})

            current_deps = feature.dependencies or []
            if dependency_id not in current_deps:
                return json.dumps({"error": "Dependency does not exist"})

            # Remove dependency atomically
            new_deps = [d for d in current_deps if d != dependency_id]
            feature.dependencies = new_deps if new_deps else None
            # Commit happens automatically on context manager exit

            return json.dumps({
                "success": True,
                "feature_id": feature_id,
                "dependencies": new_deps
            })
    except Exception as e:
        return json.dumps({"error": f"Failed to remove dependency: {str(e)}"})


@mcp.tool()
def feature_get_ready(
    limit: Annotated[int, Field(default=10, ge=1, le=50, description="Max features to return")] = 10
) -> str:
    """Get all features ready to start (dependencies satisfied, not in progress).

    Useful for parallel execution - returns multiple features that can run simultaneously.
    A feature is ready if it is not passing, not in progress, and all dependencies are passing.

    Args:
        limit: Maximum number of features to return (1-50, default 10)

    Returns:
        JSON with: features (list), count (int), total_ready (int)
    """
    session = get_session()
    try:
        all_features = session.query(Feature).all()
        passing_ids = {f.id for f in all_features if f.passes}

        ready = []
        all_dicts = [f.to_dict() for f in all_features]
        for f in all_features:
            if f.passes or f.in_progress:
                continue
            if getattr(f, 'needs_human_input', False):
                continue
            deps = f.dependencies or []
            if all(dep_id in passing_ids for dep_id in deps):
                ready.append(f.to_dict())

        # Sort by scheduling score (higher = first), then priority, then id
        scores = compute_scheduling_scores(all_dicts)
        ready.sort(key=lambda f: (-scores.get(f["id"], 0), f["priority"], f["id"]))

        return json.dumps({
            "features": ready[:limit],
            "count": len(ready[:limit]),
            "total_ready": len(ready)
        })
    finally:
        session.close()


@mcp.tool()
def feature_get_blocked(
    limit: Annotated[int, Field(default=20, ge=1, le=100, description="Max features to return")] = 20
) -> str:
    """Get features that are blocked by unmet dependencies.

    Returns features that have dependencies which are not yet passing.
    Each feature includes a 'blocked_by' field listing the blocking feature IDs.

    Args:
        limit: Maximum number of features to return (1-100, default 20)

    Returns:
        JSON with: features (list with blocked_by field), count (int), total_blocked (int)
    """
    session = get_session()
    try:
        all_features = session.query(Feature).all()
        passing_ids = {f.id for f in all_features if f.passes}

        blocked = []
        for f in all_features:
            if f.passes:
                continue
            deps = f.dependencies or []
            blocking = [d for d in deps if d not in passing_ids]
            if blocking:
                blocked.append({
                    **f.to_dict(),
                    "blocked_by": blocking
                })

        return json.dumps({
            "features": blocked[:limit],
            "count": len(blocked[:limit]),
            "total_blocked": len(blocked)
        })
    finally:
        session.close()


@mcp.tool()
def feature_get_graph() -> str:
    """Get dependency graph data for visualization.

    Returns nodes (features) and edges (dependencies) for rendering a graph.
    Each node includes status: 'pending', 'in_progress', 'done', or 'blocked'.

    Returns:
        JSON with: nodes (list), edges (list of {source, target})
    """
    session = get_session()
    try:
        all_features = session.query(Feature).all()
        passing_ids = {f.id for f in all_features if f.passes}

        nodes = []
        edges = []

        for f in all_features:
            deps = f.dependencies or []
            blocking = [d for d in deps if d not in passing_ids]

            if f.passes:
                status = "done"
            elif getattr(f, 'needs_human_input', False):
                status = "needs_human_input"
            elif blocking:
                status = "blocked"
            elif f.in_progress:
                status = "in_progress"
            else:
                status = "pending"

            nodes.append({
                "id": f.id,
                "name": f.name,
                "category": f.category,
                "status": status,
                "priority": f.priority,
                "dependencies": deps
            })

            for dep_id in deps:
                edges.append({"source": dep_id, "target": f.id})

        return json.dumps({
            "nodes": nodes,
            "edges": edges
        })
    finally:
        session.close()


@mcp.tool()
def feature_set_dependencies(
    feature_id: Annotated[int, Field(ge=1, description="Feature to set dependencies for")],
    dependency_ids: Annotated[list[int], Field(description="List of dependency feature IDs")]
) -> str:
    """Set all dependencies for a feature at once, replacing any existing dependencies.

    Validates: self-reference, existence of all dependencies, circular dependencies, max limit.

    Args:
        feature_id: The ID of the feature to set dependencies for
        dependency_ids: List of feature IDs that must be completed first

    Returns:
        JSON with success status and updated dependencies list, or error message
    """
    try:
        # Security: Self-reference check (can do before transaction)
        if feature_id in dependency_ids:
            return json.dumps({"error": "A feature cannot depend on itself"})

        # Security: Max dependencies limit
        if len(dependency_ids) > MAX_DEPENDENCIES_PER_FEATURE:
            return json.dumps({"error": f"Maximum {MAX_DEPENDENCIES_PER_FEATURE} dependencies allowed"})

        # Check for duplicates
        if len(dependency_ids) != len(set(dependency_ids)):
            return json.dumps({"error": "Duplicate dependencies not allowed"})

        # Use atomic transaction for consistent cycle detection
        with atomic_transaction(_session_maker) as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if not feature:
                return json.dumps({"error": f"Feature {feature_id} not found"})

            # Validate all dependencies exist
            all_feature_ids = {f.id for f in session.query(Feature).all()}
            missing = [d for d in dependency_ids if d not in all_feature_ids]
            if missing:
                return json.dumps({"error": f"Dependencies not found: {missing}"})

            # Check for circular dependencies
            # Within IMMEDIATE transaction, snapshot is protected by write lock
            all_features = [f.to_dict() for f in session.query(Feature).all()]
            test_features = []
            for f in all_features:
                if f["id"] == feature_id:
                    test_features.append({**f, "dependencies": dependency_ids})
                else:
                    test_features.append(f)

            for dep_id in dependency_ids:
                if would_create_circular_dependency(test_features, feature_id, dep_id):
                    return json.dumps({"error": f"Cannot add dependency {dep_id}: would create circular dependency"})

            # Set dependencies atomically
            sorted_deps = sorted(dependency_ids) if dependency_ids else None
            feature.dependencies = sorted_deps
            # Commit happens automatically on context manager exit

            return json.dumps({
                "success": True,
                "feature_id": feature_id,
                "dependencies": sorted_deps or []
            })
    except Exception as e:
        return json.dumps({"error": f"Failed to set dependencies: {str(e)}"})


@mcp.tool()
def feature_request_human_input(
    feature_id: Annotated[int, Field(description="The ID of the feature that needs human input", ge=1)],
    prompt: Annotated[str, Field(min_length=1, description="Explain what you need from the human and why")],
    fields: Annotated[list[dict], Field(min_length=1, description="List of input fields to collect")]
) -> str:
    """Request structured input from a human for a feature that is blocked.

    Use this ONLY when the feature genuinely cannot proceed without human intervention:
    - Creating API keys or external accounts
    - Choosing between design approaches that require human preference
    - Configuring external services the agent cannot access
    - Providing credentials or secrets

    Do NOT use this for issues you can solve yourself (debugging, reading docs, etc.).

    The feature will be moved out of in_progress and into a "needs human input" state.
    Once the human provides their response, the feature returns to the pending queue
    and will include the human's response when you pick it up again.

    Args:
        feature_id: The ID of the feature that needs human input
        prompt: A clear explanation of what you need and why
        fields: List of input fields, each with:
            - id (str): Unique field identifier
            - label (str): Human-readable label
            - type (str): "text", "textarea", "select", or "boolean" (default: "text")
            - required (bool): Whether the field is required (default: true)
            - placeholder (str, optional): Placeholder text
            - options (list, optional): For select type: [{value, label}]

    Returns:
        JSON with success confirmation or error message
    """
    # Validate fields
    VALID_FIELD_TYPES = {"text", "textarea", "select", "boolean"}
    seen_ids: set[str] = set()
    for i, field in enumerate(fields):
        if "id" not in field or "label" not in field:
            return json.dumps({"error": f"Field at index {i} missing required 'id' or 'label'"})
        fid = field["id"]
        flabel = field["label"]
        if not isinstance(fid, str) or not fid.strip():
            return json.dumps({"error": f"Field at index {i} has empty or invalid 'id'"})
        if not isinstance(flabel, str) or not flabel.strip():
            return json.dumps({"error": f"Field at index {i} has empty or invalid 'label'"})
        if fid in seen_ids:
            return json.dumps({"error": f"Duplicate field id '{fid}' at index {i}"})
        seen_ids.add(fid)
        ftype = field.get("type", "text")
        if ftype not in VALID_FIELD_TYPES:
            return json.dumps({"error": f"Field at index {i} has invalid type '{ftype}'. Must be one of: {', '.join(sorted(VALID_FIELD_TYPES))}"})
        if ftype == "select":
            options = field.get("options")
            if not options or not isinstance(options, list):
                return json.dumps({"error": f"Field at index {i} is type 'select' but missing or invalid 'options' array"})
            for j, opt in enumerate(options):
                if not isinstance(opt, dict):
                    return json.dumps({"error": f"Field at index {i}, option {j} must be an object with 'value' and 'label'"})
                if "value" not in opt or "label" not in opt:
                    return json.dumps({"error": f"Field at index {i}, option {j} missing required 'value' or 'label'"})
                if not isinstance(opt["value"], str) or not opt["value"].strip():
                    return json.dumps({"error": f"Field at index {i}, option {j} has empty or invalid 'value'"})
                if not isinstance(opt["label"], str) or not opt["label"].strip():
                    return json.dumps({"error": f"Field at index {i}, option {j} has empty or invalid 'label'"})
        elif field.get("options"):
            return json.dumps({"error": f"Field at index {i} has 'options' but type is '{ftype}' (only 'select' uses options)"})

    request_data = {
        "prompt": prompt,
        "fields": fields,
    }

    session = get_session()
    try:
        # Atomically set needs_human_input, clear in_progress, store request, clear previous response
        result = session.execute(text("""
            UPDATE features
            SET needs_human_input = 1,
                in_progress = 0,
                human_input_request = :request,
                human_input_response = NULL
            WHERE id = :id AND passes = 0 AND in_progress = 1
        """), {"id": feature_id, "request": json.dumps(request_data)})
        session.commit()

        if result.rowcount == 0:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            if feature is None:
                return json.dumps({"error": f"Feature with ID {feature_id} not found"})
            if feature.passes:
                return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})
            if not feature.in_progress:
                return json.dumps({"error": f"Feature with ID {feature_id} is not in progress"})
            return json.dumps({"error": "Failed to request human input for unknown reason"})

        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "name": feature.name,
            "message": f"Feature '{feature.name}' is now blocked waiting for human input"
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to request human input: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def ask_user(
    questions: Annotated[list[dict], Field(description="List of questions to ask, each with question, header, options (list of {label, description}), and multiSelect (bool)")]
) -> str:
    """Ask the user structured questions with selectable options.

    Use this when you need clarification or want to offer choices to the user.
    Each question has a short header, the question text, and 2-4 clickable options.
    The user's selections will be returned as your next message.

    Args:
        questions: List of questions, each with:
            - question (str): The question to ask
            - header (str): Short label (max 12 chars)
            - options (list): Each with label (str) and description (str)
            - multiSelect (bool): Allow multiple selections (default false)

    Returns:
        Acknowledgment that questions were presented to the user
    """
    # Validate input
    for i, q in enumerate(questions):
        if not all(key in q for key in ["question", "header", "options"]):
            return json.dumps({"error": f"Question at index {i} missing required fields"})
        if len(q["options"]) < 2 or len(q["options"]) > 4:
            return json.dumps({"error": f"Question at index {i} must have 2-4 options"})

    return "Questions presented to the user. Their response will arrive as your next message."


if __name__ == "__main__":
    mcp.run()
