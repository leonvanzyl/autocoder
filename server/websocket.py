"""
WebSocket Handlers
==================

Real-time updates for project progress, agent output, and dev server output.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from .services.dev_server_manager import get_devserver_manager
from .services.process_manager import get_manager

# Lazy imports
_count_passing_tests = None

logger = logging.getLogger(__name__)


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def _get_count_passing_tests():
    """Lazy import of count_passing_tests."""
    global _count_passing_tests
    if _count_passing_tests is None:
        import sys
        root = Path(__file__).parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from progress import count_passing_tests
        _count_passing_tests = count_passing_tests
    return _count_passing_tests


class ConnectionManager:
    """Manages WebSocket connections per project."""

    def __init__(self):
        # project_name -> set of WebSocket connections
        self.active_connections: dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_name: str):
        """Accept a WebSocket connection for a project."""
        await websocket.accept()

        async with self._lock:
            if project_name not in self.active_connections:
                self.active_connections[project_name] = set()
            self.active_connections[project_name].add(websocket)

    async def disconnect(self, websocket: WebSocket, project_name: str):
        """Remove a WebSocket connection."""
        async with self._lock:
            if project_name in self.active_connections:
                self.active_connections[project_name].discard(websocket)
                if not self.active_connections[project_name]:
                    del self.active_connections[project_name]

    async def broadcast_to_project(self, project_name: str, message: dict):
        """Broadcast a message to all connections for a project."""
        async with self._lock:
            connections = list(self.active_connections.get(project_name, set()))

        dead_connections = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for connection in dead_connections:
                    if project_name in self.active_connections:
                        self.active_connections[project_name].discard(connection)

    def get_connection_count(self, project_name: str) -> int:
        """Get number of active connections for a project."""
        return len(self.active_connections.get(project_name, set()))


# Global connection manager
manager = ConnectionManager()

# Root directory
ROOT_DIR = Path(__file__).parent.parent


def validate_project_name(name: str) -> bool:
    """Validate project name to prevent path traversal."""
    return bool(re.match(r'^[a-zA-Z0-9_-]{1,50}$', name))


async def poll_progress(websocket: WebSocket, project_name: str, project_dir: Path):
    """Poll database for progress changes and send updates."""
    count_passing_tests = _get_count_passing_tests()
    last_passing = -1
    last_in_progress = -1
    last_total = -1

    while True:
        try:
            passing, in_progress, total = count_passing_tests(project_dir)

            # Only send if changed
            if passing != last_passing or in_progress != last_in_progress or total != last_total:
                last_passing = passing
                last_in_progress = in_progress
                last_total = total
                percentage = (passing / total * 100) if total > 0 else 0

                await websocket.send_json({
                    "type": "progress",
                    "passing": passing,
                    "in_progress": in_progress,
                    "total": total,
                    "percentage": round(percentage, 1),
                })

            await asyncio.sleep(2)  # Poll every 2 seconds
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Progress polling error: {e}")
            break


async def project_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for project updates.

    Streams:
    - Progress updates (passing/total counts)
    - Agent status changes
    - Agent stdout/stderr lines
    """
    if not validate_project_name(project_name):
        await websocket.close(code=4000, reason="Invalid project name")
        return

    project_dir = _get_project_path(project_name)
    if not project_dir:
        await websocket.close(code=4004, reason="Project not found in registry")
        return

    if not project_dir.exists():
        await websocket.close(code=4004, reason="Project directory not found")
        return

    await manager.connect(websocket, project_name)

    # Get agent manager and register callbacks
    agent_manager = get_manager(project_name, project_dir, ROOT_DIR)

    async def on_output(line: str):
        """Handle agent output - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "log",
                "line": line,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass  # Connection may be closed

    async def on_status_change(status: str):
        """Handle status change - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "agent_status",
                "status": status,
            })
        except Exception:
            pass  # Connection may be closed

    # Register callbacks
    agent_manager.add_output_callback(on_output)
    agent_manager.add_status_callback(on_status_change)

    # Get dev server manager and register callbacks
    devserver_manager = get_devserver_manager(project_name, project_dir)

    async def on_dev_output(line: str):
        """Handle dev server output - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "dev_log",
                "line": line,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass  # Connection may be closed

    async def on_dev_status_change(status: str):
        """Handle dev server status change - broadcast to this WebSocket."""
        try:
            await websocket.send_json({
                "type": "dev_server_status",
                "status": status,
                "url": devserver_manager.detected_url,
            })
        except Exception:
            pass  # Connection may be closed

    # Register dev server callbacks
    devserver_manager.add_output_callback(on_dev_output)
    devserver_manager.add_status_callback(on_dev_status_change)

    # Start progress polling task
    poll_task = asyncio.create_task(poll_progress(websocket, project_name, project_dir))

    try:
        # Send initial agent status
        await websocket.send_json({
            "type": "agent_status",
            "status": agent_manager.status,
        })

        # Send initial dev server status
        await websocket.send_json({
            "type": "dev_server_status",
            "status": devserver_manager.status,
            "url": devserver_manager.detected_url,
        })

        # Send initial progress
        count_passing_tests = _get_count_passing_tests()
        passing, in_progress, total = count_passing_tests(project_dir)
        percentage = (passing / total * 100) if total > 0 else 0
        await websocket.send_json({
            "type": "progress",
            "passing": passing,
            "in_progress": in_progress,
            "total": total,
            "percentage": round(percentage, 1),
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any incoming messages (ping/pong, commands, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle ping
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {data[:100] if data else 'empty'}")
            except Exception as e:
                logger.warning(f"WebSocket error: {e}")
                break

    finally:
        # Clean up
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass

        # Unregister agent callbacks
        agent_manager.remove_output_callback(on_output)
        agent_manager.remove_status_callback(on_status_change)

        # Unregister dev server callbacks
        devserver_manager.remove_output_callback(on_dev_output)
        devserver_manager.remove_status_callback(on_dev_status_change)

        # Disconnect from manager
        await manager.disconnect(websocket, project_name)
