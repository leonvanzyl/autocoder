"""
Agent Router
============

API endpoints for agent control (start/stop/pause/resume) and git status.
Uses project registry for path lookups.
"""

import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    AgentActionResponse,
    AgentStartRequest,
    AgentStatus,
    GitStatusResponse,
    ModelConfigSchema,
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

    # Build model config schema if available
    model_config_schema = None
    if manager.model_config:
        model_config_schema = ModelConfigSchema(**manager.model_config)

    return AgentStatus(
        status=manager.status,
        pid=manager.pid,
        started_at=manager.started_at,
        yolo_mode=manager.yolo_mode,
        model_config=model_config_schema,
    )


@router.post("/start", response_model=AgentActionResponse)
async def start_agent(
    project_name: str,
    request: AgentStartRequest = AgentStartRequest(),
):
    """Start the agent for a project."""
    manager = get_project_manager(project_name)

    # Convert model config schema to dict for process manager
    model_config_dict = None
    if request.model_config:
        model_config_dict = request.model_config.model_dump()

    success, message = await manager.start(
        yolo_mode=request.yolo_mode,
        yolo_review=request.yolo_review,
        model_config=model_config_dict,
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


@router.get("/git", response_model=GitStatusResponse)
async def get_git_status(project_name: str):
    """Get the git status for a project directory."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    git_dir = project_dir / ".git"
    if not git_dir.exists():
        return GitStatusResponse(has_git=False)

    def _run_git(args: list[str]) -> str | None:
        """Run a git command in the project directory and return stdout."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    # Get current branch
    branch = _run_git(["branch", "--show-current"])

    # Get last commit info
    last_commit_hash = _run_git(["log", "-1", "--format=%h"])
    last_commit_message = _run_git(["log", "-1", "--format=%s"])
    last_commit_time = _run_git(["log", "-1", "--format=%ci"])

    # Check for uncommitted changes
    status_output = _run_git(["status", "--porcelain"])
    is_dirty = bool(status_output)
    uncommitted_count = len(status_output.splitlines()) if status_output else 0

    # Total commit count
    commit_count_str = _run_git(["rev-list", "--count", "HEAD"])
    total_commits = int(commit_count_str) if commit_count_str else 0

    return GitStatusResponse(
        has_git=True,
        branch=branch,
        last_commit_hash=last_commit_hash,
        last_commit_message=last_commit_message,
        last_commit_time=last_commit_time,
        is_dirty=is_dirty,
        uncommitted_count=uncommitted_count,
        total_commits=total_commits,
    )
