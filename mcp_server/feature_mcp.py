#!/usr/bin/env python3
"""
MCP Server for Feature and Context Management
==============================================

Provides tools to manage features and context documentation
in the autonomous coding system.

Feature Tools:
- feature_get_stats: Get progress statistics
- feature_get_next: Get next feature to implement
- feature_get_for_regression: Get random passing features for testing
- feature_mark_passing: Mark a feature as passing
- feature_skip: Skip a feature (move to end of queue)
- feature_mark_in_progress: Mark a feature as in-progress
- feature_clear_in_progress: Clear in-progress status
- feature_create_bulk: Create multiple features at once

Context Tools (for imported/analyzed projects):
- context_list: List available context documentation files
- context_read: Read a specific context file
- context_read_all: Read all context files combined
- context_write: Write/update a context documentation file
- context_get_progress: Get analysis progress status
- context_update_index: Update status in the context index
"""

import json
import os
import re
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP


def _validate_context_name(name: str) -> str | None:
    """Validate context file name to prevent path traversal.

    Returns None if valid, error message if invalid.
    """
    if not name:
        return "Context file name cannot be empty"
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return "Invalid context file name. Use only alphanumeric characters, underscores, and hyphens."
    if '..' in name or '/' in name or '\\' in name:
        return "Invalid context file name. Path traversal not allowed."
    return None


from pydantic import BaseModel, Field
from sqlalchemy.sql.expression import func

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import Feature, create_database
from api.migration import migrate_json_to_sqlite
from prompts import (
    get_context_dir,
    ensure_context_dir,
    list_context_files,
    load_context_file,
    load_all_context,
    get_analysis_progress,
)

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


# =============================================================================
# Context Management Tools (for imported/analyzed projects)
# =============================================================================

