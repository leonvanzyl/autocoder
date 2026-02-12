"""
Pydantic Schemas
================

Request/Response models for the API endpoints.
"""

import base64
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Import model constants from registry (single source of truth)
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from registry import DEFAULT_MODEL, VALID_MODELS

# ============================================================================
# Project Schemas
# ============================================================================

class ProjectCreate(BaseModel):
    """Request schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    path: str = Field(..., min_length=1, description="Absolute path to project directory")
    spec_method: Literal["claude", "manual"] = "claude"


class ProjectStats(BaseModel):
    """Project statistics."""
    passing: int = 0
    in_progress: int = 0
    total: int = 0
    percentage: float = 0.0


class ProjectSummary(BaseModel):
    """Summary of a project for list view."""
    name: str
    path: str
    has_spec: bool
    stats: ProjectStats
    default_concurrency: int = 3


class ProjectDetail(BaseModel):
    """Detailed project information."""
    name: str
    path: str
    has_spec: bool
    stats: ProjectStats
    prompts_dir: str
    default_concurrency: int = 3


class ProjectPrompts(BaseModel):
    """Project prompt files content."""
    app_spec: str = ""
    initializer_prompt: str = ""
    coding_prompt: str = ""


class ProjectPromptsUpdate(BaseModel):
    """Request schema for updating project prompts."""
    app_spec: str | None = None
    initializer_prompt: str | None = None
    coding_prompt: str | None = None


class ProjectSettingsUpdate(BaseModel):
    """Request schema for updating project-level settings."""
    default_concurrency: int | None = None

    @field_validator('default_concurrency')
    @classmethod
    def validate_concurrency(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("default_concurrency must be between 1 and 5")
        return v


# ============================================================================
# Feature Schemas
# ============================================================================

class FeatureBase(BaseModel):
    """Base feature attributes."""
    category: str
    name: str
    description: str
    steps: list[str]
    dependencies: list[int] = Field(default_factory=list)  # Optional dependencies


class FeatureCreate(FeatureBase):
    """Request schema for creating a new feature."""
    priority: int | None = None


class FeatureUpdate(BaseModel):
    """Request schema for updating a feature (partial updates allowed)."""
    category: str | None = None
    name: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    priority: int | None = None
    dependencies: list[int] | None = None  # Optional - can update dependencies


class FeatureResponse(FeatureBase):
    """Response schema for a feature."""
    id: int
    priority: int
    passes: bool
    in_progress: bool
    blocked: bool = False  # Computed: has unmet dependencies
    blocking_dependencies: list[int] = Field(default_factory=list)  # Computed
    needs_human_input: bool = False
    human_input_request: dict | None = None
    human_input_response: dict | None = None

    class Config:
        from_attributes = True


class HumanInputField(BaseModel):
    """Schema for a single human input field."""
    id: str
    label: str
    type: Literal["text", "textarea", "select", "boolean"] = "text"
    required: bool = True
    placeholder: str | None = None
    options: list[dict] | None = None  # For select: [{value, label}]


class HumanInputRequest(BaseModel):
    """Schema for an agent's human input request."""
    prompt: str
    fields: list[HumanInputField]


class HumanInputResponse(BaseModel):
    """Schema for a human's response to an input request."""
    fields: dict[str, str | bool | list[str]]


class FeatureListResponse(BaseModel):
    """Response containing list of features organized by status."""
    pending: list[FeatureResponse]
    in_progress: list[FeatureResponse]
    done: list[FeatureResponse]
    needs_human_input: list[FeatureResponse] = Field(default_factory=list)


class FeatureBulkCreate(BaseModel):
    """Request schema for bulk creating features."""
    features: list[FeatureCreate]
    starting_priority: int | None = None  # If None, appends after max priority


class FeatureBulkCreateResponse(BaseModel):
    """Response for bulk feature creation."""
    created: int
    features: list[FeatureResponse]


# ============================================================================
# Dependency Graph Schemas
# ============================================================================

class DependencyGraphNode(BaseModel):
    """Minimal node for graph visualization (no description exposed for security)."""
    id: int
    name: str
    category: str
    status: Literal["pending", "in_progress", "done", "blocked", "needs_human_input"]
    priority: int
    dependencies: list[int]


class DependencyGraphEdge(BaseModel):
    """Edge in the dependency graph."""
    source: int
    target: int


