"""
Agent Sessions Router
=====================

REST API endpoints for querying persisted agent session logs.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.agent_session_database import (
    delete_session,
    get_session_detail,
    get_session_logs,
    get_sessions,
)
from ..utils.project_helpers import get_project_path as _get_project_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["agent-sessions"])


def _resolve_project_dir(project_name: str):
    """Resolve project directory or raise 404."""
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_dir


@router.get("/{project_name}/sessions")
async def list_sessions(
    project_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List agent sessions for a project."""
    project_dir = _resolve_project_dir(project_name)
    sessions = get_sessions(project_dir, project_name, limit=limit, offset=offset)
    return {"sessions": sessions}


@router.get("/{project_name}/sessions/{session_id}")
async def get_session(project_name: str, session_id: int):
    """Get a single agent session."""
    project_dir = _resolve_project_dir(project_name)
    session = get_session_detail(project_dir, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{project_name}/sessions/{session_id}/logs")
async def list_session_logs(
    project_name: str,
    session_id: int,
    line_type: Optional[str] = Query(None),
    feature_id: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """Get logs for an agent session with optional filters."""
    project_dir = _resolve_project_dir(project_name)
    # Verify session exists
    session = get_session_detail(project_dir, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    logs = get_session_logs(
        project_dir, session_id,
        line_type_filter=line_type,
        feature_id_filter=feature_id,
        limit=limit,
        offset=offset,
    )
    return {"logs": logs}


@router.delete("/{project_name}/sessions/{session_id}")
async def remove_session(project_name: str, session_id: int):
    """Delete an agent session and all its logs."""
    project_dir = _resolve_project_dir(project_name)
    deleted = delete_session(project_dir, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
