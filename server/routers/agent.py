"""
Agent Router
============

API endpoints for agent control (start/stop/pause/resume).
Uses project registry for path lookups.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import AgentActionResponse, AgentStartRequest, AgentStatus
from ..services.chat_constants import ROOT_DIR
from ..services.process_manager import get_manager
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name


def _get_settings_defaults() -> tuple[bool, str, int, bool, int]:
    """Get defaults from global settings.

    Returns:
        Tuple of (yolo_mode, model, testing_agent_ratio, playwright_headless, batch_size)
    """
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import DEFAULT_MODEL, get_all_settings

    settings = get_all_settings()
    yolo_mode = (settings.get("yolo_mode") or "false").lower() == "true"
    model = settings.get("api_model") or settings.get("model", DEFAULT_MODEL)

    # Parse testing agent settings with defaults
    try:
        testing_agent_ratio = int(settings.get("testing_agent_ratio", "1"))
    except (ValueError, TypeError):
        testing_agent_ratio = 1

    playwright_headless = (settings.get("playwright_headless") or "true").lower() == "true"

    try:
        batch_size = int(settings.get("batch_size", "3"))
    except (ValueError, TypeError):
        batch_size = 3

    return yolo_mode, model, testing_agent_ratio, playwright_headless, batch_size


router = APIRouter(prefix="/api/projects/{project_name}/agent", tags=["agent"])


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
        started_at=manager.started_at.isoformat() if manager.started_at else None,
        yolo_mode=manager.yolo_mode,
        model=manager.model,
        parallel_mode=manager.parallel_mode,
        max_concurrency=manager.max_concurrency,
        testing_agent_ratio=manager.testing_agent_ratio,
    )


@router.post("/start", response_model=AgentActionResponse)
async def start_agent(
    project_name: str,
    request: AgentStartRequest = AgentStartRequest(),
):
    """Start the agent for a project."""
    manager = get_project_manager(project_name)

    # Get defaults from global settings if not provided in request
    default_yolo, default_model, default_testing_ratio, playwright_headless, default_batch_size = _get_settings_defaults()

    yolo_mode = request.yolo_mode if request.yolo_mode is not None else default_yolo
    model = request.model if request.model else default_model
    max_concurrency = request.max_concurrency or 1
    testing_agent_ratio = request.testing_agent_ratio if request.testing_agent_ratio is not None else default_testing_ratio

    batch_size = default_batch_size

    success, message = await manager.start(
        yolo_mode=yolo_mode,
        model=model,
        max_concurrency=max_concurrency,
        testing_agent_ratio=testing_agent_ratio,
        playwright_headless=playwright_headless,
        batch_size=batch_size,
    )

    # Notify scheduler of manual start (to prevent auto-stop during scheduled window)
    if success:
        from ..services.scheduler_service import get_scheduler
        project_dir = _get_project_path(project_name)
        if project_dir:
            get_scheduler().notify_manual_start(project_name, project_dir)

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

    # Notify scheduler of manual stop (to prevent auto-start during scheduled window)
    if success:
        from ..services.scheduler_service import get_scheduler
        project_dir = _get_project_path(project_name)
        if project_dir:
            get_scheduler().notify_manual_stop(project_name, project_dir)

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


@router.post("/graceful-pause", response_model=AgentActionResponse)
async def graceful_pause_agent(project_name: str):
    """Request a graceful pause (drain mode) - finish current work then pause."""
    manager = get_project_manager(project_name)

    success, message = await manager.graceful_pause()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/graceful-resume", response_model=AgentActionResponse)
async def graceful_resume_agent(project_name: str):
    """Resume from a graceful pause."""
    manager = get_project_manager(project_name)

    success, message = await manager.graceful_resume()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )
