#!/usr/bin/env python3
"""
MCP Server for Feature Management
==================================

Provides tools to manage features in the autonomous coding system.

This is the UNIFIED database version - uses agent_system.db which is shared
between the Initializer agent, Orchestrator, and parallel workers.

Tools:
- feature_get_stats: Get progress statistics
- feature_get_next: Get next feature to implement (legacy; not atomic)
- feature_claim_next: Atomically claim next pending feature (recommended)
- feature_get_all: Get all features with details
- feature_get_by_id: Get a specific feature
- feature_get_for_regression: Get random passing features for testing
- feature_mark_passing: Mark a feature as passing
- feature_mark_in_progress: Mark a feature as in-progress
- feature_skip: Skip a feature (move to end of queue)
- feature_clear_in_progress: Clear in-progress status (reset to pending)
- feature_create_bulk: Create multiple features at once
- feature_update: Update an existing feature
- feature_delete: Delete a feature
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# Use the UNIFIED database (shared with Orchestrator)
from autocoder.core.database import get_database

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

# Global database instance
_db = None


def get_db():
    """Get the unified database instance."""
    global _db
    if _db is None:
        _db = get_database(str(PROJECT_DIR))
    return _db


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


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup."""
    global _db

    # Create project directory if it doesn't exist
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize the unified database
    _db = get_database(str(PROJECT_DIR))

    yield

    # Cleanup (if needed)


# Initialize the MCP server
mcp = FastMCP("features", lifespan=server_lifespan)


