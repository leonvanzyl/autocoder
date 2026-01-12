"""
Agent Router
============

API endpoints for agent control (start/stop/pause/resume).
Uses project registry for path lookups.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import AgentStatus, AgentActionResponse, AgentStartRequest
from ..services.process_manager import get_manager


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    from autocoder.agent.registry import get_project_path

    return get_project_path(project_name)


router = APIRouter(prefix="/api/projects/{project_name}/agent", tags=["agent"])

# Root directory for process manager
ROOT_DIR = Path(__file__).parent.parent.parent


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


def get_project_manager(project_name: str):
    """Get the process manager for a project."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    return get_manager(project_name, project_dir, ROOT_DIR)


@router.get("/status", response_model=AgentStatus)
async def get_agent_status(project_name: str):
    """Get the current status of the agent for a project."""
    manager = get_project_manager(project_name)

    # Run healthcheck to detect crashed processes
    await manager.healthcheck()

    return AgentStatus(
        status=manager.status,
        pid=manager.pid,
        started_at=manager.started_at,
        yolo_mode=manager.yolo_mode,
        parallel_mode=manager.parallel_mode,
        parallel_count=manager.parallel_count if manager.parallel_mode else None,
        model_preset=manager.model_preset if manager.parallel_mode else None,
    )


@router.post("/start", response_model=AgentActionResponse)
async def start_agent(
    project_name: str,
    request: AgentStartRequest = AgentStartRequest(),
):
    """Start the agent for a project."""
    manager = get_project_manager(project_name)

    # Parallel and YOLO modes are mutually exclusive
    if request.parallel_mode and request.yolo_mode:
        return AgentActionResponse(
            success=False,
            status=manager.status,
            message="Cannot enable both parallel mode and YOLO mode",
        )

    success, message = await manager.start(
        yolo_mode=request.yolo_mode,
        parallel_mode=request.parallel_mode,
        parallel_count=request.parallel_count,
        model_preset=request.model_preset,
    )

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/stop", response_model=AgentActionResponse)
async def stop_agent(project_name: str):
    """Stop the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.stop()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/pause", response_model=AgentActionResponse)
async def pause_agent(project_name: str):
    """Pause the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.pause()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/resume", response_model=AgentActionResponse)
async def resume_agent(project_name: str):
    """Resume a paused agent."""
    manager = get_project_manager(project_name)

    success, message = await manager.resume()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )
