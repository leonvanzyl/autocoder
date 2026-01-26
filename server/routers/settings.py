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

from ..schemas import ModelInfo, ModelsResponse, SettingsResponse, SettingsUpdate

# Mimetype fix for Windows - must run before StaticFiles is mounted
mimetypes.add_type("text/javascript", ".js", True)

# Add root to path for registry import
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from registry import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    get_all_settings,
    set_setting,
)

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
    """
    return ModelsResponse(
        models=[ModelInfo(id=m["id"], name=m["name"]) for m in AVAILABLE_MODELS],
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


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current global settings."""
    all_settings = get_all_settings()

    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=_is_glm_mode(),
        ollama_mode=_is_ollama_mode(),
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
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

    # Return updated settings
    all_settings = get_all_settings()
    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=_is_glm_mode(),
        ollama_mode=_is_ollama_mode(),
        testing_agent_ratio=_parse_int(all_settings.get("testing_agent_ratio"), 1),
    )
