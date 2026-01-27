"""
FastAPI Main Application
========================

Main entry point for the Autonomous Coding UI server.
Provides REST API, WebSocket, and static file serving.
"""

import asyncio
import logging
import os
import re
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

# Fix for Windows subprocess support in asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pythonjsonlogger import jsonlogger
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .routers import (
    agent_router,
    assistant_chat_router,
    devserver_router,
    expand_project_router,
    features_router,
    filesystem_router,
    projects_router,
    schedules_router,
    settings_router,
    spec_creation_router,
    terminal_router,
)
from .schemas import SetupStatus
from .services.assistant_chat_session import cleanup_all_sessions as cleanup_assistant_sessions
from .services.dev_server_manager import (
    cleanup_all_devservers,
    cleanup_orphaned_devserver_locks,
)
from .services.expand_chat_session import cleanup_all_expand_sessions
from .services.process_manager import cleanup_all_managers, cleanup_orphaned_locks
from .services.scheduler_service import cleanup_scheduler, get_scheduler
from .services.terminal_manager import cleanup_all_terminals
from .websocket import project_websocket

# Paths
ROOT_DIR = Path(__file__).parent.parent
UI_DIST_DIR = ROOT_DIR / "ui" / "dist"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

# contextvar for request ID
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging():
    """Configure JSON logging with request_id."""
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    # Uvicorn loggers
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)


configure_logging()

def configure_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    sentry_init(
        dsn=dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
        environment=os.getenv("SENTRY_ENV", "production"),
    )


def configure_tracing(app: FastAPI):
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "autocoder-server"),
            "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "production"),
        }
    )
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)


METRICS_ENABLED = os.environ.get("AUTOCODER_ENABLE_METRICS", "").lower() in ("1", "true", "yes")


def normalize_path(path: str) -> str:
    if not path:
        return "/"
    normalized = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "/:uuid",
        path,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"/[0-9a-f]{8,}", "/:id", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"/\d+", "/:num", normalized)
    return normalized or "/"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup - clean up orphaned lock files from previous runs
    cleanup_orphaned_locks()
    cleanup_orphaned_devserver_locks()

    # Start the scheduler service
    scheduler = get_scheduler()
    await scheduler.start()

    yield

    # Shutdown - cleanup scheduler first to stop triggering new starts
    await cleanup_scheduler()
    # Then cleanup all running agents, sessions, terminals, and dev servers
    await cleanup_all_managers()
    await cleanup_assistant_sessions()
    await cleanup_all_expand_sessions()
    await cleanup_all_terminals()
    await cleanup_all_devservers()


# Create FastAPI app
app = FastAPI(
    title="Autonomous Coding UI",
    description="Web UI for the Autonomous Coding Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Observability (optional, controlled by env vars)
configure_sentry()
configure_tracing(app)

# Check if remote access is enabled via environment variable
# Set by start_ui.py when --host is not 127.0.0.1
ALLOW_REMOTE = os.environ.get("AUTOCODER_ALLOW_REMOTE", "").lower() in ("1", "true", "yes")

# CORS - allow all origins when remote access is enabled, otherwise localhost only
if ALLOW_REMOTE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for remote access
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",      # Vite dev server
            "http://127.0.0.1:5173",
            "http://localhost:8888",      # Production
            "http://127.0.0.1:8888",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================================================
# Health Endpoint
# ============================================================================

@app.get("/health")
async def health():
    """Lightweight liveness probe used by deploy smoke tests."""
    return {"status": "ok"}


@app.get("/readiness")
async def readiness():
    """
    Readiness probe placeholder.

    Add dependency checks (DB, external APIs, queues) here when introduced.
    """
    return {"status": "ready"}


# ============================================================================
# Security Middleware
# ============================================================================

if not ALLOW_REMOTE:
    @app.middleware("http")
    async def require_localhost(request: Request, call_next):
        """Only allow requests from localhost (disabled when AUTOCODER_ALLOW_REMOTE=1)."""
        client_host = request.client.host if request.client else None

        # Allow localhost connections
        if client_host not in ("127.0.0.1", "::1", "localhost", None):
            raise HTTPException(status_code=403, detail="Localhost access only")

        return await call_next(request)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a request_id to context and response headers for traceability."""
    incoming = request.headers.get("X-Request-ID")
    req_id = incoming or uuid.uuid4().hex
    token = request_id_ctx.set(req_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = req_id
    return response


if METRICS_ENABLED:
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        """Capture basic Prometheus metrics."""
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)
        method = request.method
        normalized = normalize_path(path)
        with REQUEST_LATENCY.labels(method=method, path=normalized).time():
            response: Response = await call_next(request)
        status = response.status_code
        REQUEST_COUNTER.labels(method=method, path=normalized, status=status).inc()
        return response


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(projects_router)
app.include_router(features_router)
app.include_router(agent_router)
app.include_router(schedules_router)
app.include_router(devserver_router)
app.include_router(spec_creation_router)
app.include_router(expand_project_router)
app.include_router(filesystem_router)
app.include_router(assistant_chat_router)
app.include_router(settings_router)
app.include_router(terminal_router)


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

    # Check for CLI configuration directory
    # Note: CLI no longer stores credentials in ~/.claude/.credentials.json
    # The existence of ~/.claude indicates the CLI has been configured
    claude_dir = Path.home() / ".claude"
    has_claude_config = claude_dir.exists() and claude_dir.is_dir()

    # If GLM mode is configured via .env, we have alternative credentials
    glm_configured = bool(os.getenv("ANTHROPIC_BASE_URL") and os.getenv("ANTHROPIC_AUTH_TOKEN"))

    # Gemini configuration (OpenAI-compatible Gemini API)
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))

    credentials = has_claude_config or glm_configured or gemini_configured

    # Check for Node.js and npm
    node = shutil.which("node") is not None
    npm = shutil.which("npm") is not None

    return SetupStatus(
        claude_cli=claude_cli,
        credentials=credentials,
        node=node,
        npm=npm,
        gemini=gemini_configured,
    )


# ============================================================================
# Static File Serving (Production)
# ============================================================================

# Serve React build files if they exist
if UI_DIST_DIR.exists():
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


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",  # Localhost only for security
        port=8888,
        reload=True,
    )
