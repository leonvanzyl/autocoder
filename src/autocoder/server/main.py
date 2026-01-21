"""
FastAPI Main Application
========================

Main entry point for the Autonomous Coding UI server.
Provides REST API, WebSocket, and static file serving.
"""

import mimetypes
import shutil
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

# Fix MIME types for JavaScript files on Windows
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

from .routers import (
    projects_router,
    features_router,
    agent_router,
    spec_creation_router,
    expand_project_router,
    filesystem_router,
    assistant_chat_router,
    model_settings_router,
    logs_router,
    activity_router,
    parallel_router,
    settings_router,
    engine_settings_router,
    generate_router,
    project_config_router,
    diagnostics_router,
    worktrees_router,
    devserver_router,
    terminal_router,
)
from .websocket import project_websocket
from .services.process_manager import cleanup_all_managers
from .services.assistant_chat_session import cleanup_all_sessions as cleanup_assistant_sessions
from .services.expand_chat_session import cleanup_all_expand_sessions
from .services.dev_server_manager import cleanup_all_dev_servers
from .services.scheduler import restore_schedules, cleanup_schedules
from .routers.devserver import devserver_websocket
from .services.terminal_manager import cleanup_all_terminals
from .routers.terminal import terminal_websocket
from .schemas import SetupStatus
from autocoder.core.cli_defaults import get_codex_cli_defaults
from autocoder.core.port_config import get_ui_port, get_ui_cors_origins, get_ui_allow_remote


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
ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    await restore_schedules()
    yield
    # Shutdown - cleanup all running agents and assistant sessions
    await cleanup_all_managers()
    await cleanup_assistant_sessions()
    await cleanup_all_expand_sessions()
    await cleanup_all_dev_servers()
    await cleanup_all_terminals()
    await cleanup_schedules()


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
    allow_credentials=ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Security Middleware
# ============================================================================

@app.middleware("http")
async def require_localhost(request: Request, call_next):
    """Only allow requests from localhost."""
    if get_ui_allow_remote():
        return await call_next(request)
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
app.include_router(expand_project_router)
app.include_router(filesystem_router)
app.include_router(assistant_chat_router)
app.include_router(model_settings_router)
app.include_router(logs_router)
app.include_router(activity_router)
app.include_router(parallel_router)
app.include_router(settings_router)
app.include_router(engine_settings_router)
app.include_router(generate_router)
app.include_router(project_config_router)
app.include_router(diagnostics_router)
app.include_router(worktrees_router)
app.include_router(devserver_router)
app.include_router(terminal_router)


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws/projects/{project_name}")
async def websocket_endpoint(websocket: WebSocket, project_name: str):
    """WebSocket endpoint for real-time project updates."""
    await project_websocket(websocket, project_name)


@app.websocket("/ws/projects/{project_name}/devserver")
async def devserver_ws_endpoint(websocket: WebSocket, project_name: str):
    """WebSocket endpoint for dev server logs/status."""
    await devserver_websocket(websocket, project_name)


@app.websocket("/ws/projects/{project_name}/terminal/{terminal_id}")
async def terminal_ws_endpoint(websocket: WebSocket, project_name: str, terminal_id: str):
    """WebSocket endpoint for interactive terminal I/O."""
    await terminal_websocket(websocket, project_name, terminal_id)


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
    # Check for Claude CLI (allow override; defaults to "claude")
    cli_command = (os.environ.get("AUTOCODER_CLI_COMMAND") or os.environ.get("CLI_COMMAND") or "claude").strip()
    claude_cli = shutil.which(cli_command) is not None

    # Claude Code CLI auth storage varies by version/platform:
    # - older: ~/.claude/.credentials.json
    # - newer: OS keychain + ~/.claude state directory
    claude_dir = Path.home() / ".claude"
    has_claude_dir = claude_dir.exists()
    credentials_path = claude_dir / ".credentials.json"
    has_credentials_file = credentials_path.exists()

    # Check for env auth (custom endpoints or direct API auth)
    env_auth = bool(os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))
    base_url = (os.environ.get("ANTHROPIC_BASE_URL") or "").strip().lower()
    custom_api = bool(base_url) or bool(os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    glm_mode = bool(custom_api and (("z.ai" in base_url) or ("glm" in base_url)))

    # Overall auth readiness: either env auth, or a plausibly authenticated CLI.
    credentials = bool(env_auth or (claude_cli and (has_credentials_file or has_claude_dir)))

    # Check for Node.js and npm
    node = shutil.which("node") is not None
    npm = shutil.which("npm") is not None
    codex_cli = shutil.which("codex") is not None
    gemini_cli = shutil.which("gemini") is not None

    codex_defaults = get_codex_cli_defaults()

    return SetupStatus(
        claude_cli=claude_cli,
        credentials=credentials,
        node=node,
        npm=npm,
        codex_cli=codex_cli,
        gemini_cli=gemini_cli,
        codex_model_default=codex_defaults.model,
        codex_reasoning_default=codex_defaults.reasoning_effort,
        env_auth=env_auth,
        custom_api=custom_api,
        glm_mode=glm_mode,
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
        return HTMLResponse(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AutoCoder UI</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 40px; }
      code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
      pre { background: #111; color: #eee; padding: 12px 14px; border-radius: 8px; overflow: auto; }
      a { color: #2563eb; }
    </style>
  </head>
  <body>
    <h1>AutoCoder UI build not found</h1>
    <p>The API is running (try <code>/api/health</code>), but the React UI build (<code>ui/dist</code>) is missing.</p>
    <p>To build and serve the UI:</p>
    <pre>npm -C ui install
npm -C ui run build</pre>
    <p>Or for development:</p>
    <pre>npm -C ui install
npm -C ui run dev</pre>
    <p>Then refresh this page.</p>
  </body>
</html>
""".strip(),
            status_code=200,
        )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from autocoder.core.port_config import get_ui_host
    uvicorn.run(
        "autocoder.server.main:app",
        host=get_ui_host(),
        port=API_PORT,
        reload=True,
    )
