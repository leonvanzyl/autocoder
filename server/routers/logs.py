"""
Logs Router
===========

REST API endpoints for querying and exporting structured logs.

Endpoints:
- GET /api/logs - Query logs with filters
- GET /api/logs/timeline - Get activity timeline
- GET /api/logs/stats - Get per-agent statistics
- POST /api/logs/export - Export logs to file
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    from registry import get_project_path

    return get_project_path(project_name)


# ============================================================================
# Request/Response Models
# ============================================================================


class LogEntry(BaseModel):
    """A structured log entry."""

    id: int
    timestamp: str
    level: str
    message: str
    agent_id: Optional[str] = None
    feature_id: Optional[int] = None
    tool_name: Optional[str] = None
    duration_ms: Optional[int] = None
    extra: Optional[str] = None


class LogQueryResponse(BaseModel):
    """Response from log query."""

    logs: list[LogEntry]
    total: int
    limit: int
    offset: int


class TimelineBucket(BaseModel):
    """A timeline bucket with activity counts."""

    timestamp: str
    agents: dict[str, int]
    total: int
    errors: int


class TimelineResponse(BaseModel):
    """Response from timeline query."""

    buckets: list[TimelineBucket]
    bucket_minutes: int


class AgentStats(BaseModel):
    """Statistics for a single agent."""

    agent_id: Optional[str]
    total: int
    info_count: int
    warn_count: int
    error_count: int
    first_log: Optional[str]
    last_log: Optional[str]


class StatsResponse(BaseModel):
    """Response from stats query."""

    agents: list[AgentStats]
    total_logs: int


class ExportRequest(BaseModel):
    """Request to export logs."""

    project_name: str
    format: Literal["json", "jsonl", "csv"] = "jsonl"
    level: Optional[str] = None
    agent_id: Optional[str] = None
    feature_id: Optional[int] = None
    since_hours: Optional[int] = None


class ExportResponse(BaseModel):
    """Response from export request."""

    filename: str
    count: int
    format: str


# ============================================================================
# REST Endpoints
# ============================================================================


@router.get("/{project_name}", response_model=LogQueryResponse)
async def query_logs(
    project_name: str,
    level: Optional[str] = Query(None, description="Filter by log level (debug, info, warn, error)"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    feature_id: Optional[int] = Query(None, description="Filter by feature ID"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    search: Optional[str] = Query(None, description="Full-text search in message"),
    since_hours: Optional[int] = Query(None, description="Filter logs from last N hours"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    Query logs with filters.

    Supports filtering by level, agent, feature, tool, and full-text search.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from structured_logging import get_log_query

        query = get_log_query(project_dir)

        since = None
        if since_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        logs = query.query(
            level=level,
            agent_id=agent_id,
            feature_id=feature_id,
            tool_name=tool_name,
            search=search,
            since=since,
            limit=limit,
            offset=offset,
        )

        total = query.count(
            level=level,
            agent_id=agent_id,
            feature_id=feature_id,
            since=since,
        )

        return LogQueryResponse(
            logs=[LogEntry(**log) for log in logs],
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.exception(f"Error querying logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while querying logs")


@router.get("/{project_name}/timeline", response_model=TimelineResponse)
async def get_timeline(
    project_name: str,
    since_hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    bucket_minutes: int = Query(5, ge=1, le=60, description="Bucket size in minutes"),
):
    """
    Get activity timeline bucketed by time intervals.

    Useful for visualizing agent activity over time.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from structured_logging import get_log_query

        query = get_log_query(project_dir)

        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        buckets = query.get_timeline(since=since, bucket_minutes=bucket_minutes)

        return TimelineResponse(
            buckets=[TimelineBucket(**b) for b in buckets],
            bucket_minutes=bucket_minutes,
        )

    except Exception as e:
        logger.exception(f"Error getting timeline: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching timeline")


@router.get("/{project_name}/stats", response_model=StatsResponse)
async def get_stats(
    project_name: str,
    since_hours: Optional[int] = Query(None, description="Hours to look back"),
):
    """
    Get log statistics per agent.

    Shows total logs, info/warn/error counts, and time range per agent.
    """
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from structured_logging import get_log_query

        query = get_log_query(project_dir)

        since = None
        if since_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

        agents = query.get_agent_stats(since=since)
        total = sum(a.get("total", 0) for a in agents)

        return StatsResponse(
            agents=[AgentStats(**a) for a in agents],
            total_logs=total,
        )

    except Exception as e:
        logger.exception(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Stats query failed")


@router.post("/export", response_model=ExportResponse)
async def export_logs(request: ExportRequest):
    """
    Export logs to a downloadable file.

    Supports JSON, JSONL, and CSV formats.
    """
    project_dir = _get_project_path(request.project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from structured_logging import get_log_query

        query = get_log_query(project_dir)

        since = None
        if request.since_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=request.since_hours)

        # Create temp file for export
        suffix = f".{request.format}" if request.format != "jsonl" else ".jsonl"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"logs_{request.project_name}_{timestamp}{suffix}"

        # Export to project's .autocoder/exports directory
        export_dir = project_dir / ".autocoder" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = export_dir / filename

        count = query.export_logs(
            output_path=output_path,
            format=request.format,
            level=request.level,
            agent_id=request.agent_id,
            feature_id=request.feature_id,
            since=since,
        )

        return ExportResponse(
            filename=filename,
            count=count,
            format=request.format,
        )

    except Exception as e:
        logger.exception(f"Error exporting logs: {e}")
        raise HTTPException(status_code=500, detail="Export failed")


@router.get("/{project_name}/download/{filename}")
async def download_export(project_name: str, filename: str):
    """Download an exported log file."""
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    # Security: validate filename to prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    export_path = project_dir / ".autocoder" / "exports" / filename
    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=export_path,
        filename=filename,
        media_type="application/octet-stream",
    )
