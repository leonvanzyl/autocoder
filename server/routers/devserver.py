"""
Dev Server Router
=================

API endpoints for dev server control (start/stop) and configuration.
Uses project registry for path lookups and project_config for command detection.
"""

import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    DevServerActionResponse,
    DevServerConfigResponse,
    DevServerConfigUpdate,
    DevServerStartRequest,
    DevServerStatus,
)
from ..services.dev_server_manager import get_devserver_manager
from ..services.project_config import (
    clear_dev_command,
    get_dev_command,
    get_project_config,
    set_dev_command,
)

# Add root to path for registry import
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from registry import get_project_path as registry_get_project_path


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    return registry_get_project_path(project_name)


router = APIRouter(prefix="/api/projects/{project_name}/devserver", tags=["devserver"])


# ============================================================================
# Helper Functions
# ============================================================================


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


def get_project_dir(project_name: str) -> Path:
    """
    Get the validated project directory for a project name.

    Args:
        project_name: Name of the project

    Returns:
        Path to the project directory

    Raises:
        HTTPException: If project is not found or directory does not exist
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}"
        )

    return project_dir


def get_project_devserver_manager(project_name: str):
    """
    Get the dev server process manager for a project.

    Args:
        project_name: Name of the project

    Returns:
        DevServerProcessManager instance for the project

    Raises:
        HTTPException: If project is not found or directory does not exist
    """
    project_dir = get_project_dir(project_name)
    return get_devserver_manager(project_name, project_dir)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=DevServerStatus)
async def get_devserver_status(project_name: str) -> DevServerStatus:
    """
    Get the current status of the dev server for a project.

    Returns information about whether the dev server is running,
    its process ID, detected URL, and the command used to start it.
    """
    manager = get_project_devserver_manager(project_name)

    # Run healthcheck to detect crashed processes
    await manager.healthcheck()

    return DevServerStatus(
        status=manager.status,
        pid=manager.pid,
        url=manager.detected_url,
        command=manager._command,
        started_at=manager.started_at,
    )


@router.post("/start", response_model=DevServerActionResponse)
async def start_devserver(
    project_name: str,
    request: DevServerStartRequest = DevServerStartRequest(),
) -> DevServerActionResponse:
    """
    Start the dev server for a project.

    If a custom command is provided in the request, it will be used.
    Otherwise, the effective command from the project configuration is used.

    Args:
        project_name: Name of the project
        request: Optional start request with custom command

    Returns:
        Response indicating success/failure and current status
    """
    manager = get_project_devserver_manager(project_name)
    project_dir = get_project_dir(project_name)

    # Determine which command to use
    command: str | None
    if request.command:
        command = request.command
    else:
        command = get_dev_command(project_dir)

    if not command:
        raise HTTPException(
            status_code=400,
            detail="No dev command available. Configure a custom command or ensure project type can be detected."
        )

    # Now command is definitely str
    success, message = await manager.start(command)

    return DevServerActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/stop", response_model=DevServerActionResponse)
async def stop_devserver(project_name: str) -> DevServerActionResponse:
    """
    Stop the dev server for a project.

    Gracefully terminates the dev server process and all its child processes.

    Args:
        project_name: Name of the project

    Returns:
        Response indicating success/failure and current status
    """
    manager = get_project_devserver_manager(project_name)

    success, message = await manager.stop()

    return DevServerActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.get("/config", response_model=DevServerConfigResponse)
async def get_devserver_config(project_name: str) -> DevServerConfigResponse:
    """
    Get the dev server configuration for a project.

    Returns information about:
    - detected_type: The auto-detected project type (nodejs-vite, python-django, etc.)
    - detected_command: The default command for the detected type
    - custom_command: Any user-configured custom command
    - effective_command: The command that will actually be used (custom or detected)

    Args:
        project_name: Name of the project

    Returns:
        Configuration details for the project's dev server
    """
    project_dir = get_project_dir(project_name)
    config = get_project_config(project_dir)

    return DevServerConfigResponse(
        detected_type=config["detected_type"],
        detected_command=config["detected_command"],
        custom_command=config["custom_command"],
        effective_command=config["effective_command"],
    )


@router.patch("/config", response_model=DevServerConfigResponse)
async def update_devserver_config(
    project_name: str,
    update: DevServerConfigUpdate,
) -> DevServerConfigResponse:
    """
    Update the dev server configuration for a project.

    Set custom_command to a string to override the auto-detected command.
    Set custom_command to null/None to clear the custom command and revert
    to using the auto-detected command.

    Args:
        project_name: Name of the project
        update: Configuration update containing the new custom_command

    Returns:
        Updated configuration details for the project's dev server
    """
    project_dir = get_project_dir(project_name)

    # Update the custom command
    if update.custom_command is None:
        # Clear the custom command
        try:
            clear_dev_command(project_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Set the custom command
        try:
            set_dev_command(project_dir, update.custom_command)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save configuration: {e}"
            )

    # Return updated config
    config = get_project_config(project_dir)

    return DevServerConfigResponse(
        detected_type=config["detected_type"],
        detected_command=config["detected_command"],
        custom_command=config["custom_command"],
        effective_command=config["effective_command"],
    )
