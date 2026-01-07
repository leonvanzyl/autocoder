#!/usr/bin/env python3
"""
MCP Server for Feature Management
==================================

Provides tools to manage features in the autonomous coding system,
replacing the previous FastAPI-based REST API.

Tools:
- feature_get_stats: Get progress statistics
- feature_get_next: Get next feature to implement
- feature_get_for_regression: Get random passing features for testing
- feature_mark_passing: Mark a feature as passing
- feature_skip: Skip a feature (move to end of queue)
- feature_mark_in_progress: Mark a feature as in-progress
- feature_clear_in_progress: Clear in-progress status
- feature_create_bulk: Create multiple features at once
"""

import argparse
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.sql.expression import func

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, FeatureStatus, create_database
from api.migration import migrate_json_to_sqlite


def get_project_dir() -> Path:
    """Get project directory from CLI args or environment variable.

    Supports both --project-dir CLI argument (preferred on Windows to avoid
    command line length limits) and PROJECT_DIR environment variable.
    """
    parser = argparse.ArgumentParser(description="Feature MCP Server")
    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project directory path"
    )
    args, _ = parser.parse_known_args()

    if args.project_dir:
        return Path(args.project_dir).resolve()

    # Fall back to environment variable
    return Path(os.environ.get("PROJECT_DIR", ".")).resolve()


# Configuration - supports both CLI args and environment variable
PROJECT_DIR = get_project_dir()


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


def init_database_direct(project_dir: Path) -> None:
    """
    Initialize database directly without running the MCP server.

    Used by parallel_coordinator.py to call MCP tools directly.
    Must be called before any tool function is invoked.
    """
    global _session_maker, _engine, PROJECT_DIR

    if _session_maker is not None:
        return  # Already initialized

    PROJECT_DIR = project_dir
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    _engine, _session_maker = create_database(PROJECT_DIR)
    migrate_json_to_sqlite(PROJECT_DIR, _session_maker)


def get_session():
    """Get a new database session."""
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database_direct() first.")
    return _session_maker()


