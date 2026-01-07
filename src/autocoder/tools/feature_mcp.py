#!/usr/bin/env python3
"""
MCP Server for Feature Management
==================================

Provides tools to manage features in the autonomous coding system,
replacing the previous FastAPI-based REST API.

Tools:
- feature_get_stats: Get progress statistics
- feature_get_next: Get next feature to implement
- feature_get_all: Get all features with details
- feature_get_by_id: Get a specific feature
- feature_get_for_regression: Get random passing features for testing
- feature_mark_passing: Mark a feature as passing
- feature_skip: Skip a feature (move to end of queue)
- feature_mark_in_progress: Mark a feature as in-progress
- feature_clear_in_progress: Clear in-progress status
- feature_create_bulk: Create multiple features at once
- feature_update: Update an existing feature
- feature_delete: Delete a feature
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy.sql.expression import func

# Add parent directory to path so we can import from api module
from autocoder.api.database import Feature, create_database
from autocoder.api.migration import migrate_json_to_sqlite

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


class UpdateFeatureInput(BaseModel):
    """Input for updating a feature."""
    feature_id: int = Field(..., ge=1, description="The ID of the feature to update")
    category: str | None = Field(None, min_length=1, max_length=100, description="New category")
    name: str | None = Field(None, min_length=1, max_length=255, description="New name")
    description: str | None = Field(None, min_length=1, description="New description")
    steps: list[str] | None = Field(None, min_length=1, description="New implementation steps")
    priority: int | None = Field(None, ge=0, description="New priority (lower = higher priority)")


class DeleteFeatureInput(BaseModel):
    """Input for deleting a feature."""
    feature_id: int = Field(..., ge=1, description="The ID of the feature to delete")


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
    session = get_session()
    try:
        total = session.query(Feature).count()
        passing = session.query(Feature).filter(Feature.passes == True).count()
        in_progress = session.query(Feature).filter(Feature.in_progress == True).count()
        percentage = round((passing / total) * 100, 1) if total > 0 else 0.0

        return json.dumps({
            "passing": passing,
            "in_progress": in_progress,
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
    feature_id: Annotated[int, Field(description="The ID of the feature to mark as passing", ge=1)]
) -> str:
    """Mark a feature as passing after successful implementation.

    Updates the feature's passes field to true and clears the in_progress flag.
    Use this after you have implemented the feature and verified it works correctly.

    Args:
        feature_id: The ID of the feature to mark as passing

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.passes = True
        feature.in_progress = False
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


