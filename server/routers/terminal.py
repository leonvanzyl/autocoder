"""
Terminal Router
===============

REST and WebSocket endpoints for interactive terminal I/O with PTY support.
Provides real-time bidirectional communication with terminal sessions.
Supports multiple terminals per project with create, list, rename, delete operations.
"""

import asyncio
import base64
import json
import logging
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..services.terminal_manager import (
    create_terminal,
    delete_terminal,
    get_terminal_info,
    get_terminal_session,
    list_terminals,
    rename_terminal,
    stop_terminal_session,
)

# Add project root to path for registry import
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from registry import get_project_path as registry_get_project_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/terminal", tags=["terminal"])


class TerminalCloseCode:
    """WebSocket close codes for terminal endpoint."""

    INVALID_PROJECT_NAME = 4000
    PROJECT_NOT_FOUND = 4004
    FAILED_TO_START = 4500


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    return registry_get_project_path(project_name)


def validate_project_name(name: str) -> bool:
    """
    Validate project name to prevent path traversal attacks.

    Allows only alphanumeric characters, underscores, and hyphens.
    Maximum length of 50 characters.

    Args:
        name: The project name to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r"^[a-zA-Z0-9_-]{1,50}$", name))


def validate_terminal_id(terminal_id: str) -> bool:
    """
    Validate terminal ID format.

    Args:
        terminal_id: The terminal ID to validate

    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r"^[a-zA-Z0-9]{1,16}$", terminal_id))


# Pydantic models for request/response bodies
class CreateTerminalRequest(BaseModel):
    """Request body for creating a terminal."""

    name: str | None = None


class RenameTerminalRequest(BaseModel):
    """Request body for renaming a terminal."""

    name: str


class TerminalInfoResponse(BaseModel):
    """Response model for terminal info."""

    id: str
    name: str
    created_at: str


# REST Endpoints


@router.get("/{project_name}")
async def list_project_terminals(project_name: str) -> list[TerminalInfoResponse]:
    """
    List all terminals for a project.

    Args:
        project_name: Name of the project

    Returns:
        List of terminal info objects
    """
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    terminals = list_terminals(project_name)

    # If no terminals exist, create a default one
    if not terminals:
        info = create_terminal(project_name)
        terminals = [info]

    return [
        TerminalInfoResponse(id=t.id, name=t.name, created_at=t.created_at) for t in terminals
    ]


@router.post("/{project_name}")
async def create_project_terminal(
    project_name: str, request: CreateTerminalRequest
) -> TerminalInfoResponse:
    """
    Create a new terminal for a project.

    Args:
        project_name: Name of the project
        request: Request body with optional terminal name

    Returns:
        The created terminal info
    """
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    info = create_terminal(project_name, request.name)
    return TerminalInfoResponse(id=info.id, name=info.name, created_at=info.created_at)


@router.patch("/{project_name}/{terminal_id}")
async def rename_project_terminal(
    project_name: str, terminal_id: str, request: RenameTerminalRequest
) -> TerminalInfoResponse:
    """
    Rename a terminal.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal to rename
        request: Request body with new name

    Returns:
        The updated terminal info
    """
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    if not validate_terminal_id(terminal_id):
        raise HTTPException(status_code=400, detail="Invalid terminal ID")

    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    if not rename_terminal(project_name, terminal_id, request.name):
        raise HTTPException(status_code=404, detail="Terminal not found")

    info = get_terminal_info(project_name, terminal_id)
    if not info:
        raise HTTPException(status_code=404, detail="Terminal not found")

    return TerminalInfoResponse(id=info.id, name=info.name, created_at=info.created_at)


@router.delete("/{project_name}/{terminal_id}")
async def delete_project_terminal(project_name: str, terminal_id: str) -> dict:
    """
    Delete a terminal and stop its session.

    Args:
        project_name: Name of the project
        terminal_id: ID of the terminal to delete

    Returns:
        Success message
    """
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name")

    if not validate_terminal_id(terminal_id):
        raise HTTPException(status_code=400, detail="Invalid terminal ID")

    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail="Project not found")

    # Stop the session if it's running
    await stop_terminal_session(project_name, terminal_id)

    # Delete the terminal metadata
    if not delete_terminal(project_name, terminal_id):
        raise HTTPException(status_code=404, detail="Terminal not found")

    return {"message": "Terminal deleted"}


# WebSocket Endpoint