@mcp.tool()
def feature_get_stats() -> str:
    """Get statistics about feature completion progress.

    Returns the number of features by status, total features,
    and completion percentage. Use this to track overall progress of the implementation.

    Returns:
        JSON with: passing, in_progress, pending, conflict, failed, total, percentage
    """
    session = get_session()
    try:
        total = session.query(Feature).count()

        # Legacy boolean counts (for backward compatibility)
        passing = session.query(Feature).filter(Feature.passes == True).count()
        in_progress = session.query(Feature).filter(Feature.in_progress == True).count()

        # New status-based counts (for parallel execution)
        pending = session.query(Feature).filter(Feature.status == FeatureStatus.PENDING).count()
        conflict = session.query(Feature).filter(Feature.status == FeatureStatus.CONFLICT).count()
        failed = session.query(Feature).filter(Feature.status == FeatureStatus.FAILED).count()

        percentage = round((passing / total) * 100, 1) if total > 0 else 0.0

        return json.dumps({
            "passing": passing,
            "in_progress": in_progress,
            "pending": pending,
            "conflict": conflict,
            "failed": failed,
            "total": total,
            "percentage": percentage
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_next() -> str:
    """Get the highest-priority pending feature to work on.

    Returns the feature with the lowest priority number that has passes=false.
    Use this at the start of each coding session to determine what to implement next.

    Returns:
        JSON with feature details (id, priority, category, name, description, steps, passes, in_progress)
        or error message if all features are passing.
    """
    session = get_session()
    try:
        feature = (
            session.query(Feature)
            .filter(Feature.passes == False)
            .order_by(Feature.priority.asc(), Feature.id.asc())
            .first()
        )

        if feature is None:
            return json.dumps({"error": "All features are passing! No more work to do."})

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_by_id(
    feature_id: Annotated[int, Field(description="The ID of the feature to retrieve", ge=1)]
) -> str:
    """Get a specific feature by its ID.

    Use this when a coordinator has already claimed a feature and the worker
    needs to retrieve its details. This is the preferred method in parallel mode.

    Args:
        feature_id: The ID of the feature to retrieve

    Returns:
        JSON with feature details or error message if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with id {feature_id} not found."})

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_for_regression(
    limit: Annotated[int, Field(default=3, ge=1, le=10, description="Maximum number of passing features to return")] = 3
) -> str:
    """Get random passing features for regression testing.

    Returns a random selection of features that are currently passing.
    Use this to verify that previously implemented features still work
    after making changes.

    Args:
        limit: Maximum number of features to return (1-10, default 3)

    Returns:
        JSON with: features (list of feature objects), count (int)
    """
    session = get_session()
    try:
        features = (
            session.query(Feature)
            .filter(Feature.passes == True)
            .order_by(func.random())
            .limit(limit)
            .all()
        )

        return json.dumps({
            "features": [f.to_dict() for f in features],
            "count": len(features)
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_mark_passing(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as passing", ge=1)],
    worker_id: Annotated[str, Field(default="", description="Worker ID that completed the feature (optional)")] = ""
) -> str:
    """Mark a feature as passing after successful implementation.

    Updates the feature's passes field to true, sets status to PASSING,
    and clears the in_progress flag and lease fields.
    Use this after you have implemented the feature and verified it works correctly.

    Args:
        feature_id: The ID of the feature to mark as passing
        worker_id: Optional worker ID that completed this feature

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Update status and passes flag
        feature.status = FeatureStatus.PASSING
        feature.passes = True
        feature.in_progress = False

        # Clear lease fields
        feature.claimed_by = None
        feature.claimed_at = None

        # Set completion audit
        feature.completed_at = datetime.utcnow()
        feature.completed_by = worker_id if worker_id else None

        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict(), indent=2)
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
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_mark_in_progress(
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as in-progress", ge=1)]
) -> str:
    """Mark a feature as in-progress. Call immediately after feature_get_next().

    This prevents other agent sessions from working on the same feature.
    Use this as soon as you retrieve a feature to work on.

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
        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict(), indent=2)
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

        return json.dumps(feature.to_dict(), indent=2)
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

    Returns:
        JSON with: created (int) - number of features created
    """
    session = get_session()
    try:
        # Get the starting priority
        max_priority_result = session.query(Feature.priority).order_by(Feature.priority.desc()).first()
        start_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        created_count = 0
        for i, feature_data in enumerate(features):
            # Validate required fields
            if not all(key in feature_data for key in ["category", "name", "description", "steps"]):
                return json.dumps({
                    "error": f"Feature at index {i} missing required fields (category, name, description, steps)"
                })

            db_feature = Feature(
                priority=start_priority + i,
                category=feature_data["category"],
                name=feature_data["name"],
                description=feature_data["description"],
                steps=feature_data["steps"],
                passes=False,
            )
            session.add(db_feature)
            created_count += 1

        session.commit()

        return json.dumps({"created": created_count}, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


# =============================================================================
# Parallel Execution Tools
# =============================================================================


@mcp.tool()
def feature_claim_next(
    worker_id: Annotated[str, Field(description="Worker ID claiming the feature", min_length=1)]
) -> str:
    """Atomically claim the next available feature for a worker.

    Uses SQLite's CTE with conditional UPDATE to ensure only one worker
    can claim each feature (race-condition safe). This should be used
    instead of feature_get_next + feature_mark_in_progress in parallel mode.

    Args:
        worker_id: Unique identifier for the worker claiming the feature

    Returns:
        JSON with claimed feature details, or {"status": "no_features_available"}
        if no pending features exist.
    """
    session = get_session()
    try:
        now = datetime.utcnow()

        # Atomic claim using CTE + conditional UPDATE with RETURNING
        # This ensures only one worker can claim each feature
        result = session.execute(text("""
            WITH next AS (
                SELECT id FROM features
                WHERE status = 'pending'
                ORDER BY priority ASC, id ASC
                LIMIT 1
            )
            UPDATE features
            SET status = 'in_progress',
                in_progress = 1,
                claimed_by = :worker_id,
                claimed_at = :now
            WHERE id IN (SELECT id FROM next)
              AND status = 'pending'
            RETURNING *
        """), {"worker_id": worker_id, "now": now})

        row = result.fetchone()
        if row is None:
            session.rollback()
            return json.dumps({"status": "no_features_available"})

        session.commit()

        # Convert row to dict
        columns = result.keys()
        feature_dict = dict(zip(columns, row))

        return json.dumps(feature_dict, indent=2, default=str)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_heartbeat(
    feature_id: Annotated[int, Field(description="The ID of the feature to heartbeat", ge=1)],
    worker_id: Annotated[str, Field(description="Worker ID that owns the feature", min_length=1)]
) -> str:
    """Extend lease on a claimed feature. Call every ~5 minutes while working.

    Updates the claimed_at timestamp to prevent stale claim recovery
    from reclaiming this feature.

    Args:
        feature_id: The ID of the feature
        worker_id: Worker ID that should own this feature

    Returns:
        JSON with {"status": "renewed"} on success,
        or {"status": "lease_lost"} if this worker no longer owns the feature.
    """
    session = get_session()
    try:
        now = datetime.utcnow()

        result = session.execute(text("""
            UPDATE features
            SET claimed_at = :now
            WHERE id = :feature_id
              AND claimed_by = :worker_id
              AND status = 'in_progress'
        """), {"feature_id": feature_id, "worker_id": worker_id, "now": now})

        if result.rowcount == 0:
            session.rollback()
            return json.dumps({"status": "lease_lost"})

        session.commit()
        return json.dumps({"status": "renewed"})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_release_claim(
    feature_id: Annotated[int, Field(description="The ID of the feature to release", ge=1)],
    worker_id: Annotated[str, Field(description="Worker ID releasing the feature", min_length=1)]
) -> str:
    """Release claim on a feature, returning it to pending status.

    Use this when abandoning a feature (e.g., agent failure, worker restart).
    Only releases if the specified worker currently owns the feature.

    Args:
        feature_id: The ID of the feature to release
        worker_id: Worker ID that should own this feature

    Returns:
        JSON with {"status": "released"} on success,
        or {"status": "not_owner"} if this worker doesn't own the feature.
    """
    session = get_session()
    try:
        result = session.execute(text("""
            UPDATE features
            SET status = 'pending',
                in_progress = 0,
                claimed_by = NULL,
                claimed_at = NULL
            WHERE id = :feature_id
              AND claimed_by = :worker_id
              AND status = 'in_progress'
        """), {"feature_id": feature_id, "worker_id": worker_id})

        if result.rowcount == 0:
            session.rollback()
            return json.dumps({"status": "not_owner"})

        session.commit()
        return json.dumps({"status": "released"})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_mark_conflict(
    feature_id: Annotated[int, Field(description="The ID of the feature with merge conflict", ge=1)],
    worker_id: Annotated[str, Field(description="Worker ID that encountered the conflict", min_length=1)]
) -> str:
    """Mark a feature as having a merge conflict.

    Use this when the feature's changes could not be merged into main.
    The feature will require manual resolution.

    Args:
        feature_id: The ID of the feature with conflict
        worker_id: Worker ID that encountered the conflict

    Returns:
        JSON with {"status": "marked_conflict"} on success,
        or {"status": "not_owner"} if this worker doesn't own the feature.
    """
    session = get_session()
    try:
        result = session.execute(text("""
            UPDATE features
            SET status = 'conflict',
                passes = 0,
                in_progress = 0,
                claimed_by = NULL,
                claimed_at = NULL
            WHERE id = :feature_id
              AND claimed_by = :worker_id
        """), {"feature_id": feature_id, "worker_id": worker_id})

        if result.rowcount == 0:
            session.rollback()
            return json.dumps({"status": "not_owner"})

        session.commit()
        return json.dumps({"status": "marked_conflict"})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_mark_failed(
    feature_id: Annotated[int, Field(description="The ID of the feature that failed", ge=1)],
    worker_id: Annotated[str, Field(description="Worker ID that encountered the failure", min_length=1)]
) -> str:
    """Mark a feature as permanently failed.

    Use this when the agent cannot complete the feature and it should
    not be retried automatically.

    Args:
        feature_id: The ID of the failed feature
        worker_id: Worker ID that encountered the failure

    Returns:
        JSON with {"status": "marked_failed"} on success,
        or {"status": "not_owner"} if this worker doesn't own the feature.
    """
    session = get_session()
    try:
        result = session.execute(text("""
            UPDATE features
            SET status = 'failed',
                passes = 0,
                in_progress = 0,
                claimed_by = NULL,
                claimed_at = NULL
            WHERE id = :feature_id
              AND claimed_by = :worker_id
        """), {"feature_id": feature_id, "worker_id": worker_id})

        if result.rowcount == 0:
            session.rollback()
            return json.dumps({"status": "not_owner"})

        session.commit()
        return json.dumps({"status": "marked_failed"})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_reclaim_stale(
    lease_timeout_minutes: Annotated[int, Field(default=30, ge=5, le=120, description="Minutes after which a claim is considered stale")] = 30
) -> str:
    """Reclaim features with expired leases.

    Used by the coordinator to recover from worker crashes.
    Features that have been in_progress for longer than lease_timeout
    without a heartbeat are returned to pending status.

    Args:
        lease_timeout_minutes: Minutes after which a claim is considered stale (5-120, default 30)

    Returns:
        JSON with {"reclaimed": count} indicating how many features were reclaimed.
    """
    session = get_session()
    try:
        # Calculate cutoff time
        cutoff = datetime.utcnow()
        # Subtract minutes manually since SQLite doesn't have great datetime math
        from datetime import timedelta
        cutoff = cutoff - timedelta(minutes=lease_timeout_minutes)

        result = session.execute(text("""
            UPDATE features
            SET status = 'pending',
                in_progress = 0,
                claimed_by = NULL,
                claimed_at = NULL
            WHERE status = 'in_progress'
              AND claimed_at < :cutoff
        """), {"cutoff": cutoff})

        reclaimed = result.rowcount
        session.commit()

        return json.dumps({"reclaimed": reclaimed})
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_is_project_complete() -> str:
    """Check if the project has no more automated work remaining.

    Returns true when there are no PENDING and no IN_PROGRESS features.
    Note: CONFLICT and FAILED features don't block completion.

    Returns:
        JSON with {"complete": bool, "pending": int, "in_progress": int}
    """
    session = get_session()
    try:
        pending = session.query(Feature).filter(Feature.status == FeatureStatus.PENDING).count()
        in_progress = session.query(Feature).filter(Feature.status == FeatureStatus.IN_PROGRESS).count()

        return json.dumps({
            "complete": pending == 0 and in_progress == 0,
            "pending": pending,
            "in_progress": in_progress
        })
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