class DependencyGraphResponse(BaseModel):
    """Response for dependency graph visualization."""
    nodes: list[DependencyGraphNode]
    edges: list[DependencyGraphEdge]


class DependencyUpdate(BaseModel):
    """Request schema for updating a feature's dependencies."""
    dependency_ids: list[int] = Field(..., max_length=20)  # Security: limit


# ============================================================================
# Agent Schemas
# ============================================================================

class AgentStartRequest(BaseModel):
    """Request schema for starting the agent."""
    yolo_mode: bool | None = None  # None means use global settings
    model: str | None = None  # None means use global settings
    parallel_mode: bool | None = None  # DEPRECATED: Use max_concurrency instead
    max_concurrency: int | None = None  # Max concurrent coding agents (1-5)
    testing_agent_ratio: int | None = None  # Regression testing agents (0-3)

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        """Validate model is in the allowed list (Claude) or allow any model for alternative providers."""
        if v is not None and v not in VALID_MODELS:
            from registry import get_all_settings
            settings = get_all_settings()
            if settings.get("api_provider", "claude") == "claude":
                raise ValueError(f"Invalid model. Must be one of: {VALID_MODELS}")
        return v

    @field_validator('max_concurrency')
    @classmethod
    def validate_concurrency(cls, v: int | None) -> int | None:
        """Validate max_concurrency is between 1 and 5."""
        if v is not None and (v < 1 or v > 5):
            raise ValueError("max_concurrency must be between 1 and 5")
        return v

    @field_validator('testing_agent_ratio')
    @classmethod
    def validate_testing_ratio(cls, v: int | None) -> int | None:
        """Validate testing_agent_ratio is between 0 and 3."""
        if v is not None and (v < 0 or v > 3):
            raise ValueError("testing_agent_ratio must be between 0 and 3")
        return v


class AgentStatus(BaseModel):
    """Current agent status."""
    status: Literal["stopped", "running", "paused", "crashed", "pausing", "paused_graceful"]
    pid: int | None = None
    started_at: datetime | None = None
    yolo_mode: bool = False
    model: str | None = None  # Model being used by running agent
    parallel_mode: bool = False  # DEPRECATED: Always True now (unified orchestrator)
    max_concurrency: int | None = None
    testing_agent_ratio: int = 1  # Regression testing agents (0-3)


class AgentActionResponse(BaseModel):
    """Response for agent control actions."""
    success: bool
    status: str
    message: str = ""


# ============================================================================
# Setup Schemas
# ============================================================================

class SetupStatus(BaseModel):
    """System setup status."""
    claude_cli: bool
    credentials: bool
    node: bool
    npm: bool


# ============================================================================
# WebSocket Message Schemas
# ============================================================================

class WSProgressMessage(BaseModel):
    """WebSocket message for progress updates."""
    type: Literal["progress"] = "progress"
    passing: int
    in_progress: int
    total: int
    percentage: float
    needs_human_input: int = 0


class WSFeatureUpdateMessage(BaseModel):
    """WebSocket message for feature status updates."""
    type: Literal["feature_update"] = "feature_update"
    feature_id: int
    passes: bool


class WSLogMessage(BaseModel):
    """WebSocket message for agent log output."""
    type: Literal["log"] = "log"
    line: str
    timestamp: datetime
    featureId: int | None = None
    agentIndex: int | None = None


class WSAgentStatusMessage(BaseModel):
    """WebSocket message for agent status changes."""
    type: Literal["agent_status"] = "agent_status"
    status: str


# Agent state for multi-agent tracking
AgentState = Literal["idle", "thinking", "working", "testing", "success", "error", "struggling"]

# Agent type (coding vs testing)
AgentType = Literal["coding", "testing"]

# Agent mascot names assigned by index
AGENT_MASCOTS = ["Spark", "Fizz", "Octo", "Hoot", "Buzz"]


class WSAgentUpdateMessage(BaseModel):
    """WebSocket message for multi-agent status updates."""
    type: Literal["agent_update"] = "agent_update"
    agentIndex: int
    agentName: str  # One of AGENT_MASCOTS
    agentType: AgentType = "coding"  # "coding" or "testing"
    featureId: int
    featureName: str
    state: AgentState
    thought: str | None = None
    timestamp: datetime


# ============================================================================
# Spec Chat Schemas
# ============================================================================

