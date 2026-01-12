"""
FastAPI Main Application
========================

Main entry point for the Autonomous Coding UI server.
Provides REST API, WebSocket, and static file serving.
"""

import mimetypes
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Fix MIME types for JavaScript files on Windows
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from .routers import (
    projects_router,
    features_router,
    agent_router,
    spec_creation_router,
    filesystem_router,
    assistant_chat_router,
    model_settings_router,
    logs_router,
    parallel_router,
    settings_router,
)
from .websocket import project_websocket
from .services.process_manager import cleanup_all_managers
from .services.assistant_chat_session import cleanup_all_sessions as cleanup_assistant_sessions
from .schemas import SetupStatus
from autocoder.core.port_config import get_ui_port, get_ui_cors_origins


# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent


def _find_ui_dist_dir() -> Path | None:
    """
    Locate the built React UI `dist/` directory.

    In editable installs, the FastAPI code lives under `src/autocoder/server/`, while the UI lives
    at repo-root `ui/dist`. When installed as a package, the UI may not exist at all.
    """
    # Most common: repo root is 3 parents above this file (server -> autocoder -> src -> repo_root).
    for base in Path(__file__).resolve().parents:
        candidate = base / "ui" / "dist"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


UI_DIST_DIR = _find_ui_dist_dir()

# Get UI server port + CORS allowlist
API_PORT = get_ui_port()
CORS_ORIGINS = get_ui_cors_origins()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    yield
    # Shutdown - cleanup all running agents and assistant sessions
    await cleanup_all_managers()
    await cleanup_assistant_sessions()


# Create FastAPI app
app = FastAPI(
    title="Autonomous Coding UI",
    description="Web UI for the Autonomous Coding Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow only localhost origins for security
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Security Middleware
# ============================================================================

@app.middleware("http")
async def require_localhost(request: Request, call_next):
    """Only allow requests from localhost."""
    client_host = request.client.host if request.client else None

    # Allow localhost connections
    if client_host not in ("127.0.0.1", "::1", "localhost", None):
        raise HTTPException(status_code=403, detail="Localhost access only")

    return await call_next(request)


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(projects_router)
app.include_router(features_router)
app.include_router(agent_router)
app.include_router(spec_creation_router)
app.include_router(filesystem_router)
app.include_router(assistant_chat_router)
app.include_router(model_settings_router)
app.include_router(logs_router)
app.include_router(parallel_router)
app.include_router(settings_router)


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/projects/{project_name}")
async def websocket_endpoint(websocket: WebSocket, project_name: str):
    """WebSocket endpoint for real-time project updates."""
    await project_websocket(websocket, project_name)


# ============================================================================
# Setup & Health Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/setup/status", response_model=SetupStatus)
async def setup_status():
    """Check system setup status."""
    # Check for Claude CLI
    claude_cli = shutil.which("claude") is not None

    # Check for credentials file
    credentials_path = Path.home() / ".claude" / ".credentials.json"
    credentials = credentials_path.exists()

    # Check for Node.js and npm
    node = shutil.which("node") is not None
    npm = shutil.which("npm") is not None

    return SetupStatus(
        claude_cli=claude_cli,
        credentials=credentials,
        node=node,
        npm=npm,
    )


# ============================================================================
# Static File Serving (Production)
# ============================================================================

# Serve React build files if they exist
if UI_DIST_DIR and UI_DIST_DIR.exists():
    # Mount static assets
    app.mount("/assets", StaticFiles(directory=UI_DIST_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        """Serve the React app index.html."""
        return FileResponse(UI_DIST_DIR / "index.html")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """
        Serve static files or fall back to index.html for SPA routing.
        """
        # Check if the path is an API route (shouldn't hit this due to router ordering)
        if path.startswith("api/") or path.startswith("ws/"):
            raise HTTPException(status_code=404)

        # Try to serve the file directly
        file_path = UI_DIST_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Fall back to index.html for SPA routing
        return FileResponse(UI_DIST_DIR / "index.html")
else:
    @app.get("/")
    async def missing_ui_build():
        """
        Friendly message when the UI build isn't available.

        The API still works (use `/api/health`), but serving the React app requires building `ui/dist`.
        """
        return {
            "detail": "UI build not found. Run `npm -C ui install` then `npm -C ui run build`, or run the Vite dev server in `ui/`.",
        }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",  # Localhost only for security
        port=API_PORT,
        reload=True,
    )
