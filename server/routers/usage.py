"""
Usage Router
============

API endpoints for usage tracking and analytics.
"""

import sys
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

# Add parent directory to path
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from registry import get_project_path
from usage_tracking import get_usage_tracker

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _get_project_path(project_name: str) -> Path:
    """Get project path or raise 404."""
    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    return project_path


@router.get("/{project_name}/summary")
async def get_usage_summary(
    project_name: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
):
    """
    Get usage summary for a project.

    Args:
        project_name: The project name
        days: Number of days to include (default 30, max 365)

    Returns:
        Usage summary with totals, breakdowns by model and agent type
    """
    project_path = _get_project_path(project_name)
    tracker = get_usage_tracker(project_path)
    return tracker.get_project_usage_summary(project_name, days=days)


@router.get("/{project_name}/daily")
async def get_daily_usage(
    project_name: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
):
    """
    Get daily usage breakdown for a project.

    Args:
        project_name: The project name
        days: Number of days to include (default 30, max 365)

    Returns:
        List of daily usage records
    """
    project_path = _get_project_path(project_name)
    tracker = get_usage_tracker(project_path)
    return tracker.get_daily_usage(project_name, days=days)


@router.get("/{project_name}/recent")
async def get_recent_usage(
    project_name: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    """
    Get recent usage records for a project.

    Args:
        project_name: The project name
        limit: Maximum records to return (default 50, max 500)

    Returns:
        List of recent usage records
    """
    project_path = _get_project_path(project_name)
    tracker = get_usage_tracker(project_path)
    return tracker.get_recent_usage(project_name, limit=limit)


@router.get("/{project_name}/attempts")
async def get_feature_attempts(
    project_name: str,
    feature_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """
    Get feature attempt history for a project.

    Args:
        project_name: The project name
        feature_id: Optional filter by feature ID
        limit: Maximum records to return (default 100, max 500)

    Returns:
        List of feature attempt records
    """
    project_path = _get_project_path(project_name)
    tracker = get_usage_tracker(project_path)
    return tracker.get_feature_attempts(project_name, feature_id=feature_id, limit=limit)


@router.get("/{project_name}/cost-estimate")
async def get_cost_estimate(
    project_name: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
):
    """
    Get cost estimates and projections for a project.

    Args:
        project_name: The project name
        days: Number of days to analyze (default 30)

    Returns:
        Cost analysis with historical data and projections
    """
    project_path = _get_project_path(project_name)
    tracker = get_usage_tracker(project_path)

    summary = tracker.get_project_usage_summary(project_name, days=days)
    daily = tracker.get_daily_usage(project_name, days=days)

    # Calculate averages and projections
    total_cost = summary["totals"]["cost"]
    total_days = len(daily) if daily else 1

    avg_daily_cost = total_cost / total_days if total_days > 0 else 0
    projected_monthly = avg_daily_cost * 30

    return {
        "projectName": project_name,
        "periodDays": days,
        "totalCost": total_cost,
        "avgDailyCost": round(avg_daily_cost, 4),
        "projectedMonthlyCost": round(projected_monthly, 2),
        "costByModel": summary["byModel"],
        "costByAgentType": summary["byAgentType"],
        "dailyTrend": daily[-7:] if len(daily) >= 7 else daily,  # Last 7 days
    }
