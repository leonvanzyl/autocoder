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
- feature_create: Create a single feature
- feature_update: Update a feature's editable fields
"""

import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from sqlalchemy.sql.expression import func

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, create_database
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
        # Use lock to prevent race condition in priority assignment
        with _priority_lock:
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
            )
            session.add(db_feature)
            session.commit()

        session.refresh(db_feature)

        return json.dumps({
            "success": True,
            "message": f"Created feature: {name}",
            "feature": db_feature.to_dict()
        }, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


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

        feature_info = feature.to_dict()
        was_passing = feature.passes

        session.delete(feature)
        session.commit()

        result = {
            "success": True,
            "message": f"Deleted feature: {feature_info['name']}",
            "deleted_feature": feature_info,
        }

        # Add hint for completed features
        if was_passing:
            result["note"] = "This feature was completed. The implemented code remains in the codebase. If you want the code removed, create a new feature describing what to remove."

        return json.dumps(result, indent=2)
    except Exception as e:
        session.rollback()
        return json.dumps({"error": str(e)})
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
