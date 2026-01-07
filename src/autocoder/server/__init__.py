"""
FastAPI Backend Server
======================

Web UI server for the Autonomous Coding Agent.
Provides REST API and WebSocket endpoints for project management,
feature tracking, and agent control.
"""

import uvicorn
from pathlib import Path


def start_server(host: str = "127.0.0.1", port: int = 8888, reload: bool = False) -> None:
    """
    Start the AutoCoder web UI server.

    Args:
        host: Host to bind to (default: 127.0.0.1 for security)
        port: Port to bind to (default: 8888)
        reload: Enable auto-reload for development (default: False)
    """
    uvicorn.run(
        "autocoder.server.main:app",
        host=host,
        port=port,
        reload=reload,
    )


__all__ = ["start_server"]