@mcp.tool()
def context_list() -> str:
    """List all available context documentation files.

    Returns the list of context files in the prompts/context/ directory.
    These files contain analysis documentation for imported projects.

    Returns:
        JSON with: files (list of {name, path, size_kb}), total_files (int)
    """
    try:
        files = list_context_files(PROJECT_DIR)
        result = []
        for name, path in files:
            try:
                size_kb = round(path.stat().st_size / 1024, 1)
            except OSError:
                size_kb = 0
            result.append({
                "name": name,
                "path": str(path),
                "size_kb": size_kb
            })

        return json.dumps({
            "files": result,
            "total_files": len(result)
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def context_read(
    name: Annotated[str, Field(description="Name of the context file to read (without .md extension)")]
) -> str:
    """Read a specific context documentation file.

    Use this to load detailed analysis about a specific area of the codebase.
    Common context file names: _index, architecture, database_schema,
    api_endpoints, components, services, configuration.

    Args:
        name: The name of the context file (without .md extension)

    Returns:
        The content of the context file, or error if not found.
    """
    try:
        # Validate name to prevent path traversal
        validation_error = _validate_context_name(name)
        if validation_error:
            return json.dumps({"success": False, "error": validation_error})

        content = load_context_file(PROJECT_DIR, name)
        if content is None:
            return json.dumps({"success": False, "error": f"Context file '{name}' not found"})
        return json.dumps({"success": True, "content": content}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def context_read_all(
    max_chars: Annotated[int, Field(default=50000, ge=1000, le=100000, description="Maximum characters to return")] = 50000
) -> str:
    """Read all context documentation combined.

    Loads all context files in priority order (index, architecture, database,
    API, components, services) up to the character limit. Use this to get
    a full overview of the analyzed codebase.

    Args:
        max_chars: Maximum characters to return (default 50000)

    Returns:
        Combined context documentation with section headers.
    """
    try:
        content = load_all_context(PROJECT_DIR, max_chars)
        if not content:
            return json.dumps({"success": False, "error": "No context documentation found. Run analyzer first."})
        return json.dumps({"success": True, "content": content}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def context_write(
    name: Annotated[str, Field(description="Name of the context file (without .md extension)")],
    content: Annotated[str, Field(description="The markdown content to write")]
) -> str:
    """Write or update a context documentation file.

    Use this after analyzing a specific area of the codebase to save
    the documentation for future sessions.

    Common context file names:
    - _index: Overview and progress tracking
    - architecture: System architecture, patterns, code organization
    - database_schema: Tables, models, relationships
    - api_endpoints: Routes, methods, request/response formats
    - components: UI components, hierarchy, props
    - services: Business logic, external integrations
    - configuration: Config files, environment variables

    Args:
        name: The name of the context file (without .md extension)
        content: The markdown content to write

    Returns:
        JSON with: success (bool), path (str), message (str)
    """
    try:
        # Validate name to prevent path traversal
        validation_error = _validate_context_name(name)
        if validation_error:
            return json.dumps({"success": False, "error": validation_error})

        # Ensure context directory exists
        context_dir = ensure_context_dir(PROJECT_DIR)
        file_path = context_dir / f"{name}.md"

        # Additional safety: verify resolved path is within context_dir
        if not file_path.resolve().is_relative_to(context_dir.resolve()):
            return json.dumps({"success": False, "error": "Invalid file path"})

        # Write the content
        file_path.write_text(content, encoding="utf-8")

        return json.dumps({
            "success": True,
            "path": str(file_path),
            "message": f"Context file '{name}.md' written successfully"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def context_get_progress() -> str:
    """Get the analysis progress for the project.

    Returns which areas have been analyzed and which are still pending.
    Use this to understand what analysis work remains.

    Returns:
        JSON with: analyzed_areas (list), pending_areas (list),
                   total_files (int), is_complete (bool)
    """
    try:
        progress = get_analysis_progress(PROJECT_DIR)
        return json.dumps(progress, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def context_update_index(
    status_updates: Annotated[dict, Field(description="Dictionary mapping area names to their status (Pending/Complete/In Progress)")]
) -> str:
    """Update the analysis status in the context index file.

    Use this to mark analysis areas as complete or in-progress.
    The index file tracks overall analysis progress.

    Args:
        status_updates: Dict mapping area names to status strings.
                       Example: {"architecture": "Complete", "database_schema": "In Progress"}

    Returns:
        JSON with: success (bool), updated_areas (list), message (str)
    """
    # Valid status values for consistency
    valid_statuses = {"Pending", "Complete", "In Progress"}

    try:
        # Validate status values before processing
        for area, status in status_updates.items():
            if status not in valid_statuses:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid status '{status}' for area '{area}'. Must be one of: {', '.join(sorted(valid_statuses))}"
                })

        context_dir = ensure_context_dir(PROJECT_DIR)
        index_path = context_dir / "_index.md"

        if not index_path.exists():
            return json.dumps({
                "success": False,
                "error": "Index file does not exist. Create it first using context_write."
            })

        content = index_path.read_text(encoding="utf-8")
        updated_areas = []

        # Update status entries in the markdown table
        for area, status in status_updates.items():
            # Look for table rows like "| Architecture | Pending | architecture.md |"
            # Capture the area and filename columns, only replace the status
            # Use case-sensitive matching for precise table row targeting
            # Match only valid status values explicitly to avoid false matches
            status_pattern = r"(?:Pending|Complete|In Progress)"
            pattern = rf"(\|\s*{re.escape(area)}\s*\|)\s*{status_pattern}\s*(\|[^|\n]*\|)"
            replacement = rf"\g<1> {status} \2"
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0:
                content = new_content
                updated_areas.append(area)

        # Add last updated timestamp if there's a placeholder
        content = content.replace(
            "**Status:** Initial scan complete",
            f"**Status:** Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        # Write back
        index_path.write_text(content, encoding="utf-8")

        # Warn if no updates occurred
        if len(updated_areas) == 0:
            return json.dumps({
                "success": False,
                "updated_areas": [],
                "error": "No areas were updated. Check that area names match the index table exactly."
            }, indent=2)

        return json.dumps({
            "success": True,
            "updated_areas": updated_areas,
            "message": f"Updated {len(updated_areas)} area(s) in index"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


if __name__ == "__main__":
    mcp.run()