@mcp.tool()
def feature_get_all() -> str:
    """Get all features in the database with full details.

    Returns a complete list of all features ordered by priority.
    Use this to see the entire feature list and understand what needs to be implemented.

    Returns:
        JSON with: features (list of all feature objects with id, priority, category, name, description, steps, passes, in_progress)
    """
    session = get_session()
    try:
        features = (
            session.query(Feature)
            .order_by(Feature.priority.asc(), Feature.id.asc())
            .all()
        )

        return json.dumps({
            "features": [f.to_dict() for f in features],
            "count": len(features)
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_by_id(
    feature_id: Annotated[int, Field(description="The ID of the feature to retrieve", ge=1)]
) -> str:
    """Get detailed information about a specific feature.

    Use this to see the full details of a particular feature,
    including its description and implementation steps.

    Args:
        feature_id: The ID of the feature to retrieve

    Returns:
        JSON with the feature details (id, priority, category, name, description, steps, passes, in_progress)
        or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_update(
    feature_id: Annotated[int, Field(description="The ID of the feature to update", ge=1)],
    category: Annotated[str | None, Field(default=None, description="New category")] = None,
    name: Annotated[str | None, Field(default=None, description="New name")] = None,
    description: Annotated[str | None, Field(default=None, description="New description")] = None,
    steps: Annotated[list[str] | None, Field(default=None, description="New implementation steps")] = None,
    priority: Annotated[int | None, Field(default=None, ge=0, description="New priority (lower=higher priority)")] = None,
) -> str:
    """Update an existing feature with new information.

    Use this to modify a feature's details, for example when requirements change
    or you need to adjust the implementation approach.

    Only provide the fields you want to change - other fields will remain unchanged.

    Args:
        feature_id: The ID of the feature to update
        category: New category (optional)
        name: New name (optional)
        description: New description (optional)
        steps: New implementation steps (optional)
        priority: New priority number (optional)

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Update only provided fields
        if category is not None:
            feature.category = category
        if name is not None:
            feature.name = name
        if description is not None:
            feature.description = description
        if steps is not None:
            feature.steps = steps
        if priority is not None:
            feature.priority = priority

        session.commit()
        session.refresh(feature)

        return json.dumps({
            "success": True,
            "feature": feature.to_dict()
        }, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_delete(
    feature_id: Annotated[int, Field(description="The ID of the feature to delete", ge=1)]
) -> str:
    """Delete a feature from the database.

    Use this to remove a feature that is no longer needed.
    This cannot be undone - the feature will be permanently deleted.

    WARNING: If a feature is already in progress or passing, you should
    generally skip it rather than delete it, to preserve implementation history.

    Args:
        feature_id: The ID of the feature to delete

    Returns:
        JSON with success confirmation and deleted feature details, or error if not found.
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature_details = feature.to_dict()

        session.delete(feature)
        session.commit()

        return json.dumps({
            "success": True,
            "deleted": feature_details,
            "message": f"Feature '{feature.name}' has been deleted"
        }, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_claim_batch(
    count: Annotated[int, Field(default=1, ge=1, le=10, description="Number of features to claim")],
    agent_id: Annotated[str, Field(default="", description="Agent ID claiming these features")]
) -> str:
    """Atomically claim multiple pending features for parallel processing.

    This is the CORE tool for parallel agent execution. Multiple agents can call
    this simultaneously, and each will receive different features without conflicts.

    Uses database row-level locking (SELECT ... FOR UPDATE) to prevent race conditions.
    Only claims features that are NOT already in_progress and NOT passing.

    Args:
        count: How many features to claim (1-10, default 1)
        agent_id: Optional agent ID to track which agent claimed which feature

    Returns:
        JSON with: features (list of claimed feature objects), count (int)
        Returns empty list if no pending features available.
    """
    session = get_session()
    try:
        # Use with_for_update() to lock rows and prevent race conditions
        features = (
            session.query(Feature)
            .filter(Feature.passes == False)
            .filter(Feature.in_progress == False)
            .order_by(Feature.priority.asc(), Feature.id.asc())
            .limit(count)
            .with_for_update()  # CRITICAL: Row-level locking for atomicity
            .all()
        )

        # Mark all claimed features as in_progress
        for feature in features:
            feature.in_progress = True

        session.commit()

        return json.dumps({
            "features": [f.to_dict() for f in features],
            "count": len(features),
            "agent_id": agent_id
        }, indent=2)

    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_release(
    feature_id: Annotated[int, Field(description="The ID of the feature to release", ge=1)],
    status: Annotated[str, Field(description="New status: 'passing', 'failed', or 'pending'")] = "pending",
    notes: Annotated[str, Field(default="", description="Optional notes about implementation")] = ""
) -> str:
    """Release a claimed feature with completion status.

    Called when an agent finishes working on a feature (success or failure).
    Updates the feature status and clears the in_progress flag so other agents can work on it.

    Args:
        feature_id: The ID of the feature to release
        status: New status - "passing" if successful, "failed" if needs retry, "pending" to return to queue
        notes: Optional notes about implementation results or failure reasons

    Returns:
        JSON with the updated feature details
    """
    session = get_session()
    try:
        feature = session.query(Feature).filter(Feature.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        # Update status based on result
        if status == "passing":
            feature.passes = True
            feature.in_progress = False
        elif status == "failed":
            feature.in_progress = False  # Return to queue with failure note
        elif status == "pending":
            feature.in_progress = False  # Return to queue (retry later)
        else:
            return json.dumps({"error": f"Invalid status: {status}. Must be 'passing', 'failed', or 'pending'"})

        # Add notes to description for tracking
        if notes:
            feature.notes = notes

        session.commit()
        session.refresh(feature)

        return json.dumps({
            "success": True,
            "feature": feature.to_dict(),
            "message": f"Feature {feature_id} released with status: {status}"
        }, indent=2)

    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def feature_get_claimed(
    agent_id: Annotated[str, Field(default="", description="Filter by agent ID (optional)")]
) -> str:
    """Get all features currently claimed (in_progress).

    Use this to see what features are currently being worked on by agents.
    Can filter by agent_id to see specific agent's work.

    Args:
        agent_id: Optional agent ID to filter results

    Returns:
        JSON with: features (list of in_progress feature objects), count (int)
    """
    session = get_session()
    try:
        query = session.query(Feature).filter(Feature.in_progress == True)

        features = query.order_by(Feature.priority.asc()).all()

        return json.dumps({
            "features": [f.to_dict() for f in features],
            "count": len(features)
        }, indent=2)
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
