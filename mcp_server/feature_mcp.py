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
- feature_get_for_regression: Get passing features for regression testing (least-tested-first)
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
- feature_start_attempt: Start tracking an agent attempt on a feature
- feature_end_attempt: End tracking an agent attempt with outcome
- feature_get_attempts: Get attempt history for a feature
- feature_log_error: Log an error for a feature
- feature_get_errors: Get error history for a feature
- feature_resolve_error: Mark an error as resolved

Note: Feature selection (which feature to work on) is handled by the
orchestrator, not by agents. Agents receive pre-assigned feature IDs.
"""

import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, FeatureAttempt, FeatureError, create_database
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

# Lock for priority assignment to prevent race conditions
_priority_lock = threading.Lock()


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
            func.sum(case((Feature.in_progress == True, 1), else_=0)).label('in_progress')
        ).first()

        total = result.total or 0
        passing = int(result.passing or 0)
        in_progress = int(result.in_progress or 0)
        percentage = round((passing / total) * 100, 1) if total > 0 else 0.0

        return json.dumps({
            "passing": passing,
            "in_progress": in_progress,
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
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.passes = True
        feature.in_progress = False
        feature.completed_at = _utc_now()
        feature.last_error = None  # Clear any previous error
        session.commit()

        return json.dumps({"success": True, "feature_id": feature_id, "name": feature.name})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to mark feature passing: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_mark_failing(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as failing", ge=1)],
    error_message: Annotated[str | None, Field(description="Optional error message describing why the feature failed", default=None)] = None
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
        error_message: Optional message describing the failure (e.g., test output, stack trace)

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.passes = False
        feature.in_progress = False
        feature.last_failed_at = _utc_now()
        if error_message:
            # Truncate to 10KB to prevent storing huge stack traces
            feature.last_error = error_message[:10240] if len(error_message) > 10240 else error_message
        session.commit()
        session.refresh(feature)

        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "name": feature.name,
            "message": "Regression detected"
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to mark feature failing: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_get_for_regression(
    limit: Annotated[int, Field(default=3, ge=1, le=10, description="Maximum number of passing features to return")] = 3
) -> str:
    """Get passing features for regression testing, prioritizing least-tested features.

    Returns features that are currently passing, ordered by regression_count (ascending)
    so that features tested fewer times are prioritized. This ensures even distribution
    of regression testing across all features, avoiding duplicate testing of the same
    features while others are never tested.

    Each returned feature has its regression_count incremented to track testing frequency.

    Args:
        limit: Maximum number of features to return (1-10, default 3)

    Returns:
        JSON with list of features for regression testing.
    """
    session = get_session()
    try:
        # Select features with lowest regression_count first (least tested)
        # Use id as secondary sort for deterministic ordering when counts are equal
        features = (
            session.query(Feature)
            .filter(Feature.passes == True)
            .order_by(Feature.regression_count.asc(), Feature.id.asc())
            .limit(limit)
            .all()
        )

        # Increment regression_count for selected features
        for feature in features:
            feature.regression_count = (feature.regression_count or 0) + 1
        session.commit()

        # Refresh to get updated counts
        for feature in features:
            session.refresh(feature)

        return json.dumps({
            "features": [f.to_dict() for f in features],
            "count": len(features)
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to get regression features: {str(e)}"})
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

        # Use lock to prevent race condition in priority assignment
        with _priority_lock:
            # Get max priority and set this feature to max + 1
            max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
            new_priority = (max_priority_result[0] + 1) if max_priority_result else 1

            feature.priority = new_priority
            feature.in_progress = False
            session.commit()

        session.refresh(feature)

        return json.dumps({
            "id": feature.id,
            "name": feature.name,
            "old_priority": old_priority,
            "new_priority": new_priority,
            "message": f"Feature '{feature.name}' moved to end of queue"
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
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})

        if feature.in_progress:
            return json.dumps({"error": f"Feature with ID {feature_id} is already in-progress"})

        feature.in_progress = True
        feature.started_at = _utc_now()
        session.commit()
        session.refresh(feature)

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
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": f"Feature with ID {feature_id} is already passing"})

        # Idempotent: if already in-progress, just return details
        already_claimed = feature.in_progress
        if not already_claimed:
            feature.in_progress = True
            feature.started_at = _utc_now()
            session.commit()
            session.refresh(feature)

        result = feature.to_dict()
        result["already_claimed"] = already_claimed
        return json.dumps(result)
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
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.in_progress = False
        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict())
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to clear in-progress status: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_release_testing(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to release testing claim")],
    tested_ok: Annotated[bool, Field(description="True if feature passed, False if regression found")]
) -> str:
    """Release a testing claim on a feature.

    Testing agents MUST call this when done, regardless of outcome.

    Args:
        feature_id: The ID of the feature to release
        tested_ok: True if the feature still passes, False if a regression was found

    Returns:
        JSON with: success, feature_id, tested_ok, message
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        feature.in_progress = False
        session.commit()

        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "tested_ok": tested_ok,
            "message": f"Released testing claim on feature #{feature_id}"
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
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
    session = get_session()
    try:
        # Use lock to prevent race condition in priority assignment
        with _priority_lock:
            # Get the starting priority
            max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
            start_priority = (max_priority_result[0] + 1) if max_priority_result else 1

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

            # Second pass: create all features
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
                    created_features[i].dependencies = sorted(dep_ids)
                    deps_count += 1

            session.commit()

        return json.dumps({
            "created": len(created_features),
            "with_dependencies": deps_count
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


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
    session = get_session()
    try:
        # Use lock to prevent race condition in priority assignment
        with _priority_lock:
            # Get the next priority
            max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
            next_priority = (max_priority_result[0] + 1) if max_priority_result else 1

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
            session.commit()

        session.refresh(db_feature)

        return json.dumps({
            "success": True,
            "message": f"Created feature: {name}",
            "feature": db_feature.to_dict()
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


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
    session = get_session()
    try:
        # Security: Self-reference check
        if feature_id == dependency_id:
            return json.dumps({"error": "A feature cannot depend on itself"})

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
        # would_create_circular_dependency(features, source_id, target_id)
        # source_id = feature gaining the dependency, target_id = feature being depended upon
        all_features = [f.to_dict() for f in session.query(Feature).all()]
        if would_create_circular_dependency(all_features, feature_id, dependency_id):
            return json.dumps({"error": "Cannot add: would create circular dependency"})

        # Add dependency
        current_deps.append(dependency_id)
        feature.dependencies = sorted(current_deps)
        session.commit()

        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "dependencies": feature.dependencies
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to add dependency: {str(e)}"})
    finally:
        session.close()


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
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        current_deps = feature.dependencies or []
        if dependency_id not in current_deps:
            return json.dumps({"error": "Dependency does not exist"})

        current_deps.remove(dependency_id)
        feature.dependencies = current_deps if current_deps else None
        session.commit()

        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "dependencies": feature.dependencies or []
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to remove dependency: {str(e)}"})
    finally:
        session.close()


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
        # Optimized: Query only passing IDs (smaller result set)
        passing_ids = {
            f.id for f in session.query(Feature.id).filter(Feature.passes == True).all()
        }

        # Optimized: Query only candidate features (not passing, not in progress)
        candidates = session.query(Feature).filter(
            Feature.passes == False,
            Feature.in_progress == False
        ).all()

        # Filter by dependencies (must be done in Python since deps are JSON)
        ready = []
        for f in candidates:
            deps = f.dependencies or []
            if all(dep_id in passing_ids for dep_id in deps):
                ready.append(f.to_dict())

        # Sort by scheduling score (higher = first), then priority, then id
        # Need all features for scoring computation
        all_dicts = [f.to_dict() for f in candidates]
        all_dicts.extend([{"id": pid} for pid in passing_ids])
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
        # Optimized: Query only passing IDs
        passing_ids = {
            f.id for f in session.query(Feature.id).filter(Feature.passes == True).all()
        }

        # Optimized: Query only non-passing features (candidates for being blocked)
        candidates = session.query(Feature).filter(Feature.passes == False).all()

        blocked = []
        for f in candidates:
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
    session = get_session()
    try:
        # Security: Self-reference check
        if feature_id in dependency_ids:
            return json.dumps({"error": "A feature cannot depend on itself"})

        # Security: Max dependencies limit
        if len(dependency_ids) > MAX_DEPENDENCIES_PER_FEATURE:
            return json.dumps({"error": f"Maximum {MAX_DEPENDENCIES_PER_FEATURE} dependencies allowed"})

        # Check for duplicates
        if len(dependency_ids) != len(set(dependency_ids)):
            return json.dumps({"error": "Duplicate dependencies not allowed"})

        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        # Validate all dependencies exist
        all_feature_ids = {f.id for f in session.query(Feature).all()}
        missing = [d for d in dependency_ids if d not in all_feature_ids]
        if missing:
            return json.dumps({"error": f"Dependencies not found: {missing}"})

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
                return json.dumps({"error": f"Cannot add dependency {dep_id}: would create circular dependency"})

        # Set dependencies
        feature.dependencies = sorted(dependency_ids) if dependency_ids else None
        session.commit()

        return json.dumps({
            "success": True,
            "feature_id": feature_id,
            "dependencies": feature.dependencies or []
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to set dependencies: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_start_attempt(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to start attempt on")],
    agent_type: Annotated[str, Field(description="Agent type: 'initializer', 'coding', or 'testing'")],
    agent_id: Annotated[str | None, Field(description="Optional unique agent identifier", default=None)] = None,
    agent_index: Annotated[int | None, Field(description="Optional agent index for parallel runs", default=None)] = None
) -> str:
    """Start tracking an agent's attempt on a feature.

    Creates a new FeatureAttempt record to track which agent is working on
    which feature, with timing and outcome tracking.

    Args:
        feature_id: The ID of the feature being worked on
        agent_type: Type of agent ("initializer", "coding", "testing")
        agent_id: Optional unique identifier for the agent
        agent_index: Optional index for parallel agent runs (0, 1, 2, etc.)

    Returns:
        JSON with the created attempt ID and details
    """
    session = get_session()
    try:
        # Verify feature exists
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        # Validate agent_type
        valid_types = {"initializer", "coding", "testing"}
        if agent_type not in valid_types:
            return json.dumps({"error": f"Invalid agent_type. Must be one of: {valid_types}"})

        # Create attempt record
        attempt = FeatureAttempt(
            feature_id=feature_id,
            agent_type=agent_type,
            agent_id=agent_id,
            agent_index=agent_index,
            started_at=_utc_now(),
            outcome="in_progress"
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)

        return json.dumps({
            "success": True,
            "attempt_id": attempt.id,
            "feature_id": feature_id,
            "agent_type": agent_type,
            "started_at": attempt.started_at.isoformat()
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to start attempt: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_end_attempt(
    attempt_id: Annotated[int, Field(ge=1, description="Attempt ID to end")],
    outcome: Annotated[str, Field(description="Outcome: 'success', 'failure', or 'abandoned'")],
    error_message: Annotated[str | None, Field(description="Optional error message for failures", default=None)] = None
) -> str:
    """End tracking an agent's attempt on a feature.

    Updates the FeatureAttempt record with the final outcome and timing.

    Args:
        attempt_id: The ID of the attempt to end
        outcome: Final outcome ("success", "failure", "abandoned")
        error_message: Optional error message for failure cases

    Returns:
        JSON with the updated attempt details including duration
    """
    session = get_session()
    try:
        attempt = session.query(FeatureAttempt).filter(FeatureAttempt.id == attempt_id).first()
        if not attempt:
            return json.dumps({"error": f"Attempt {attempt_id} not found"})

        # Validate outcome
        valid_outcomes = {"success", "failure", "abandoned"}
        if outcome not in valid_outcomes:
            return json.dumps({"error": f"Invalid outcome. Must be one of: {valid_outcomes}"})

        # Update attempt
        attempt.ended_at = _utc_now()
        attempt.outcome = outcome
        if error_message:
            # Truncate long error messages
            attempt.error_message = error_message[:10240] if len(error_message) > 10240 else error_message

        session.commit()
        session.refresh(attempt)

        return json.dumps({
            "success": True,
            "attempt": attempt.to_dict(),
            "duration_seconds": attempt.duration_seconds
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to end attempt: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_get_attempts(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to get attempts for")],
    limit: Annotated[int, Field(default=10, ge=1, le=100, description="Max attempts to return")] = 10
) -> str:
    """Get attempt history for a feature.

    Returns all attempts made on a feature, ordered by most recent first.
    Useful for debugging and understanding which agents worked on a feature.

    Args:
        feature_id: The ID of the feature
        limit: Maximum number of attempts to return (1-100, default 10)

    Returns:
        JSON with list of attempts and statistics
    """
    session = get_session()
    try:
        # Verify feature exists
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        # Get attempts ordered by most recent
        attempts = session.query(FeatureAttempt).filter(
            FeatureAttempt.feature_id == feature_id
        ).order_by(FeatureAttempt.started_at.desc()).limit(limit).all()

        # Calculate statistics
        total_attempts = session.query(FeatureAttempt).filter(
            FeatureAttempt.feature_id == feature_id
        ).count()

        success_count = session.query(FeatureAttempt).filter(
            FeatureAttempt.feature_id == feature_id,
            FeatureAttempt.outcome == "success"
        ).count()

        failure_count = session.query(FeatureAttempt).filter(
            FeatureAttempt.feature_id == feature_id,
            FeatureAttempt.outcome == "failure"
        ).count()

        return json.dumps({
            "feature_id": feature_id,
            "feature_name": feature.name,
            "attempts": [a.to_dict() for a in attempts],
            "statistics": {
                "total_attempts": total_attempts,
                "success_count": success_count,
                "failure_count": failure_count,
                "abandoned_count": total_attempts - success_count - failure_count
            }
        })
    finally:
        session.close()


@mcp.tool()
def feature_log_error(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to log error for")],
    error_type: Annotated[str, Field(description="Error type: 'test_failure', 'lint_error', 'runtime_error', 'timeout', 'other'")],
    error_message: Annotated[str, Field(description="Error message describing what went wrong")],
    stack_trace: Annotated[str | None, Field(description="Optional full stack trace", default=None)] = None,
    agent_type: Annotated[str | None, Field(description="Optional agent type that encountered the error", default=None)] = None,
    agent_id: Annotated[str | None, Field(description="Optional agent ID", default=None)] = None,
    attempt_id: Annotated[int | None, Field(description="Optional attempt ID to link this error to", default=None)] = None
) -> str:
    """Log an error for a feature.

    Creates a new error record to track issues encountered while working on a feature.
    This maintains a full history of all errors for debugging and analysis.

    Args:
        feature_id: The ID of the feature
        error_type: Type of error (test_failure, lint_error, runtime_error, timeout, other)
        error_message: Description of the error
        stack_trace: Optional full stack trace
        agent_type: Optional type of agent that encountered the error
        agent_id: Optional identifier of the agent
        attempt_id: Optional attempt ID to associate this error with

    Returns:
        JSON with the created error ID and details
    """
    session = get_session()
    try:
        # Verify feature exists
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        # Validate error_type
        valid_types = {"test_failure", "lint_error", "runtime_error", "timeout", "other"}
        if error_type not in valid_types:
            return json.dumps({"error": f"Invalid error_type. Must be one of: {valid_types}"})

        # Truncate long messages
        truncated_message = error_message[:10240] if len(error_message) > 10240 else error_message
        truncated_trace = stack_trace[:50000] if stack_trace and len(stack_trace) > 50000 else stack_trace

        # Create error record
        error = FeatureError(
            feature_id=feature_id,
            error_type=error_type,
            error_message=truncated_message,
            stack_trace=truncated_trace,
            agent_type=agent_type,
            agent_id=agent_id,
            attempt_id=attempt_id,
            occurred_at=_utc_now()
        )
        session.add(error)

        # Also update the feature's last_error field
        feature.last_error = truncated_message
        feature.last_failed_at = _utc_now()

        session.commit()
        session.refresh(error)

        return json.dumps({
            "success": True,
            "error_id": error.id,
            "feature_id": feature_id,
            "error_type": error_type,
            "occurred_at": error.occurred_at.isoformat()
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to log error: {str(e)}"})
    finally:
        session.close()


@mcp.tool()
def feature_get_errors(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to get errors for")],
    limit: Annotated[int, Field(default=20, ge=1, le=100, description="Max errors to return")] = 20,
    include_resolved: Annotated[bool, Field(default=False, description="Include resolved errors")] = False
) -> str:
    """Get error history for a feature.

    Returns all errors recorded for a feature, ordered by most recent first.
    By default, only unresolved errors are returned.

    Args:
        feature_id: The ID of the feature
        limit: Maximum number of errors to return (1-100, default 20)
        include_resolved: Whether to include resolved errors (default False)

    Returns:
        JSON with list of errors and statistics
    """
    session = get_session()
    try:
        # Verify feature exists
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if not feature:
            return json.dumps({"error": f"Feature {feature_id} not found"})

        # Build query
        query = session.query(FeatureError).filter(FeatureError.feature_id == feature_id)
        if not include_resolved:
            query = query.filter(FeatureError.resolved == False)

        # Get errors ordered by most recent
        errors = query.order_by(FeatureError.occurred_at.desc()).limit(limit).all()

        # Calculate statistics
        total_errors = session.query(FeatureError).filter(
            FeatureError.feature_id == feature_id
        ).count()

        unresolved_count = session.query(FeatureError).filter(
            FeatureError.feature_id == feature_id,
            FeatureError.resolved == False
        ).count()

        # Count by type
        from sqlalchemy import func
        type_counts = dict(
            session.query(FeatureError.error_type, func.count(FeatureError.id))
            .filter(FeatureError.feature_id == feature_id)
            .group_by(FeatureError.error_type)
            .all()
        )

        return json.dumps({
            "feature_id": feature_id,
            "feature_name": feature.name,
            "errors": [e.to_dict() for e in errors],
            "statistics": {
                "total_errors": total_errors,
                "unresolved_count": unresolved_count,
                "resolved_count": total_errors - unresolved_count,
                "by_type": type_counts
            }
        })
    finally:
        session.close()


@mcp.tool()
def feature_resolve_error(
    error_id: Annotated[int, Field(ge=1, description="Error ID to resolve")],
    resolution_notes: Annotated[str | None, Field(description="Optional notes about how the error was resolved", default=None)] = None
) -> str:
    """Mark an error as resolved.

    Updates an error record to indicate it has been fixed or addressed.

    Args:
        error_id: The ID of the error to resolve
        resolution_notes: Optional notes about the resolution

    Returns:
        JSON with the updated error details
    """
    session = get_session()
    try:
        error = session.query(FeatureError).filter(FeatureError.id == error_id).first()
        if not error:
            return json.dumps({"error": f"Error {error_id} not found"})

        if error.resolved:
            return json.dumps({"error": "Error is already resolved"})

        error.resolved = True
        error.resolved_at = _utc_now()
        if resolution_notes:
            error.resolution_notes = resolution_notes[:5000] if len(resolution_notes) > 5000 else resolution_notes

        session.commit()
        session.refresh(error)

        return json.dumps({
            "success": True,
            "error": error.to_dict()
        })
    except Exception as e:
        session.rollback()
        return json.dumps({"error": f"Failed to resolve error: {str(e)}"})
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
