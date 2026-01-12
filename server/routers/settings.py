"""
Settings Router
===============

API endpoints for global settings management.
Settings are stored in the registry database and shared across all projects.
"""

import os
import sys
from pathlib import Path

from fastapi import APIRouter

from ..schemas import ModelInfo, ModelsResponse, SettingsResponse, SettingsUpdate

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
    return bool(os.getenv("ANTHROPIC_BASE_URL"))


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


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current global settings."""
    all_settings = get_all_settings()

    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=_is_glm_mode(),
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(update: SettingsUpdate):
    """Update global settings."""
    if update.yolo_mode is not None:
        set_setting("yolo_mode", "true" if update.yolo_mode else "false")

    if update.model is not None:
        set_setting("model", update.model)

    # Return updated settings
    all_settings = get_all_settings()
    return SettingsResponse(
        yolo_mode=_parse_yolo_mode(all_settings.get("yolo_mode")),
        model=all_settings.get("model", DEFAULT_MODEL),
        glm_mode=_is_glm_mode(),
    )
