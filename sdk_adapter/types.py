"""
Unified Types for SDK Adapters
==============================

Defines common event types and configuration options that work across
both Claude Agent SDK and Codex SDK.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine


class EventType(str, Enum):
    """Unified event types for agent responses."""

    TEXT = "text"  # Text content from agent
    TOOL_CALL = "tool_call"  # Tool/command execution started
    TOOL_RESULT = "tool_result"  # Tool/command execution result
    DONE = "done"  # Response complete
    ERROR = "error"  # Error occurred


@dataclass
class AgentEvent:
    """
    Unified event type for SDK responses.

    Both Claude and Codex SDKs emit different event structures.
    This class provides a common interface for handling events
    from either SDK.
    """

    type: EventType
    content: str = ""
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    tool_id: str | None = None
    is_error: bool = False
    raw: Any = None  # Original SDK-specific event for debugging


# Type alias for hook functions (Claude SDK style)
HookFunction = Callable[
    [dict[str, Any], str | None, dict[str, Any] | None],
    Coroutine[Any, Any, dict[str, Any]],
]


@dataclass
class AdapterOptions:
    """
    Configuration options for SDK adapters.

    These options are translated to SDK-specific configurations
    by each adapter implementation.
    """

    # Required
    model: str
    project_dir: Path

    # Agent configuration
    system_prompt: str = "You are an expert full-stack developer building a production-quality web application."
    max_turns: int = 300
    agent_type: str = "coding"  # "coding", "testing", or "initializer"
    agent_id: str | None = None  # For browser isolation in parallel mode

    # Tool configuration
    allowed_tools: list[str] = field(default_factory=list)
    mcp_servers: dict[str, Any] = field(default_factory=dict)

    # Environment
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    settings_file: str | None = None

    # Mode flags
    yolo_mode: bool = False

    # Hooks (Claude SDK only - Codex uses event-based model)
    bash_hook: HookFunction | None = None
    compact_hook: HookFunction | None = None

    # Extended context (Claude SDK only)
    betas: list[str] = field(default_factory=list)

    # Buffer size for large responses (screenshots, etc.)
    max_buffer_size: int = 10 * 1024 * 1024  # 10MB

    # CLI path override
    cli_path: str | None = None

    # Setting sources for project config
    setting_sources: list[str] = field(default_factory=lambda: ["project"])

    # Chat session options
    # Permission mode: "acceptEdits" or "bypassPermissions"
    permission_mode: str = "acceptEdits"
    # If True, setting_sources will include "user" for global skills/settings
    include_user_settings: bool = False