@mcp.tool()
def feature_get_stats() -> str:
    """Get statistics about feature completion progress.

    Returns the number of passing features, in-progress features, total features,
    and completion percentage. Use this to track overall progress of the implementation.

    Returns:
        JSON with: passing (int), in_progress (int), total (int), percentage (float)
    """
    db = get_db()
    stats = db.get_stats()
    progress = db.get_progress()

    result = {
        "passing": stats["features"]["completed"],
        "in_progress": stats["features"]["in_progress"],
        "pending": stats["features"]["pending"],
        "total": stats["features"]["total"],
        "percentage": progress["percentage"]
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def feature_get_next() -> str:
    """Get the next pending feature to implement (non-atomic).

    Prefer `feature_claim_next` for concurrent/parallel execution.

    Returns:
        JSON with feature details (id, name, description, category, steps, priority)
    """
    db = get_db()
    feature = db.get_next_pending_feature()

    if not feature:
        return json.dumps({"error": "No pending features available"}, indent=2)

    # Parse steps from JSON if present
    if feature.get("steps"):
        try:
            feature["steps"] = json.loads(feature["steps"])
        except:
            feature["steps"] = []

    return json.dumps(feature, indent=2)


@mcp.tool()
def feature_claim_next(agent_id: str) -> str:
    """
    Atomically claim the next pending feature and return it.

    Args:
        agent_id: Unique identifier for the caller (use a stable value per worker)

    Returns:
        JSON with feature details, or an error if none are available.
    """
    db = get_db()
    feature = db.claim_next_pending_feature(agent_id)

    if not feature:
        return json.dumps({"error": "No pending features available"}, indent=2)

    if feature.get("steps"):
        try:
            feature["steps"] = json.loads(feature["steps"])
        except Exception:
            feature["steps"] = []

    return json.dumps(feature, indent=2)


@mcp.tool()
def feature_get_for_regression(limit: int = 3) -> str:
    """Get random passing features for regression testing.

    Args:
        limit: Maximum number of passing features to return (default: 3, max: 10)

    Returns:
        JSON with list of passing features
    """
    db = get_db()
    features = db.get_passing_features_for_regression(limit=limit)

    # Parse steps from JSON for each feature
    for feature in features:
        if feature.get("steps"):
            try:
                feature["steps"] = json.loads(feature["steps"])
            except:
                feature["steps"] = []

    return json.dumps(features, indent=2)


@mcp.tool()
def feature_get_all() -> str:
    """Get all features with full details.

    Returns:
        JSON with list of all features (including status, priority, etc.)
    """
    db = get_db()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM features ORDER BY priority DESC, id ASC")
        features = [dict(row) for row in cursor.fetchall()]

    # Parse steps from JSON for each feature
    for feature in features:
        if feature.get("steps"):
            try:
                feature["steps"] = json.loads(feature["steps"])
            except:
                feature["steps"] = []

    return json.dumps(features, indent=2)


@mcp.tool()
def feature_get_by_id(feature_id: int) -> str:
    """Get a specific feature by ID.

    Args:
        feature_id: The ID of the feature to retrieve

    Returns:
        JSON with feature details
    """
    db = get_db()
    feature = db.get_feature(feature_id)

    if not feature:
        return json.dumps({"error": f"Feature {feature_id} not found"}, indent=2)

    # Parse steps from JSON if present
    if feature.get("steps"):
        try:
            feature["steps"] = json.loads(feature["steps"])
        except:
            feature["steps"] = []

    return json.dumps(feature, indent=2)


@mcp.tool()
def feature_mark_passing(feature_id: int) -> str:
    """Mark a feature as passing (complete) or submit for deterministic verification.

    Args:
        feature_id: The ID of the feature to mark as passing

    Returns:
        JSON with success status
    """
    db = get_db()
    require_gatekeeper = os.environ.get("AUTOCODER_REQUIRE_GATEKEEPER", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if require_gatekeeper:
        success = db.mark_feature_ready_for_verification(feature_id)
        message = (
            "Feature submitted for gatekeeper verification"
            if success
            else "Failed to submit feature for gatekeeper verification"
        )
    else:
        success = db.mark_feature_passing(feature_id)
        message = "Feature marked as passing" if success else "Failed to mark feature as passing"

    result = {
        "success": success,
        "feature_id": feature_id,
        "message": message,
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def feature_mark_in_progress(feature_id: int) -> str:
    """Mark a feature as in-progress.

    Args:
        feature_id: The ID of the feature to mark as in-progress

    Returns:
        JSON with success status
    """
    db = get_db()
    success = db.update_feature_status(feature_id, "in_progress")

    result = {
        "success": success,
        "feature_id": feature_id,
        "message": "Feature marked as in-progress" if success else "Failed to mark feature as in-progress"
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def feature_skip(feature_id: int) -> str:
    """Skip a feature (reset to pending for later implementation).

    Args:
        feature_id: The ID of the feature to skip

    Returns:
        JSON with success status
    """
    db = get_db()
    success = db.update_feature_status(feature_id, "pending")

    result = {
        "success": success,
        "feature_id": feature_id,
        "message": "Feature reset to pending" if success else "Failed to skip feature"
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def feature_clear_in_progress(feature_id: int) -> str:
    """Clear a feature from in-progress back to pending (no attempt increment)."""
    db = get_db()
    success = db.clear_feature_in_progress(feature_id)
    return json.dumps(
        {
            "success": success,
            "feature_id": feature_id,
            "message": "Feature cleared to pending" if success else "Failed to clear feature",
        },
        indent=2,
    )


@mcp.tool()
def feature_create_bulk(features: list[dict]) -> str:
    """Create multiple features at once.

    This is used by the Initializer agent to populate the feature database.

    Args:
        features: List of feature dicts with keys: category, name, description, steps

    Returns:
        JSON with number of features created
    """
    db = get_db()
    count = db.create_features_bulk(features)

    result = {
        "success": True,
        "created": count,
        "message": f"Created {count} features"
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def feature_update(
    feature_id: int,
    category: str | None = None,
    name: str | None = None,
    description: str | None = None,
    steps: list[str] | None = None,
    priority: int | None = None
) -> str:
    """Update an existing feature.

    Args:
        feature_id: The ID of the feature to update
        category: New category (optional)
        name: New name (optional)
        description: New description (optional)
        steps: New implementation steps (optional)
        priority: New priority (optional)

    Returns:
        JSON with success status
    """
    db = get_db()

    # Build update query dynamically based on provided fields
    updates = []
    params = []

    if category is not None:
        updates.append("category = ?")
        params.append(category)

    if name is not None:
        updates.append("name = ?")
        params.append(name)

    if description is not None:
        updates.append("description = ?")
        params.append(description)

    if steps is not None:
        updates.append("steps = ?")
        params.append(json.dumps(steps))

    if priority is not None:
        updates.append("priority = ?")
        params.append(priority)

    if not updates:
        return json.dumps({"error": "No fields to update"}, indent=2)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(feature_id)

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE features
            SET {', '.join(updates)}
            WHERE id = ?
        """, params)
        conn.commit()
        success = cursor.rowcount > 0

    result = {
        "success": success,
        "feature_id": feature_id,
        "message": "Feature updated successfully" if success else "Failed to update feature"
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def feature_delete(feature_id: int) -> str:
    """Delete a feature from the database.

    Args:
        feature_id: The ID of the feature to delete

    Returns:
        JSON with success status
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM features WHERE id = ?", (feature_id,))
        conn.commit()
        success = cursor.rowcount > 0

    result = {
        "success": success,
        "feature_id": feature_id,
        "message": "Feature deleted successfully" if success else "Failed to delete feature"
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
