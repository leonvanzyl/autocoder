#!/usr/bin/env python3
"""
MCP Server for Task Management (v2)
===================================

Provides tools to manage tasks in the autonomous coding system.
Supports both legacy 'features' schema and new hierarchical schema.

Hierarchy: Project → Phase → Feature → Task

Legacy Tools (backward compatible):
- feature_get_stats: Get progress statistics
- feature_get_next: Get next feature/task to implement
- feature_get_for_regression: Get random passing features/tasks for testing
- feature_mark_passing: Mark a feature/task as passing
- feature_skip: Skip a feature/task (move to end of queue)
- feature_mark_in_progress: Mark a feature/task as in-progress
- feature_clear_in_progress: Clear in-progress status
- feature_create_bulk: Create multiple features/tasks at once

New v2 Tools:
- task_get_stats: Get task progress statistics
- task_get_next: Get next task (considering dependencies)
- task_get_ready: Get all tasks ready to work on (dependencies satisfied)
- task_get_blocked: Get all blocked tasks
- task_mark_passing: Mark a task as passing
- task_set_dependencies: Set task dependencies
- task_get_dependency_graph: Get dependency graph for visualization
- phase_get_current: Get the current active phase
- phase_get_all: Get all phases for a project
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from sqlalchemy.sql.expression import func

# Add parent directory to path so we can import from api module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import (
    Feature,
    LegacyFeature,
    Phase,
    Task,
    create_database,
    get_blocked_tasks,
    get_critical_path,
    get_dependency_chain,
    get_dependency_graph,
    get_ready_tasks,
    propagate_completion,
    set_task_dependencies,
    update_blocked_status,
    validate_no_cycles,
)
from api.migration import get_schema_version, migrate_json_to_sqlite

# Configuration from environment
PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", ".")).resolve()

# Global database session maker (initialized on startup)
_session_maker = None
_engine = None
_schema_version = "legacy"  # Will be updated on startup


@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initialize database on startup, cleanup on shutdown."""
    global _session_maker, _engine, _schema_version

    # Create project directory if it doesn't exist
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database
    _engine, _session_maker = create_database(PROJECT_DIR)

    # Detect schema version
    _schema_version = get_schema_version(_engine)

    # Run JSON migration if needed (converts legacy JSON to SQLite)
    if _schema_version == "legacy":
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


def is_v2_schema() -> bool:
    """Check if using v2 schema."""
    return _schema_version == "v2"


def get_task_model():
    """Get the appropriate model for tasks based on schema version."""
    return Task if is_v2_schema() else LegacyFeature


# =============================================================================
# Legacy Tools (backward compatible - work with both schemas)
# =============================================================================


