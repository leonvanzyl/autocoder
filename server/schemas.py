"""
Pydantic Schemas
================

Request/Response models for the API endpoints.
"""

import base64
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


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


class ProjectDetail(BaseModel):
    """Detailed project information."""
    name: str
    path: str
    has_spec: bool
    stats: ProjectStats
    prompts_dir: str


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


# ============================================================================
# Feature Schemas
# ============================================================================

class FeatureBase(BaseModel):
    """Base feature attributes."""
    category: str
    name: str
    description: str
    steps: list[str]


class FeatureCreate(FeatureBase):
    """Request schema for creating a new feature."""
    priority: int | None = None


class FeatureResponse(FeatureBase):
    """Response schema for a feature."""
    id: int
    priority: int
    passes: bool
    in_progress: bool

    class Config:
        from_attributes = True


class FeatureListResponse(BaseModel):
    """Response containing list of features organized by status."""
    pending: list[FeatureResponse]
    in_progress: list[FeatureResponse]
    done: list[FeatureResponse]


# ============================================================================
# Agent Schemas
# ============================================================================

class AgentStartRequest(BaseModel):
    """Request schema for starting the agent."""
    yolo_mode: bool = False


class AgentStatus(BaseModel):
    """Current agent status."""
    status: Literal["stopped", "running", "paused", "crashed"]
    pid: int | None = None
    started_at: datetime | None = None
    yolo_mode: bool = False


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
    total: int
    percentage: float


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


class WSAgentStatusMessage(BaseModel):
    """WebSocket message for agent status changes."""
    type: Literal["agent_status"] = "agent_status"
    status: str


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