# Maximum image file size: 5 MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class ImageAttachment(BaseModel):
    """Image attachment from client for spec creation chat."""
    filename: str = Field(..., min_length=1, max_length=255)
    mimeType: Literal['image/jpeg', 'image/png']
    base64Data: str

    @field_validator('base64Data')
    @classmethod
    def validate_base64_and_size(cls, v: str) -> str:
        """Validate that base64 data is valid and within size limit."""
        try:
            decoded = base64.b64decode(v)
            if len(decoded) > MAX_IMAGE_SIZE:
                raise ValueError(
                    f'Image size ({len(decoded) / (1024 * 1024):.1f} MB) exceeds '
                    f'maximum of {MAX_IMAGE_SIZE // (1024 * 1024)} MB'
                )
            return v
        except Exception as e:
            if 'Image size' in str(e):
                raise
            raise ValueError(f'Invalid base64 data: {e}')


# ============================================================================
# Filesystem Schemas
# ============================================================================

class DriveInfo(BaseModel):
    """Information about a drive (Windows only)."""
    letter: str
    label: str
    available: bool = True


class DirectoryEntry(BaseModel):
    """An entry in a directory listing."""
    name: str
    path: str  # POSIX format
    is_directory: bool
    is_hidden: bool = False
    size: int | None = None  # Bytes, for files
    has_children: bool = False  # True if directory has subdirectories


class DirectoryListResponse(BaseModel):
    """Response for directory listing."""
    current_path: str  # POSIX format
    parent_path: str | None
    entries: list[DirectoryEntry]
    drives: list[DriveInfo] | None = None  # Windows only


class PathValidationResponse(BaseModel):
    """Response for path validation."""
    valid: bool
    exists: bool
    is_directory: bool
    can_read: bool
    can_write: bool
    message: str = ""


class CreateDirectoryRequest(BaseModel):
    """Request to create a new directory."""
    parent_path: str
    name: str = Field(..., min_length=1, max_length=255)


# ============================================================================
# Settings Schemas
# ============================================================================

# Note: VALID_MODELS and DEFAULT_MODEL are imported from registry at the top of this file


class ModelInfo(BaseModel):
    """Information about an available model."""
    id: str
    name: str


class ProviderInfo(BaseModel):
    """Information about an API provider."""
    id: str
    name: str
    base_url: str | None = None
    models: list[ModelInfo]
    default_model: str
    requires_auth: bool = False


class ProvidersResponse(BaseModel):
    """Response schema for available providers list."""
    providers: list[ProviderInfo]
    current: str


class SettingsResponse(BaseModel):
    """Response schema for global settings."""
    yolo_mode: bool = False
    model: str = DEFAULT_MODEL
    glm_mode: bool = False  # True when api_provider is "glm"
    ollama_mode: bool = False  # True when api_provider is "ollama"
    testing_agent_ratio: int = 1  # Regression testing agents (0-3)
    playwright_headless: bool = True
    batch_size: int = 3  # Features per coding agent batch (1-3)
    agent_session_logging: bool = True  # Persist agent output to SQLite
    api_provider: str = "claude"
    api_base_url: str | None = None
    api_has_auth_token: bool = False  # Never expose actual token
    api_model: str | None = None


class ModelsResponse(BaseModel):
    """Response schema for available models list."""
    models: list[ModelInfo]
    default: str


class SettingsUpdate(BaseModel):
    """Request schema for updating global settings."""
    yolo_mode: bool | None = None
    model: str | None = None
    testing_agent_ratio: int | None = None  # 0-3
    playwright_headless: bool | None = None
    batch_size: int | None = None  # Features per agent batch (1-3)
    agent_session_logging: bool | None = None
    api_provider: str | None = None
    api_base_url: str | None = Field(None, max_length=500)
    api_auth_token: str | None = Field(None, max_length=500)  # Write-only, never returned
    api_model: str | None = Field(None, max_length=200)

    @field_validator('api_base_url')
    @classmethod
    def validate_api_base_url(cls, v: str | None) -> str | None:
        if v is not None and v.strip():
            v = v.strip()
            if not v.startswith(("http://", "https://")):
                raise ValueError("api_base_url must start with http:// or https://")
        return v

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str | None, info) -> str | None:  # type: ignore[override]
        if v is not None:
            # Skip VALID_MODELS check when using an alternative API provider
            api_provider = info.data.get("api_provider")
            if api_provider and api_provider != "claude":
                return v
            if v not in VALID_MODELS:
                raise ValueError(f"Invalid model. Must be one of: {VALID_MODELS}")
        return v

    @field_validator('testing_agent_ratio')
    @classmethod
    def validate_testing_ratio(cls, v: int | None) -> int | None:
        if v is not None and (v < 0 or v > 3):
            raise ValueError("testing_agent_ratio must be between 0 and 3")
        return v

    @field_validator('batch_size')
    @classmethod
    def validate_batch_size(cls, v: int | None) -> int | None:
        if v is not None and (v < 1 or v > 3):
            raise ValueError("batch_size must be between 1 and 3")
        return v


