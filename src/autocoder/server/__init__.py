"""
FastAPI Backend Server
======================

Web UI server for the Autonomous Coding Agent.
Provides REST API and WebSocket endpoints for project management,
feature tracking, and agent control.
"""

import os
import uvicorn
from pathlib import Path

from autocoder.core.port_config import get_ui_port
from autocoder.server.server_lock import ServerLock


def start_server(host: str = "127.0.0.1", port: int | None = None, reload: bool = False) -> None:
    """
    Start the AutoCoder web UI server.

    Args:
        host: Host to bind to (default: 127.0.0.1 for security)
        port: Port to bind to (default: AUTOCODER_UI_PORT or 8888)
        reload: Enable auto-reload for development (default: False)
    """
    if port is None:
        port = get_ui_port()
    disable_lock = str(os.environ.get("AUTOCODER_DISABLE_UI_LOCK", "")).lower() in ("1", "true", "yes")
    if disable_lock:
        uvicorn.run(
            "autocoder.server.main:app",
            host=host,
            port=port,
            reload=reload,
        )
        return

    with ServerLock(port):
        uvicorn.run(
            "autocoder.server.main:app",
            host=host,
            port=port,
            reload=reload,
        )


__all__ = ["start_server"]