@mcp.tool()
def feature_get_stats() -> str:
    """Get statistics about feature/task completion progress.

    Returns the number of passing features, in-progress features, total features,
    and completion percentage. Use this to track overall progress of the implementation.

    Returns:
        JSON with: passing (int), in_progress (int), total (int), percentage (float)
    """
    session = get_session()
    try:
        model = get_task_model()
        total = session.query(model).count()
        passing = session.query(model).filter(model.passes == True).count()
        in_progress = session.query(model).filter(model.in_progress == True).count()
        percentage = round((passing / total) * 100, 1) if total > 0 else 0.0

        result = {
            "passing": passing,
            "in_progress": in_progress,
            "total": total,
            "percentage": percentage,
            "schema_version": _schema_version,
        }

        # Add v2-specific stats
        if is_v2_schema():
            blocked = session.query(Task).filter(Task.is_blocked == True).count()
            reviewed = session.query(Task).filter(Task.reviewed == True).count()
            result["blocked"] = blocked
            result["reviewed"] = reviewed

        return json.dumps(result, indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_next() -> str:
    """Get the highest-priority pending feature/task to work on.

    Returns the feature with the lowest priority number that has passes=false.
    In v2 schema, also skips blocked tasks.
    Use this at the start of each coding session to determine what to implement next.

    Returns:
        JSON with feature details (id, priority, category, name, description, steps, passes, in_progress)
        or error message if all features are passing.
    """
    session = get_session()
    try:
        model = get_task_model()

        query = session.query(model).filter(model.passes == False)

        # In v2, skip blocked tasks
        if is_v2_schema():
            query = query.filter(Task.is_blocked == False)

        feature = query.order_by(model.priority.asc(), model.id.asc()).first()

        if feature is None:
            # Check if there are blocked tasks
            if is_v2_schema():
                blocked_count = (
                    session.query(Task)
                    .filter(Task.passes == False, Task.is_blocked == True)
                    .count()
                )
                if blocked_count > 0:
                    return json.dumps({
                        "error": f"No ready tasks. {blocked_count} tasks are blocked by dependencies."
                    })
            return json.dumps({"error": "All features are passing! No more work to do."})

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_get_for_regression(
    limit: Annotated[
        int,
        Field(default=3, ge=1, le=10, description="Maximum number of passing features to return"),
    ] = 3
) -> str:
    """Get random passing features/tasks for regression testing.

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
        model = get_task_model()
        features = (
            session.query(model)
            .filter(model.passes == True)
            .order_by(func.random())
            .limit(limit)
            .all()
        )

        return json.dumps(
            {"features": [f.to_dict() for f in features], "count": len(features)},
            indent=2,
        )
    finally:
        session.close()


@mcp.tool()
def feature_mark_passing(
    feature_id: Annotated[
        int, Field(description="The ID of the feature to mark as passing", ge=1)
    ]
) -> str:
    """Mark a feature/task as passing after successful implementation.

    Updates the feature's passes field to true and clears the in_progress flag.
    In v2 schema, also updates completed_at and propagates to unblock dependent tasks.
    Use this after you have implemented the feature and verified it works correctly.

    Args:
        feature_id: The ID of the feature to mark as passing

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        model = get_task_model()
        feature = session.query(model).filter(model.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        feature.passes = True
        feature.in_progress = False

        # V2-specific updates
        if is_v2_schema():
            feature.completed_at = datetime.utcnow()
            session.commit()

            # Propagate completion to unblock dependent tasks
            unblocked = propagate_completion(session, feature_id)
            session.refresh(feature)

            result = feature.to_dict()
            result["unblocked_tasks"] = unblocked
            return json.dumps(result, indent=2)

        session.commit()
        session.refresh(feature)
        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_skip(
    feature_id: Annotated[
        int, Field(description="The ID of the feature to skip", ge=1)
    ]
) -> str:
    """Skip a feature/task by moving it to the end of the priority queue.

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
        model = get_task_model()
        feature = session.query(model).filter(model.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps({"error": "Cannot skip a feature that is already passing"})

        old_priority = feature.priority

        # Get max priority and set this feature to max + 1
        max_priority_result = (
            session.query(model.priority).order_by(model.priority.desc()).first()
        )
        new_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        feature.priority = new_priority
        feature.in_progress = False
        session.commit()
        session.refresh(feature)

        return json.dumps(
            {
                "id": feature.id,
                "name": feature.name,
                "old_priority": old_priority,
                "new_priority": new_priority,
                "message": f"Feature '{feature.name}' moved to end of queue",
            },
            indent=2,
        )
    finally:
        session.close()


@mcp.tool()
def feature_mark_in_progress(
    feature_id: Annotated[
        int, Field(description="The ID of the feature to mark as in-progress", ge=1)
    ]
) -> str:
    """Mark a feature/task as in-progress. Call immediately after feature_get_next().

    This prevents other agent sessions from working on the same feature.
    Use this as soon as you retrieve a feature to work on.

    Args:
        feature_id: The ID of the feature to mark as in-progress

    Returns:
        JSON with the updated feature details, or error if not found or already in-progress.
    """
    session = get_session()
    try:
        model = get_task_model()
        feature = session.query(model).filter(model.id == feature_id).first()

        if feature is None:
            return json.dumps({"error": f"Feature with ID {feature_id} not found"})

        if feature.passes:
            return json.dumps(
                {"error": f"Feature with ID {feature_id} is already passing"}
            )

        if feature.in_progress:
            return json.dumps(
                {"error": f"Feature with ID {feature_id} is already in-progress"}
            )

        # In v2, check if blocked
        if is_v2_schema() and feature.is_blocked:
            return json.dumps({
                "error": f"Feature with ID {feature_id} is blocked: {feature.blocked_reason}"
            })

        feature.in_progress = True
        session.commit()
        session.refresh(feature)

        return json.dumps(feature.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def feature_clear_in_progress(
    feature_id: Annotated[
        int,
        Field(description="The ID of the feature to clear in-progress status", ge=1),
    ]
) -> str:
    """Clear in-progress status from a feature/task.

    Use this when abandoning a feature or manually unsticking a stuck feature.
    The feature will return to the pending queue.

    Args:
        feature_id: The ID of the feature to clear in-progress status

    Returns:
        JSON with the updated feature details, or error if not found.
    """
    session = get_session()
    try:
        model = get_task_model()
        feature = session.query(model).filter(model.id == feature_id).first()

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
    features: Annotated[
        list[dict],
        Field(
            description="List of features to create, each with category, name, description, and steps"
        ),
    ]
) -> str:
    """Create multiple features/tasks in a single operation.

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
        model = get_task_model()

        # Get the starting priority
        max_priority_result = (
            session.query(model.priority).order_by(model.priority.desc()).first()
        )
        start_priority = (max_priority_result[0] + 1) if max_priority_result else 1

        created_count = 0
        for i, feature_data in enumerate(features):
            # Validate required fields
            if not all(
                key in feature_data for key in ["category", "name", "description", "steps"]
            ):
                return json.dumps({
                    "error": f"Feature at index {i} missing required fields (category, name, description, steps)"
                })

            db_feature = model(
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
# V2 Task Tools (new functionality)
# =============================================================================


@mcp.tool()
def task_get_ready() -> str:
    """Get all tasks that are ready to work on (dependencies satisfied).

    Returns tasks that are:
    - Not yet passing
    - Not in-progress
    - Not blocked by dependencies

    Ordered by priority.

    Returns:
        JSON with: tasks (list of task objects), count (int)
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_get_ready requires v2 schema"})

    session = get_session()
    try:
        tasks = (
            session.query(Task)
            .filter(
                Task.passes == False,
                Task.in_progress == False,
                Task.is_blocked == False,
            )
            .order_by(Task.priority.asc(), Task.id.asc())
            .all()
        )

        return json.dumps(
            {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}, indent=2
        )
    finally:
        session.close()


@mcp.tool()
def task_get_blocked() -> str:
    """Get all tasks that are currently blocked by dependencies.

    Returns:
        JSON with: tasks (list of task objects with blocked_reason), count (int)
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_get_blocked requires v2 schema"})

    session = get_session()
    try:
        tasks = (
            session.query(Task)
            .filter(Task.passes == False, Task.is_blocked == True)
            .order_by(Task.priority.asc())
            .all()
        )

        return json.dumps(
            {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}, indent=2
        )
    finally:
        session.close()


@mcp.tool()
def task_set_dependencies(
    task_id: Annotated[int, Field(description="The ID of the task to set dependencies for", ge=1)],
    depends_on: Annotated[list[int], Field(description="List of task IDs this task depends on")],
) -> str:
    """Set dependencies for a task.

    The task will be marked as blocked if any of its dependencies are not passing.
    When a dependency is completed, the task will automatically be unblocked.

    Args:
        task_id: The ID of the task to set dependencies for
        depends_on: List of task IDs this task depends on

    Returns:
        JSON with the updated task details.
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_set_dependencies requires v2 schema"})

    session = get_session()
    try:
        task = set_task_dependencies(session, task_id, depends_on)
        return json.dumps(task.to_dict(), indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    finally:
        session.close()


@mcp.tool()
def task_get_dependency_graph(
    feature_id: Annotated[
        int | None,
        Field(default=None, description="Optional feature ID to filter tasks"),
    ] = None
) -> str:
    """Get the dependency graph for visualization.

    Returns nodes (tasks) and edges (dependencies) that can be used
    to render a directed acyclic graph (DAG).

    Args:
        feature_id: Optional feature ID to filter tasks

    Returns:
        JSON with: nodes (list), edges (list)
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_get_dependency_graph requires v2 schema"})

    session = get_session()
    try:
        query = session.query(Task)
        if feature_id:
            query = query.filter(Task.feature_id == feature_id)
        tasks = query.all()

        nodes = []
        edges = []

        for task in tasks:
            status = "done" if task.passes else ("blocked" if task.is_blocked else "pending")
            if task.in_progress:
                status = "in_progress"

            nodes.append({
                "id": task.id,
                "name": task.name,
                "category": task.category,
                "status": status,
                "priority": task.priority,
            })

            for dep_id in task.depends_on or []:
                edges.append({"from": dep_id, "to": task.id})

        return json.dumps({"nodes": nodes, "edges": edges}, indent=2)
    finally:
        session.close()


# =============================================================================
# Phase Tools (v2 only)
# =============================================================================


@mcp.tool()
def phase_get_current() -> str:
    """Get the currently active phase.

    Returns the first phase with status 'in_progress', or the first
    'pending' phase if none are in progress.

    Returns:
        JSON with phase details, or error if no phases exist.
    """
    if not is_v2_schema():
        return json.dumps({"error": "phase_get_current requires v2 schema"})

    session = get_session()
    try:
        # First try to find an in-progress phase
        phase = (
            session.query(Phase)
            .filter(Phase.status == "in_progress")
            .order_by(Phase.order.asc())
            .first()
        )

        if phase is None:
            # Fall back to pending phase
            phase = (
                session.query(Phase)
                .filter(Phase.status == "pending")
                .order_by(Phase.order.asc())
                .first()
            )

        if phase is None:
            return json.dumps({"error": "No active phases found"})

        return json.dumps(phase.to_dict(), indent=2)
    finally:
        session.close()


@mcp.tool()
def phase_get_all() -> str:
    """Get all phases for the current project.

    Returns:
        JSON with: phases (list of phase objects), count (int)
    """
    if not is_v2_schema():
        return json.dumps({"error": "phase_get_all requires v2 schema"})

    session = get_session()
    try:
        phases = session.query(Phase).order_by(Phase.order.asc()).all()

        return json.dumps(
            {"phases": [p.to_dict() for p in phases], "count": len(phases)}, indent=2
        )
    finally:
        session.close()


@mcp.tool()
def phase_check_completion(
    phase_id: Annotated[int, Field(description="The ID of the phase to check", ge=1)]
) -> str:
    """Check if all tasks in a phase are complete.

    Returns:
        JSON with: complete (bool), total_tasks (int), passing_tasks (int),
                   remaining_tasks (list of task names)
    """
    if not is_v2_schema():
        return json.dumps({"error": "phase_check_completion requires v2 schema"})

    session = get_session()
    try:
        phase = session.query(Phase).filter(Phase.id == phase_id).first()

        if phase is None:
            return json.dumps({"error": f"Phase with ID {phase_id} not found"})

        # Get all tasks in this phase's features
        all_tasks = []
        for feature in phase.features:
            all_tasks.extend(feature.tasks)

        total = len(all_tasks)
        passing = sum(1 for t in all_tasks if t.passes)
        remaining = [t.name for t in all_tasks if not t.passes]

        return json.dumps({
            "complete": passing == total and total > 0,
            "total_tasks": total,
            "passing_tasks": passing,
            "remaining_tasks": remaining[:10],  # Limit to 10 for readability
            "remaining_count": len(remaining),
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def task_validate_dependencies(
    task_id: Annotated[int, Field(description="The task ID to validate", ge=1)],
    depends_on: Annotated[list[int], Field(description="Proposed dependency IDs to validate")],
) -> str:
    """Validate that proposed dependencies won't create a cycle.

    Use this before setting dependencies to ensure they're valid.

    Args:
        task_id: The task that would have dependencies
        depends_on: Proposed list of task IDs to depend on

    Returns:
        JSON with: valid (bool), error (str if invalid)
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_validate_dependencies requires v2 schema"})

    session = get_session()
    try:
        is_valid, error = validate_no_cycles(session, task_id, depends_on)
        return json.dumps({"valid": is_valid, "error": error}, indent=2)
    finally:
        session.close()


@mcp.tool()
def task_get_critical_path(
    feature_id: Annotated[
        int | None,
        Field(default=None, description="Optional feature ID to scope the analysis"),
    ] = None
) -> str:
    """Get the critical path - the longest chain of dependent tasks.

    The critical path determines the minimum time to complete all tasks
    since these tasks must be done sequentially.

    Args:
        feature_id: Optional feature ID to scope the analysis

    Returns:
        JSON with: tasks (ordered list), length (int)
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_get_critical_path requires v2 schema"})

    session = get_session()
    try:
        critical_tasks = get_critical_path(session, feature_id)
        return json.dumps({
            "tasks": [t.to_dict() for t in critical_tasks],
            "length": len(critical_tasks),
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def task_get_dependency_chain(
    task_id: Annotated[int, Field(description="The task ID to get chain for", ge=1)],
    direction: Annotated[
        str,
        Field(
            default="upstream",
            description="Direction: 'upstream' (dependencies) or 'downstream' (blocked tasks)"
        ),
    ] = "upstream",
) -> str:
    """Get the dependency chain for a specific task.

    - upstream: Gets all tasks this task depends on (directly and transitively)
    - downstream: Gets all tasks blocked by this task (directly and transitively)

    Args:
        task_id: The task to get the chain for
        direction: 'upstream' or 'downstream'

    Returns:
        JSON with: tasks (list), count (int)
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_get_dependency_chain requires v2 schema"})

    if direction not in ("upstream", "downstream"):
        return json.dumps({"error": "direction must be 'upstream' or 'downstream'"})

    session = get_session()
    try:
        chain = get_dependency_chain(session, task_id, direction)
        return json.dumps({
            "tasks": [t.to_dict() for t in chain],
            "count": len(chain),
            "direction": direction,
        }, indent=2)
    finally:
        session.close()


@mcp.tool()
def task_clear_dependencies(
    task_id: Annotated[int, Field(description="The task ID to clear dependencies for", ge=1)]
) -> str:
    """Clear all dependencies from a task.

    This will unblock the task if it was blocked.

    Args:
        task_id: The task to clear dependencies from

    Returns:
        JSON with the updated task details.
    """
    if not is_v2_schema():
        return json.dumps({"error": "task_clear_dependencies requires v2 schema"})

    session = get_session()
    try:
        task = set_task_dependencies(session, task_id, [])
        return json.dumps(task.to_dict(), indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    finally:
        session.close()


if __name__ == "__main__":
    mcp.run()
