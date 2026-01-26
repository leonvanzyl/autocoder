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
- feature_update: Update a feature's editable fields
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
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy import text

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

# NOTE: The old threading.Lock() was removed because it only worked per-process,
# not cross-process. In parallel mode, multiple MCP servers run in separate
# processes, so the lock was useless. We now use atomic SQL operations instead.

# Lock for atomic claim operations to prevent multi-agent race conditions
_claim_lock = threading.Lock()


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
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as passing", ge=1)],
    quality_result: Annotated[dict | None, Field(description="Optional quality gate results to store as test evidence", default=None)] = None
) -> str:
    """Mark a feature as passing after successful implementation.

    IMPORTANT: In strict mode (default), this will automatically run quality checks
    (lint, type-check) and BLOCK if they fail. You must fix the issues and try again.

    Updates the feature's passes field to true and clears the in_progress flag.
    Use this after you have implemented the feature and verified it works correctly.

    Optionally stores quality gate results (lint, type-check, test outputs) as
    test evidence for compliance and debugging purposes.

    Args:
        feature_id: The ID of the feature to mark as passing
        quality_result: Optional dict with quality gate results (lint, type-check, etc.)

    Returns:
        JSON with success confirmation: {success, feature_id, name}
    """
    # Import quality gates module
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from quality_gates import verify_quality, load_quality_config

    session = get_session()
    try:
        # First get the feature name for the response
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Load quality gates config
        config = load_quality_config(PROJECT_DIR)
        quality_enabled = config.get("enabled", True)
        strict_mode = config.get("strict_mode", True)

        # Run quality checks in strict mode
        if quality_enabled and strict_mode:
            checks_config = config.get("checks", {})

            quality_result = verify_quality(
                PROJECT_DIR,
                run_lint=checks_config.get("lint", True),
                run_type_check=checks_config.get("type_check", True),
                run_custom=True,
                custom_script_path=checks_config.get("custom_script"),
            )

            # Store the quality result
            feature.quality_result = quality_result

            # Block if quality checks failed
            if not quality_result["passed"]:
                feature.in_progress = False  # Release the feature
                session.commit()

                # Build detailed error message
                failed_checks = []
                for name, check in quality_result["checks"].items():
                    if not check["passed"]:
                        output_preview = check["output"][:500] if check["output"] else "No output"
                        failed_checks.append({
                            "check": check["name"],
                            "output": output_preview,
                        })

                return json.dumps({
                    "error": "quality_check_failed",
                    "message": f"Cannot mark feature #{feature_id} as passing - quality checks failed",
                    "summary": quality_result["summary"],
                    "failed_checks": failed_checks,
                    "hint": "Fix the issues above and try feature_mark_passing again",
                }, indent=2)

        # All checks passed (or disabled) - mark as passing
        feature.passes = True
        feature.in_progress = False
        feature.completed_at = _utc_now()
        feature.last_error = None  # Clear any previous error

        # Store quality gate results as test evidence
        if quality_result:
            feature.quality_result = quality_result

        session.commit()

        return json.dumps({"success": True, "feature_id": feature_id, "name": name})
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

    Uses atomic SQL UPDATE for parallel safety.

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
        # Check if feature exists first
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.passes = False
        feature.in_progress = False
        feature.last_failed_at = _utc_now()
        if error_message:
            # Truncate to 10KB to prevent storing huge stack traces
            feature.last_error = error_message[:10240] if len(error_message) > 10240 else error_message
        else:
            # Clear stale error message when no new error is provided
            feature.last_error = None
        session.commit()

        # Refresh to get updated state
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
        # Use application-level _claim_lock to serialize feature selection and updates.
        # This prevents race conditions where concurrent requests both select
        # the same features (with lowest regression_count) before either commits.
        # The lock ensures requests are serialized: the second request will block
        # until the first commits, then see the updated regression_count values.
        with _claim_lock:
            features = (
                session.query(Feature)
                .filter(Feature.passes == True)
                .order_by(Feature.regression_count.asc(), Feature.id.asc())
                .limit(limit)
                .all()
            )

            # Increment regression_count for selected features (now safe under lock)
            for feature in features:
                feature.regression_count = (feature.regression_count or 0) + 1
            session.commit()

            # Refresh to get updated counts after commit
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

    Use this ONLY for truly external blockers you cannot control:
    - External API credentials not configured (e.g., Stripe keys, OAuth secrets)
    - External service unavailable or inaccessible
    - Hardware/environment limitations you cannot fulfill

    DO NOT skip for:
    - Missing functionality (build it yourself)
    - Refactoring features (implement them like any other feature)
    - "Unclear requirements" (interpret the intent and implement)
    - Dependencies on other features (build those first)

    The feature's priority is set to max_priority + 1, so it will be
    worked on after all other pending features. Also clears the in_progress
    flag so the feature returns to "pending" status.

    Uses atomic SQL UPDATE with subquery for parallel safety.

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

    Uses atomic locking to prevent race conditions when multiple agents
    try to claim the same feature simultaneously.

    Args:
        feature_id: The ID of the feature to mark as in-progress

    Returns:
        JSON with the updated feature details, or error if not found or already in-progress.
    """
    # Use lock to prevent race condition when multiple agents try to claim simultaneously
    with _claim_lock:
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

    Uses atomic locking to prevent race conditions when multiple agents
    try to claim the same feature simultaneously.

    Args:
        feature_id: The ID of the feature to claim and retrieve

    Returns:
        JSON with feature details including claimed status, or error if not found.
    """
    # Use lock to ensure atomic claim operation across multiple processes
    with _claim_lock:
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

    Uses atomic SQL UPDATE for parallel safety.

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
        
        # Persist the regression test outcome
        if tested_ok:
            # Feature still passes - clear failure markers
            feature.passes = True
            feature.last_failed_at = None
            feature.last_error = None
        else:
            # Regression detected - mark as failing
            feature.passes = False
            feature.last_failed_at = _utc_now()
        
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

    Uses EXCLUSIVE transaction to prevent priority collisions in parallel mode.

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
        # Use EXCLUSIVE transaction for bulk inserts to prevent conflicts
        with atomic_transaction(_session_maker, "EXCLUSIVE") as session:
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
                    priority=start_priority + i,  # Guaranteed unique within EXCLUSIVE transaction
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

    Uses IMMEDIATE transaction for parallel safety.

    Args:
        category: Feature category for grouping (e.g., 'Authentication', 'API', 'UI')
        name: Descriptive name for the feature
        description: Detailed description of what this feature should do
        steps: List of steps to implement or verify the feature

    Returns:
        JSON with the created feature details including its ID
    """
    try:
        # Use IMMEDIATE transaction to prevent priority collisions
        with atomic_transaction(_session_maker, "IMMEDIATE") as session:
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
def feature_update(
    feature_id: Annotated[int, Field(description="The ID of the feature to update", ge=1)],
    category: Annotated[str | None, Field(default=None, min_length=1, max_length=100, description="New category (optional)")] = None,
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=255, description="New name (optional)")] = None,
    description: Annotated[str | None, Field(default=None, min_length=1, description="New description (optional)")] = None,
    steps: Annotated[list[str] | None, Field(default=None, min_length=1, description="New steps list (optional)")] = None,
) -> str:
    """Update an existing feature's editable fields.

    Use this when the user asks to modify, update, edit, or change a feature.
    Only the provided fields will be updated; others remain unchanged.

    Cannot update: id, priority (use feature_skip), passes, in_progress (agent-controlled)

    Args:
        feature_id: The ID of the feature to update
        category: New category (optional)
        name: New name (optional)
        description: New description (optional)
        steps: New steps list (optional)

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Collect updates
        updates = {}
        if category is not None:
            updates["category"] = category
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if steps is not None:
            updates["steps"] = steps

        if not updates:
            return json.dumps({"error": "No fields to update. Provide at least one of: category, name, description, steps"})

        # Apply updates
        for field, value in updates.items():
            setattr(feature, field, value)

        session.commit()
        session.refresh(feature)

        return json.dumps({
            "success": True,
            "message": f"Updated feature: {feature.name}",
            "feature": feature.to_dict()
        }, indent=2)
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

    Uses IMMEDIATE transaction to prevent stale reads during cycle detection.

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

        # Use IMMEDIATE transaction for consistent cycle detection
        with atomic_transaction(_session_maker, "IMMEDIATE") as session:
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

    Uses IMMEDIATE transaction for parallel safety.

    Args:
        feature_id: The ID of the feature to remove a dependency from
        dependency_id: The ID of the dependency to remove

    Returns:
        JSON with success status and updated dependencies list, or error message
    """
    try:
        # Use IMMEDIATE transaction for consistent read-modify-write
        with atomic_transaction(_session_maker, "IMMEDIATE") as session:
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
def feature_delete(
    feature_id: Annotated[int, Field(description="The ID of the feature to delete", ge=1)]
) -> str:
    """Delete a feature from the backlog.

    Use this when the user asks to remove, delete, or drop a feature.
    This removes the feature from tracking only - any implemented code remains.

    For completed features, consider suggesting the user create a new "removal"
    feature if they also want the code removed.

    Args:
        feature_id: The ID of the feature to delete

    Returns:
        JSON with success message and deleted feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Check for dependent features that reference this feature
        # Query all features and filter those that have this feature_id in their dependencies
        all_features = session.query(Feature).all()
        dependent_features = [
            f for f in all_features 
            if f.dependencies and feature_id in f.dependencies
        ]

        # Cascade-update dependent features to remove this feature_id from their dependencies
        if dependent_features:
            for dependent in dependent_features:
                deps = dependent.dependencies.copy()
                deps.remove(feature_id)
                dependent.dependencies = deps if deps else None
            session.flush()  # Flush updates before deletion

        # Store details before deletion for confirmation message
        feature_data = feature.to_dict()

        session.delete(feature)
        session.commit()

        result = {
            "success": True,
            "message": f"Deleted feature: {feature_data['name']}",
            "deleted_feature": feature_data
        }
        
        # Include info about updated dependencies if any
        if dependent_features:
            result["updated_dependents"] = [
                {"id": f.id, "name": f.name} for f in dependent_features
            ]
            result["message"] += f" (removed dependency reference from {len(dependent_features)} dependent feature(s))"

        return json.dumps(result, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
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

    Uses IMMEDIATE transaction to prevent stale reads during cycle detection.

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

        # Use IMMEDIATE transaction for consistent cycle detection
        with atomic_transaction(_session_maker, "IMMEDIATE") as session:
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
            # Temporarily update the feature's dependencies for cycle check
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


# =============================================================================
# Quality Gates Tools
# =============================================================================


@mcp.tool()
def feature_verify_quality(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to verify quality for")]
) -> str:
    """Verify code quality before marking a feature as passing.

    Runs configured quality checks:
    - Lint (ESLint/Biome for JS/TS, ruff/flake8 for Python)
    - Type check (TypeScript tsc, Python mypy)
    - Custom script (.autocoder/quality-checks.sh if exists)

    Configuration is loaded from .autocoder/config.json (quality_gates section).

    IMPORTANT: In strict mode (default), feature_mark_passing will automatically
    call this and BLOCK if quality checks fail. Use this tool for manual checks
    or to preview quality status.

    Args:
        feature_id: The ID of the feature being verified

    Returns:
        JSON with: passed (bool), checks (dict), summary (str)
    """
    # Import here to avoid circular imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from quality_gates import verify_quality, load_quality_config

    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()
        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Load config
        config = load_quality_config(PROJECT_DIR)

        if not config.get("enabled", True):
            return json.dumps({
                "passed": True,
                "summary": "Quality gates disabled in config",
                "checks": {}
            })

        checks_config = config.get("checks", {})

        # Run quality checks
        result = verify_quality(
            PROJECT_DIR,
            run_lint=checks_config.get("lint", True),
            run_type_check=checks_config.get("type_check", True),
            run_custom=True,
            custom_script_path=checks_config.get("custom_script"),
        )

        # Store result in database
        feature.quality_result = result
        session.commit()

        return json.dumps({
            "feature_id": feature_id,
            "passed": result["passed"],
            "summary": result["summary"],
            "checks": result["checks"],
            "timestamp": result["timestamp"],
        }, indent=2)
    finally:
        session.close()


# =============================================================================
# Error Recovery Tools
# =============================================================================


@mcp.tool()
def feature_report_failure(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID that failed")],
    reason: Annotated[str, Field(min_length=1, description="Description of why the feature failed")]
) -> str:
    """Report a failure for a feature, incrementing its failure count.

    Use this when you encounter an error implementing a feature.
    The failure information helps with retry logic and escalation.

    Behavior based on failure_count:
    - count < 3: Agent should retry with the failure reason as context
    - count >= 3: Agent should skip this feature (use feature_skip)
    - count >= 5: Feature may need to be broken into smaller features
    - count >= 7: Feature is escalated for human review

    Args:
        feature_id: The ID of the feature that failed
        reason: Description of the failure (error message, blocker, etc.)

    Returns:
        JSON with updated failure info: failure_count, failure_reason, recommendation
    """
    from datetime import datetime

    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Update failure tracking
        feature.failure_count = (feature.failure_count or 0) + 1
        feature.failure_reason = reason
        feature.last_failure_at = datetime.utcnow().isoformat()

        # Clear in_progress so the feature returns to pending
        feature.in_progress = False

        session.commit()
        session.refresh(feature)

        # Determine recommendation based on failure count
        count = feature.failure_count
        if count < 3:
            recommendation = "retry"
            message = f"Retry #{count}. Include the failure reason in your next attempt."
        elif count < 5:
            recommendation = "skip"
            message = f"Failed {count} times. Consider skipping with feature_skip and trying later."
        elif count < 7:
            recommendation = "decompose"
            message = f"Failed {count} times. This feature may need to be broken into smaller parts."
        else:
            recommendation = "escalate"
            message = f"Failed {count} times. This feature needs human review."

        return json.dumps({
            "feature_id": feature_id,
            "failure_count": feature.failure_count,
            "failure_reason": feature.failure_reason,
            "last_failure_at": feature.last_failure_at,
            "recommendation": recommendation,
            "message": message
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_stuck() -> str:
    """Get all features that have failed at least once.

    Returns features sorted by failure_count (descending), showing
    which features are having the most trouble.

    Use this to identify problematic features that may need:
    - Manual intervention
    - Decomposition into smaller features
    - Dependency adjustments

    Returns:
        JSON with: features (list with failure info), count (int)
    """
    session = get_session()
    try:
        features = (
            session.query(Feature)
            .filter(Feature.failure_count > 0)
            .order_by(Feature.failure_count.desc())
            .all()
        )

        result = []
        for f in features:
            result.append({
                "id": f.id,
                "name": f.name,
                "category": f.category,
                "failure_count": f.failure_count,
                "failure_reason": f.failure_reason,
                "last_failure_at": f.last_failure_at,
                "passes": f.passes,
                "in_progress": f.in_progress,
            })

        return json.dumps({
            "features": result,
            "count": len(result)
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_clear_all_in_progress() -> str:
    """Clear ALL in_progress flags from all features.

    Use this on agent startup to unstick features from previous
    interrupted sessions. When an agent is stopped mid-work, features
    can be left with in_progress=True and become orphaned.

    This does NOT affect:
    - passes status (completed features stay completed)
    - failure_count (failure history is preserved)
    - priority (queue order is preserved)

    Returns:
        JSON with: cleared (int) - number of features that were unstuck
    """
    session = get_session()
    try:
        # Count features that will be cleared
        in_progress_count = (
            session.query(Feature)
            .filter(Feature.in_progress == True)
            .count()
        )

        if in_progress_count == 0:
            return json.dumps({
                "cleared": 0,
                "message": "No features were in_progress"
            })

        # Clear all in_progress flags
        session.execute(
            text("UPDATE features SET in_progress = 0 WHERE in_progress = 1")
        )
        session.commit()

        return json.dumps({
            "cleared": in_progress_count,
            "message": f"Cleared in_progress flag from {in_progress_count} feature(s)"
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_reset_failure(
    feature_id: Annotated[int, Field(ge=1, description="Feature ID to reset")]
) -> str:
    """Reset the failure counter and reason for a feature.

    Use this when you want to give a feature a fresh start,
    for example after fixing an underlying issue.

    Args:
        feature_id: The ID of the feature to reset

    Returns:
        JSON with the updated feature details
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.failure_count = 0
        feature.failure_reason = None
        feature.last_failure_at = None

        session.commit()
        session.refresh(feature)

        return json.dumps({
            "success": True,
            "message": f"Reset failure tracking for feature #{feature_id}",
            "feature": feature.to_dict()
        }, indent=2)
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
