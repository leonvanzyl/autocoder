"""
Settings Router
===============

API endpoints for global settings management.
Settings are stored in the registry database and shared across all projects.
"""

import mimetypes
import os
import sys
from pathlib import Path

from fastapi import APIRouter

from ..schemas import (
    DeniedCommandItem,
    DeniedCommandsResponse,
    ModelInfo,
    ModelsResponse,
    SettingsResponse,
    SettingsUpdate,
)

# Mimetype fix for Windows - must run before StaticFiles is mounted
mimetypes.add_type("text/javascript", ".js", True)

# Add root to path for registry import
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from registry import (
    CLAUDE_MODELS,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_MODELS,
    get_all_settings,
    set_setting,
)
from security import clear_denied_commands, get_denied_commands

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _parse_yolo_mode(value: str | None) -> bool:
    """Parse YOLO mode string to boolean."""
    return (value or "false").lower() == "true"


def _is_glm_mode() -> bool:
    """Check if GLM API is configured via environment variables."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    # GLM mode is when ANTHROPIC_BASE_URL is set but NOT pointing to Ollama
    return bool(base_url) and not _is_ollama_mode()


def _is_ollama_mode() -> bool:
    """Check if Ollama API is configured via environment variables."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    return "localhost:11434" in base_url or "127.0.0.1:11434" in base_url


@router.get("/models", response_model=ModelsResponse)
async def get_available_models():
    """Get list of available models.

    Frontend should call this to get the current list of models
    instead of hardcoding them.

    Returns appropriate models based on the configured API mode:
    - Ollama mode: Returns Ollama models (llama, codellama, etc.)
    - Claude mode: Returns Claude models (opus, sonnet)
    """
    if _is_ollama_mode():
        return ModelsResponse(
            models=[ModelInfo(id=m["id"], name=m["name"]) for m in OLLAMA_MODELS],
            default=DEFAULT_OLLAMA_MODEL,
        )
    return ModelsResponse(
        models=[ModelInfo(id=m["id"], name=m["name"]) for m in CLAUDE_MODELS],
        default=DEFAULT_MODEL,
    )


def _parse_int(value: str | None, default: int) -> int:
    """Parse integer setting with default fallback."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_bool(value: str | None, default: bool = False) -> bool:
    """Parse boolean setting with default fallback."""
    if value is None:
        return default
    return value.lower() == "true"


def _get_default_model() -> str:
    """Get the appropriate default model based on API mode."""
    return DEFAULT_OLLAMA_MODEL if _is_ollama_mode() else DEFAULT_MODEL


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current global settings."""
    all_settings = get_all_settings()
    default_model = _get_default_model()

    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", default_model),
        glm_mode=_is_glm_mode(),
        ollama_mode=_is_ollama_mode(),
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
        preferred_ide=all_settings.get("preferred_ide"),
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate):
    """Update global settings."""
    if update.yolo_mode is not None:
        set_setting("yolo_mode", "true" if update.yolo_mode else "false")

    if update.model is not None:
        set_setting("model", update.model)

    if update.testing_agent_ratio is not None:
        set_setting("testing_agent_ratio", str(update.testing_agent_ratio))

    if update.preferred_ide is not None:
        set_setting("preferred_ide", update.preferred_ide)

    # Return updated settings
    all_settings = get_all_settings()
    default_model = _get_default_model()
    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", default_model),
        glm_mode=_is_glm_mode(),
        ollama_mode=_is_ollama_mode(),
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
        preferred_ide=all_settings.get("preferred_ide"),
    )


@router.get("/denied-commands", response_model=DeniedCommandsResponse)
async def get_denied_commands_list():
    """Get list of recently denied commands.

    Returns the last 100 commands that were blocked by the security system.
    Useful for debugging and understanding what commands agents tried to run.
    """
    denied = get_denied_commands()
    return DeniedCommandsResponse(
        commands=[
            DeniedCommandItem(
                command=d["command"],
                reason=d["reason"],
                timestamp=d["timestamp"],
                project_dir=d["project_dir"],
            )
            for d in denied
        ],
        count=len(denied),
    )


@router.delete("/denied-commands")
async def clear_denied_commands_list():
    """Clear the denied commands history."""
    clear_denied_commands()
    return {"status": "cleared"}
