"""
Agent Router
============

API endpoints for agent control (start/stop/pause/resume).
Uses project registry for path lookups.

Includes auto-resume functionality that automatically restarts
crashed agents when the autoResume setting is enabled.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import AgentActionResponse, AgentStartRequest, AgentStatus
from ..services.auto_resume_service import (
    handle_agent_crash,
    register_auto_resume,
    unregister_auto_resume,
)
from ..services.process_manager import get_manager


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def _get_settings_defaults() -> tuple[bool, str, int]:
    """Get defaults from global settings.

    Returns:
        Tuple of (yolo_mode, model, testing_agent_ratio)
    """
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import DEFAULT_MODEL, get_all_settings

    settings = get_all_settings()
    yolo_mode = (settings.get("yolo_mode") or "false").lower() == "true"
    model = settings.get("model", DEFAULT_MODEL)

    # Parse testing agent settings with defaults
    try:
        testing_agent_ratio = int(settings.get("testing_agent_ratio", "1"))
    except (ValueError, TypeError):
        testing_agent_ratio = 1

    return yolo_mode, model, testing_agent_ratio


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

    # Get full status dict including orchestrator state
    status_dict = manager.get_status_dict()

    return AgentStatus(
        status=manager.status,
        pid=manager.pid,
        started_at=manager.started_at.isoformat() if manager.started_at else None,
        yolo_mode=manager.yolo_mode,
        model=manager.model,
        parallel_mode=manager.parallel_mode,
        max_concurrency=manager.max_concurrency,
        testing_agent_ratio=manager.testing_agent_ratio,
        pickup_paused=status_dict.get("pickup_paused", False),
        graceful_shutdown=status_dict.get("graceful_shutdown", False),
        active_agent_count=status_dict.get("active_agent_count", 0),
    )


@router.post("/start", response_model=AgentActionResponse)
async def start_agent(
    project_name: str,
    request: AgentStartRequest = AgentStartRequest(),
):
    """Start the agent for a project."""
    manager = get_project_manager(project_name)
    project_dir = _get_project_path(project_name)

    # Get defaults from global settings if not provided in request
    default_yolo, default_model, default_testing_ratio = _get_settings_defaults()

    yolo_mode = request.yolo_mode if request.yolo_mode is not None else default_yolo
    model = request.model if request.model else default_model
    max_concurrency = request.max_concurrency or 1
    testing_agent_ratio = request.testing_agent_ratio if request.testing_agent_ratio is not None else default_testing_ratio

    success, message = await manager.start(
        yolo_mode=yolo_mode,
        model=model,
        max_concurrency=max_concurrency,
        testing_agent_ratio=testing_agent_ratio,
    )

    # Setup auto-resume and notify scheduler if start was successful
    if success and project_dir:
        # Notify scheduler of manual start (to prevent auto-stop during scheduled window)
        from ..services.scheduler_service import get_scheduler
        get_scheduler().notify_manual_start(project_name, project_dir)

        # Register for auto-resume if enabled
        tracker = register_auto_resume(
            project_name=project_name,
            project_dir=project_dir,
            yolo_mode=yolo_mode,
            model=model,
            max_concurrency=max_concurrency,
            testing_agent_ratio=testing_agent_ratio,
        )

        if tracker:
            # Create status callback for crash detection
            async def on_crash_status_change(status: str):
                if status == "crashed":
                    await handle_agent_crash(project_name)

            tracker.set_status_callback(on_crash_status_change)
            manager.add_status_callback(on_crash_status_change)

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/stop", response_model=AgentActionResponse)
async def stop_agent(project_name: str):
    """Stop the agent for a project."""
    manager = get_project_manager(project_name)

    # Unregister from auto-resume BEFORE stopping
    # This prevents the crash handler from restarting after manual stop
    unregister_auto_resume(project_name)

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


@router.post("/pause-pickup", response_model=AgentActionResponse)
async def pause_pickup(project_name: str):
    """Pause claiming new features. Running agents continue until completion."""
    manager = get_project_manager(project_name)

    success, message = await manager.pause_pickup()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/resume-pickup", response_model=AgentActionResponse)
async def resume_pickup(project_name: str):
    """Resume claiming new features after pause."""
    manager = get_project_manager(project_name)

    success, message = await manager.resume_pickup()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/graceful-stop", response_model=AgentActionResponse)
async def graceful_stop(project_name: str):
    """Stop the agent gracefully after current tasks complete."""
    manager = get_project_manager(project_name)

    # Unregister from auto-resume - graceful stop is intentional
    unregister_auto_resume(project_name)

    success, message = await manager.graceful_stop()

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


@router.post("/run-doc-admin", response_model=AgentActionResponse)
async def run_doc_admin(project_name: str):
    """Manually trigger the documentation admin agent.

    This spawns a doc-admin agent to assess and update project documentation.
    Works whether the main agent is running or not.
    Uses a lock file to prevent duplicate doc-admin agents.
    """
    import os
    import subprocess
    import sys

    manager = get_project_manager(project_name)
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    # Check lock file to prevent duplicate doc-admin runs
    doc_admin_lock = project_dir / ".doc-admin.lock"
    if doc_admin_lock.exists():
        try:
            pid = int(doc_admin_lock.read_text().strip())
            # Check if process is still running
            os.kill(pid, 0)
            return AgentActionResponse(
                success=False,
                status=manager.status,
                message=f"Doc-admin already running (PID {pid})",
            )
        except (ValueError, ProcessLookupError, PermissionError):
            # Stale lock - will be cleaned up by the new process
            pass

    root_dir = Path(__file__).parent.parent.parent
    cmd = [
        sys.executable, "-u",
        str(root_dir / "autonomous_agent_demo.py"),
        "--project-dir", str(project_dir),
        "--agent-type", "doc-admin",
        "--max-iterations", "1",
        "--model", "haiku",
    ]

    try:
        # Fire and forget - don't wait for completion
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(root_dir),
        )
        return AgentActionResponse(
            success=True,
            status=manager.status,
            message="Started doc-admin agent",
        )
    except Exception as e:
        return AgentActionResponse(
            success=False,
            status=manager.status,
            message=f"Failed to start doc-admin agent: {e}",
        )