# ============================================================================
# Dev Server Schemas
# ============================================================================


class DevServerStartRequest(BaseModel):
    """Request schema for starting the dev server."""
    command: str | None = None  # If None, uses effective command from config


class DevServerStatus(BaseModel):
    """Current dev server status."""
    status: Literal["stopped", "running", "crashed"]
    pid: int | None = None
    url: str | None = None
    command: str | None = None
    started_at: datetime | None = None


class DevServerActionResponse(BaseModel):
    """Response for dev server control actions."""
    success: bool
    status: Literal["stopped", "running", "crashed"]
    message: str = ""


class DevServerConfigResponse(BaseModel):
    """Response for dev server configuration."""
    detected_type: str | None = None
    detected_command: str | None = None
    custom_command: str | None = None
    effective_command: str | None = None


class DevServerConfigUpdate(BaseModel):
    """Request schema for updating dev server configuration."""
    custom_command: str | None = None  # None clears the custom command


# ============================================================================
# Dev Server WebSocket Message Schemas
# ============================================================================


class WSDevLogMessage(BaseModel):
    """WebSocket message for dev server log output."""
    type: Literal["dev_log"] = "dev_log"
    line: str
    timestamp: datetime


class WSDevServerStatusMessage(BaseModel):
    """WebSocket message for dev server status changes."""
    type: Literal["dev_server_status"] = "dev_server_status"
    status: Literal["stopped", "running", "crashed"]
    url: str | None = None


# ============================================================================
# Schedule Schemas
# ============================================================================


class ScheduleCreate(BaseModel):
    """Request schema for creating a schedule."""
    start_time: str = Field(
        ...,
        pattern=r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$',
        description="Start time in HH:MM format (local time, will be stored as UTC)"
    )
    duration_minutes: int = Field(
        ...,
        ge=1,
        le=1440,
        description="Duration in minutes (1-1440)"
    )
    days_of_week: int = Field(
        default=127,
        ge=0,
        le=127,
        description="Bitfield: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64"
    )
    enabled: bool = True
    yolo_mode: bool = False
    model: str | None = None
    max_concurrency: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Max concurrent agents (1-5)"
    )

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        """Validate model is in the allowed list (Claude) or allow any model for alternative providers."""
        if v is not None and v not in VALID_MODELS:
            from registry import get_all_settings
            settings = get_all_settings()
            if settings.get("api_provider", "claude") == "claude":
                raise ValueError(f"Invalid model. Must be one of: {VALID_MODELS}")
        return v


class ScheduleUpdate(BaseModel):
    """Request schema for updating a schedule (partial updates allowed)."""
    start_time: str | None = Field(
        None,
        pattern=r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$'
    )
    duration_minutes: int | None = Field(None, ge=1, le=1440)
    days_of_week: int | None = Field(None, ge=0, le=127)
    enabled: bool | None = None
    yolo_mode: bool | None = None
    model: str | None = None
    max_concurrency: int | None = Field(None, ge=1, le=5)

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        """Validate model is in the allowed list (Claude) or allow any model for alternative providers."""
        if v is not None and v not in VALID_MODELS:
            from registry import get_all_settings
            settings = get_all_settings()
            if settings.get("api_provider", "claude") == "claude":
                raise ValueError(f"Invalid model. Must be one of: {VALID_MODELS}")
        return v


class ScheduleResponse(BaseModel):
    """Response schema for a schedule."""
    id: int
    project_name: str
    start_time: str  # UTC, frontend converts to local
    duration_minutes: int
    days_of_week: int
    enabled: bool
    yolo_mode: bool
    model: str | None
    max_concurrency: int
    crash_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    """Response containing list of schedules."""
    schedules: list[ScheduleResponse]


class NextRunResponse(BaseModel):
    """Response for next scheduled run calculation."""
    has_schedules: bool
    next_start: datetime | None  # UTC
    next_end: datetime | None  # UTC (latest end if overlapping)
    is_currently_running: bool
    active_schedule_count: int