@router.websocket("/ws/{project_name}/{terminal_id}")
async def terminal_websocket(websocket: WebSocket, project_name: str, terminal_id: str) -> None:
    """
    WebSocket endpoint for interactive terminal I/O.

    Message protocol:

    Client -> Server:
    - {"type": "input", "data": "<base64-encoded-bytes>"} - Keyboard input
    - {"type": "resize", "cols": 80, "rows": 24} - Terminal resize
    - {"type": "ping"} - Keep-alive ping

    Server -> Client:
    - {"type": "output", "data": "<base64-encoded-bytes>"} - PTY output
    - {"type": "exit", "code": 0} - Shell process exited
    - {"type": "pong"} - Keep-alive response
    - {"type": "error", "message": "..."} - Error message
    """
    # Validate project name
    if not validate_project_name(project_name):
        await websocket.close(
            code=TerminalCloseCode.INVALID_PROJECT_NAME, reason="Invalid project name"
        )
        return

    # Validate terminal ID
    if not validate_terminal_id(terminal_id):
        await websocket.close(
            code=TerminalCloseCode.INVALID_PROJECT_NAME, reason="Invalid terminal ID"
        )
        return

    # Look up project directory from registry
    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.close(
            code=TerminalCloseCode.PROJECT_NOT_FOUND,
            reason="Project not found in registry",
        )
        return

    if not project_dir.exists():
        await websocket.close(
            code=TerminalCloseCode.PROJECT_NOT_FOUND,
            reason="Project directory not found",
        )
        return

    # Verify terminal exists in metadata
    terminal_info = get_terminal_info(project_name, terminal_id)
    if not terminal_info:
        await websocket.close(
            code=TerminalCloseCode.PROJECT_NOT_FOUND,
            reason="Terminal not found",
        )
        return

    await websocket.accept()

    # Get or create terminal session for this project/terminal
    session = get_terminal_session(project_name, project_dir, terminal_id)

    # Queue for output data to send to client
    output_queue: asyncio.Queue[bytes] = asyncio.Queue()

    # Callback to receive terminal output and queue it for sending
    def on_output(data: bytes) -> None:
        """Queue terminal output for async sending to WebSocket."""
        try:
            output_queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning(f"Output queue full for {project_name}, dropping data")

    # Register the output callback
    session.add_output_callback(on_output)

    # Track if we need to wait for initial resize before starting
    # This ensures the PTY is created with correct dimensions from the start
    needs_initial_resize = not session.is_active

    # Task to send queued output to WebSocket
    async def send_output_task() -> None:
        """Continuously send queued output to the WebSocket client."""
        try:
            while True:
                # Wait for output data
                data = await output_queue.get()

                # Encode as base64 and send
                encoded = base64.b64encode(data).decode("ascii")
                await websocket.send_json({"type": "output", "data": encoded})

        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.warning(f"Error sending output for {project_name}: {e}")
            raise

    # Task to monitor if the terminal session exits
    async def monitor_exit_task() -> None:
        """Monitor the terminal session and notify client on exit."""
        try:
            # Wait for session to become active first (deferred start)
            while not session.is_active:
                await asyncio.sleep(0.1)

            # Now monitor until it becomes inactive
            while session.is_active:
                await asyncio.sleep(0.5)

            # Session ended - send exit message
            # Note: We don't have access to actual exit code from PTY
            await websocket.send_json({"type": "exit", "code": 0})

        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.warning(f"Error in exit monitor for {project_name}: {e}")

    # Start background tasks
    output_task = asyncio.create_task(send_output_task())
    exit_task = asyncio.create_task(monitor_exit_task())

    try:
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "input":
                    # Only allow input after terminal is started
                    if not session.is_active:
                        await websocket.send_json(
                            {"type": "error", "message": "Terminal not ready - send resize first"}
                        )
                        continue

                    # Decode base64 input and write to PTY
                    encoded_data = message.get("data", "")
                    # Add size limit to prevent DoS
                    if len(encoded_data) > 65536:  # 64KB limit for base64 encoded data
                        await websocket.send_json({"type": "error", "message": "Input too large"})
                        continue
                    if encoded_data:
                        try:
                            decoded = base64.b64decode(encoded_data)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to decode base64 input: {e}")
                            await websocket.send_json(
                                {"type": "error", "message": "Invalid base64 data"}
                            )
                            continue

                        try:
                            session.write(decoded)
                        except Exception as e:
                            logger.warning(f"Failed to write to terminal: {e}")
                            await websocket.send_json(
                                {"type": "error", "message": "Failed to write to terminal"}
                            )

                elif msg_type == "resize":
                    # Resize the terminal
                    cols = message.get("cols", 80)
                    rows = message.get("rows", 24)

                    # Validate dimensions
                    if isinstance(cols, int) and isinstance(rows, int):
                        cols = max(10, min(500, cols))
                        rows = max(5, min(200, rows))

                        # If this is the first resize and session not started, start with these dimensions
                        # This ensures the PTY is created with correct size from the beginning
                        if needs_initial_resize and not session.is_active:
                            started = await session.start(cols=cols, rows=rows)
                            if not started:
                                session.remove_output_callback(on_output)
                                try:
                                    await websocket.send_json(
                                        {"type": "error", "message": "Failed to start terminal session"}
                                    )
                                except Exception:
                                    pass
                                await websocket.close(
                                    code=TerminalCloseCode.FAILED_TO_START, reason="Failed to start terminal"
                                )
                                return
                            # Mark that we no longer need initial resize
                            needs_initial_resize = False
                        else:
                            session.resize(cols, rows)
                    else:
                        await websocket.send_json({"type": "error", "message": "Invalid resize dimensions"})

                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info(f"Terminal WebSocket disconnected for {project_name}/{terminal_id}")

    except Exception as e:
        logger.exception(f"Terminal WebSocket error for {project_name}/{terminal_id}")
        try:
            await websocket.send_json({"type": "error", "message": f"Server error: {str(e)}"})
        except Exception:
            pass

    finally:
        # Cancel background tasks
        output_task.cancel()
        exit_task.cancel()

        try:
            await output_task
        except asyncio.CancelledError:
            pass

        try:
            await exit_task
        except asyncio.CancelledError:
            pass

        # Remove the output callback
        session.remove_output_callback(on_output)

        # Only stop session if no other clients are connected
        with session._callbacks_lock:
            remaining_callbacks = len(session._output_callbacks)

        if remaining_callbacks == 0:
            await session.stop()
            logger.info(f"Terminal session stopped for {project_name}/{terminal_id} (last client disconnected)")
        else:
            logger.info(
                f"Client disconnected from {project_name}/{terminal_id}, {remaining_callbacks} clients remaining"
            )
